# Shared by make-system711-disk.sh and make-system755-disk.sh (sourced, not
# run): the tools that go onto the test disks, unpacked from the archives
# the user provides and packed as MacBinary for `hcopy -m`. Each function
# takes the archive and the folder for its work files and prints the paths
# of the MacBinary files it wrote. Needs unar, hfsutils and $TOOLS.

# MacsBug from Apple's MacsBug_6.x.sit: "MacsBug" (into the System Folder)
# and, where the archive has one, "Debugger Prefs" (also there).
extra_macsbug() {
    archive="$1"; work="$2"
    mkdir -p "$work/macsbug"
    unar -q -forks fork -o "$work/macsbug" "$archive" >/dev/null
    find "$work/macsbug" -type f \( -name MacsBug -o -name 'Debugger Prefs' \) |
        grep -v -e dcmds -e Building | while read -r f; do
        out="$work/$(basename "$f" | tr ' ' '_').bin"
        python3 -I "$TOOLS/re/tomacbinary.py" "$f" "$out"
        echo "$out"
    done
}

# Debugger! (siddhartha77): an application that drops into MacsBug
# (DebugStr) - the way in where no key does it (MAME).
extra_debugger() {
    archive="$1"; work="$2"
    mkdir -p "$work/debugger"
    unar -q -forks fork -o "$work/debugger" "$archive" >/dev/null
    app="$(find "$work/debugger" -type f -name 'Debugger!' | head -1)"
    python3 -I "$TOOLS/re/tomacbinary.py" "$app" "$work/debugger.bin"
    echo "$work/debugger.bin"
}

# StuffIt Expander from stuffit_expander_4.0.2.sea_.bin: an NDIF image in a
# StuffIt archive; the image is under 800K, so it is padded for hfsutils.
extra_expander() {
    archive="$1"; work="$2"
    mkdir -p "$work/expander"
    unar -q -forks fork -o "$work/expander" "$archive" >/dev/null
    img="$(find "$work/expander" -name '*.img' | head -1)"
    python3 -I "$TOOLS/re/ndif.py" "$img" "$img/..namedfork/rsrc" "$work/expander.dsk" >/dev/null
    python3 -I -c "import sys; f=open(sys.argv[1],'r+b'); f.truncate(max(819200, f.seek(0,2)))" \
        "$work/expander.dsk"
    hmount "$work/expander.dsk" >/dev/null
    folder="$(hls | head -1)"
    app="$(hls ":$folder" | grep -v '^Read Us' | head -1)"
    hcopy -m ":$folder:$app" "$work/expander.bin"
    humount >/dev/null
    echo "$work/expander.bin"
}

# Delete a folder with everything in it from the mounted HFS volume
# (hfsutils has no recursive delete). Names may start with a space, as the
# Installer's " Installer Temp" does: read them with IFS= to keep it.
hfs_rm_tree() {
    hls -a "$1" | while IFS= read -r name; do
        if hls -l -d "$1:$name" 2>/dev/null | grep -q '^d'; then
            hfs_rm_tree "$1:$name"
        else
            hdel "$1:$name"
        fi
    done
    hrmdir "$1"
}
