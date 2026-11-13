-- Drive a MAME Mac (68k, ADB keyboard) from a list of timed actions.
-- Load with `-autoboot_script drive.lua -autoboot_delay 0`; the actions
-- come from the environment, times in emulated seconds since power-on:
--   MAME_DRIVE="35 key return; 46 key cmd+g; 53 shot; 53 dump -0x6546,1920,map.bin; 54 regs; 60 exit"
-- Verbs:
--   key A+B   press the keys together for 0.15 s: field names of :macadb:KEYn
--             ("s  S", "Return", ...), their first character (s, 1, ...) or
--             cmd, opt, shift, ctrl, return, space, esc, tab, left, right,
--             up, down, enter, power (cmd+power: MacsBug), button
--   shot      screenshot into -snapshot_directory
--   dump OFF,LEN,FILE  LEN bytes at CurrentA5 (low memory 0x904) + OFF
--             (the application's globals), read through the MMU
--   regs      print PC, SR, A5-A7, the stack, CurrentA5, CurApName, the A6
--             frame chain (return addresses) and the bytes around PC
--   insert MEDIA,FILE / eject MEDIA   change a disk (MEDIA: flop, flop2,
--             cdrm, hard1, ... as `mame -listmedia` names them; no spaces
--             in FILE)
--   feed MEDIA,FILE1|FILE2|...   from now on, whenever the drive is empty
--             (the Mac ejected the disk), insert the next file, round robin
--             and press Return 6 s later (an installer's "wrong disk" alert:
--             Continue ejects it; during copying Return does nothing)
--   move X,Y / click X,Y   put the cursor at screen X,Y through the Mac's
--             low memory (any Mac OS), click: then the mouse button
--   exit      quit MAME
-- Times run on the emulated clock, so a run with -nothrottle does the same.
local aliases = {
  cmd = "Command / Open Apple", opt = "Option / Solid Apple", shift = "Shift",
  ctrl = "Control", ["return"] = "Return", space = "Space", esc = "Esc",
  tab = "Tab", left = "Left Arrow", right = "Right Arrow", up = "Up Arrow",
  down = "Down Arrow", enter = "Keypad Enter", power = "Reset / Power",
  button = "Mouse Button 0",
}
local fields = {}
for tag, port in pairs(manager.machine.ioport.ports) do
  if tag:find(":macadb:KEY") or tag:find(":macadb:MOUSE") then
    for name, f in pairs(port.fields) do
      fields[name] = f
      local first = name:match("^(%S+)  ")
      if first then fields[first] = f end
    end
  end
end
local function field(n)
  local f = fields[aliases[n] or n]
  if not f then error("no key " .. n) end
  return f
end

local actions = {}
for item in (os.getenv("MAME_DRIVE") or ""):gmatch("[^;]+") do
  local t, verb, arg = item:match("^%s*([%d.]+)%s+(%a+)%s*(%S*)")
  table.insert(actions, { t = tonumber(t), verb = verb, arg = arg })
end
table.sort(actions, function(a, b) return a.t < b.t end)

local held, release_at, i = nil, nil, 1
local feeder, pending_click
sub = emu.add_machine_frame_notifier(function()
  local now = manager.machine.time:as_double()
  if feeder and not feeder.img.exists then
    if feeder.wait == 0 then
      feeder.wait = now + 2 -- give the Mac time to notice the empty drive
    elseif now >= feeder.wait then
      local f = feeder.files[feeder.next]
      feeder.next = feeder.next % #feeder.files + 1
      feeder.img:load(f)
      feeder.wait = 0
      feeder.press_at = now + 6 -- Return answers a "wrong disk" alert
      print(string.format("feed t=%.2f %s", now, f))
    end
  end
  if pending_click and now >= pending_click and not held then
    pending_click = nil
    held = { field("Mouse Button 0") }
    held[1]:set_value(1)
    release_at = now + 0.15
  end
  if feeder and feeder.press_at and now >= feeder.press_at and not held then
    feeder.press_at = nil
    held = { field("return") }
    held[1]:set_value(1)
    release_at = now + 0.15
  end
  if held and now >= release_at then
    for _, f in ipairs(held) do f:clear_value() end
    held = nil
  end
  while i <= #actions and now >= actions[i].t and not held do
    local a = actions[i]; i = i + 1
    if a.verb == "key" then
      held = {}
      for n in a.arg:gmatch("[^+]+") do table.insert(held, field(n)) end
      for _, f in ipairs(held) do f:set_value(1) end
      release_at = now + 0.15
    elseif a.verb == "shot" then
      manager.machine.video:snapshot()
    elseif a.verb == "dump" then
      -- dump OFFSET,LENGTH,FILE: LENGTH bytes at CurrentA5 + OFFSET (hex ok)
      local off, len, file = a.arg:match("^([^,]+),([^,]+),(.+)$")
      local space = manager.machine.devices[":maincpu"].spaces["program"]
      local a5 = space:readv_u32(0x904)
      local base = (a5 + math.tointeger(tonumber(off))) & 0xffffffff
      local out = assert(io.open(file, "wb"))
      for k = 0, math.tointeger(tonumber(len)) - 1 do
        out:write(string.char(space:readv_u8(base + k)))
      end
      out:close()
      print(string.format("dump t=%.2f A5=%08x %s", now, a5, file))
    elseif a.verb == "regs" then
      local cpu = manager.machine.devices[":maincpu"]
      local space = cpu.spaces["program"]
      local s = string.format("regs t=%.2f", now)
      for _, r in ipairs({ "PC", "SR", "A5", "A6", "A7" }) do
        s = s .. string.format(" %s=%08x", r, cpu.state[r].value)
      end
      local sp = cpu.state["A7"].value
      s = s .. "\n  stack:"
      for k = 0, 15 do s = s .. string.format(" %08x", space:readv_u32(sp + 4 * k)) end
      local nlen = space:readv_u8(0x910)
      local name = ""
      for k = 1, math.min(nlen, 31) do name = name .. string.char(space:readv_u8(0x910 + k)) end
      s = s .. string.format("\n  CurrentA5=%08x CurApName=%s\n  frames:", space:readv_u32(0x904), name)
      local fp = cpu.state["A6"].value
      for _ = 1, 12 do
        if fp == 0 or fp > 0x8000000 then break end
        s = s .. string.format(" %08x", space:readv_u32(fp + 4))
        fp = space:readv_u32(fp) & 0xffffffff
      end
      local pc = cpu.state["PC"].value
      s = s .. string.format("\n  code@%08x:", pc - 16)
      for k = 0, 47 do s = s .. string.format("%02x", space:readv_u8(pc - 16 + k)) end
      print(s)
    elseif a.verb == "insert" or a.verb == "eject" then
      -- insert MEDIA,FILE / eject MEDIA: MEDIA is the brief name (flop,
      -- flop1, flop2, cdrm, hard1, ...) as in `mame -listmedia`
      local media, file = a.arg:match("^([^,]+),?(.*)$")
      local img
      for _, d in pairs(manager.machine.images) do
        if d.brief_instance_name == media or d.instance_name == media then img = d end
      end
      if not img then error("no media " .. media) end
      if a.verb == "eject" then img:unload() else img:load(file) end
      print(string.format("%s t=%.2f %s %s", a.verb, now, media, file))
    elseif a.verb == "feed" then
      -- feed MEDIA,FILE1|FILE2|...: whenever the drive is empty (the Mac
      -- ejected the disk), insert the next file, round robin; an
      -- installer ejects a wrong disk and asks again
      local media, list = a.arg:match("^([^,]+),(.+)$")
      local files = {}
      for f in list:gmatch("[^|]+") do table.insert(files, f) end
      for _, d in pairs(manager.machine.images) do
        if d.brief_instance_name == media or d.instance_name == media then
          feeder = { img = d, files = files, next = 1, wait = 0 }
        end
      end
      if not feeder then error("no media " .. media) end
    elseif a.verb == "move" or a.verb == "click" then
      -- move X,Y / click X,Y: put the cursor there through low memory
      -- (MTemp 0x828 and RawMouse 0x82c as v,h; CrsrNew 0x8ce), then for
      -- click press the mouse button 0.3 s later for 0.15 s
      local x, y = a.arg:match("^(%d+),(%d+)$")
      local space = manager.machine.devices[":maincpu"].spaces["program"]
      for _, at in ipairs({ 0x828, 0x82c }) do
        space:writev_u16(at, tonumber(y))
        space:writev_u16(at + 2, tonumber(x))
      end
      space:writev_u8(0x8ce, space:readv_u8(0x8cf)) -- CrsrNew = CrsrCouple
      if a.verb == "click" then
        pending_click = now + 0.3
      end
    elseif a.verb == "exit" then
      manager.machine:exit()
    end
  end
end)
