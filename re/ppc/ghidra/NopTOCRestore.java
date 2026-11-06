// Ghidra headless post-script (analysis aid only, changes the Ghidra
// database, not the original file): replace every "lwz r2,0x14(r1)"
// (0x80410014, the TOC restore after a cross-fragment call) by a nop, so
// the decompiler keeps r2 = TOC (SetTOC.java) through calls.
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;

public class NopTOCRestore extends GhidraScript {
    @Override
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        byte[] nop = {0x60, 0, 0, 0};
        int n = 0;
        for (MemoryBlock b : mem.getBlocks()) {
            if (!b.isExecute()) continue;
            for (Address a = b.getStart(); a.compareTo(b.getEnd()) < 0; a = a.add(4)) {
                if (mem.getInt(a) == 0x80410014) {
                    clearListing(a, a.add(3));
                    mem.setBytes(a, nop);
                    new DisassembleCommand(a, new AddressSet(a, a.add(3)), false).applyTo(currentProgram, monitor);
                    n++;
                }
            }
        }
        println("NopTOCRestore: " + n + " TOC restores replaced");
    }
}
