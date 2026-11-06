// Ghidra headless post-script: print the memory blocks.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;

public class ListBlocks extends GhidraScript {
    @Override
    public void run() throws Exception {
        for (MemoryBlock b : currentProgram.getMemory().getBlocks()) {
            println(String.format("BLOCK %-12s %s-%s init=%b r=%b w=%b x=%b vol=%b", b.getName(), b.getStart(), b.getEnd(),
                b.isInitialized(), b.isRead(), b.isWrite(), b.isExecute(), b.isVolatile()));
        }
    }
}
