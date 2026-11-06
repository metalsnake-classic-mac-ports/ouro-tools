// Ghidra headless post-script: create and name functions from a list of
// "address size name" lines (re/tools/pef_traceback.py output).
// Argument: input file path.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.nio.file.*;

public class ApplyNames extends GhidraScript {
    @Override
    public void run() throws Exception {
        int created = 0, renamed = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            if (line.trim().startsWith("#")) continue;
            String[] p = line.trim().split("\\s+");
            if (p.length < 3) continue;
            Address a = toAddr(Long.parseLong(p[0], 16));
            String name = p[2].startsWith(".") ? p[2].substring(1) : p[2];
            Function f = getFunctionAt(a);
            if (f == null) {
                Function inside = getFunctionContaining(a);
                if (inside != null && !inside.getEntryPoint().equals(a)) {
                    removeFunction(inside);
                }
                new DisassembleCommand(a, null, true).applyTo(currentProgram, monitor);
                new CreateFunctionCmd(a).applyTo(currentProgram, monitor);
                f = getFunctionAt(a);
                if (f == null) { println("could not create " + p[0] + " " + name); continue; }
                created++;
            }
            if (!f.getName().equals(name)) {
                f.setName(name, SourceType.IMPORTED);
                renamed++;
            }
        }
        println("ApplyNames: created " + created + ", renamed " + renamed);
    }
}
