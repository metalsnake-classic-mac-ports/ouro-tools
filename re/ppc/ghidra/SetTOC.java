// Ghidra headless post-script: give register r2 (the TOC pointer) its value
// over the whole code block. The PEF loader sets it only for functions it
// found itself; functions created later (ApplyNames) otherwise decompile
// with "unaff_r2". The value is taken from the entry of the first function
// that has it. Optional argument: a file to write it to ("0x..." - the
// Python tools read it as toc.txt).
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import java.io.FileWriter;
import java.math.BigInteger;

public class SetTOC extends GhidraScript {
    @Override
    public void run() throws Exception {
        ProgramContext ctx = currentProgram.getProgramContext();
        Register r2 = ctx.getRegister("r2");
        BigInteger toc = null;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            toc = ctx.getValue(r2, f.getEntryPoint(), false);
            if (toc != null) break;
        }
        if (toc == null) { println("SetTOC: no r2 value found"); return; }
        if (getScriptArgs().length > 0) {
            try (FileWriter w = new FileWriter(getScriptArgs()[0])) {
                w.write("0x" + toc.toString(16) + "\n");
            }
        }
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (b.isExecute()) {
                ctx.setValue(r2, b.getStart(), b.getEnd(), toc);
                println("SetTOC: r2 = 0x" + toc.toString(16) + " over " + b.getName());
            }
        }
    }
}
