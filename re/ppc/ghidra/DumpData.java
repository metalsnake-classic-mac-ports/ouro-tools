// Ghidra headless post-script: write the initialised data block (the
// unpacked PEF data section, with relocations applied) to a file.
// Argument: output file. The first 4 bytes of the file are not data: they
// hold the block's start address (big-endian).
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;
import java.io.*;

public class DumpData extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            if (b.isInitialized() && b.isWrite() && !b.isExecute()) {
                byte[] buf = new byte[(int) b.getSize()];
                b.getBytes(b.getStart(), buf);
                try (DataOutputStream o = new DataOutputStream(new FileOutputStream(getScriptArgs()[0]))) {
                    o.writeInt((int) b.getStart().getOffset());
                    o.write(buf);
                }
                println("DumpData: " + b.getName() + " " + b.getStart() + " " + buf.length + " bytes");
                return;
            }
        }
    }
}
