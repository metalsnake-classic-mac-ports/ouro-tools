// Ghidra headless post-script: decompile the functions at the given
// offsets. Where Ghidra has no function there (a routine without LINK A6,
// a second entry into another routine's code), one is made for this run:
// disassembled from the offset and given a body by Ghidra's flow (run the
// project with -readOnly so nothing is saved). Prints, per offset, the
// function's entry and body range and its C.
// Arguments: the output file, then hex offsets into the segment (0x
// optional).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.io.*;
import java.util.Arrays;

public class DecompileAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        Address base = currentProgram.getMinAddress();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        String[] args = getScriptArgs();
        PrintWriter w = new PrintWriter(new FileWriter(args[0]));
        for (String arg : Arrays.copyOfRange(args, 1, args.length)) {
            String hex = arg.toLowerCase().startsWith("0x") ? arg.substring(2) : arg;
            Address a = base.add(Long.parseLong(hex, 16));
            Function f = getFunctionAt(a);
            String made = "";
            if (f == null) {
                Function around = getFunctionContaining(a);
                disassemble(a);
                f = createFunction(a, null);
                made = around == null ? " (made for this run)" : " (made for this run, inside " + around.getName() + ")";
            }
            if (f == null) {
                w.println("===== " + arg + ": no function could be made there");
                continue;
            }
            AddressSetView body = f.getBody();
            w.println("===== " + f.getName() + " @ " + f.getEntryPoint() + made
                    + " body " + body.getMinAddress() + "-" + body.getMaxAddress());
            DecompileResults r = ifc.decompileFunction(f, 60, monitor);
            w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "// decompile failed: " + r.getErrorMessage());
        }
        w.close();
    }
}
