// Ghidra headless post-script: list the imported symbols (IMPORTS block)
// as "address library::name" lines, and the TOC slots that point to them.
// Argument: output file.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.*;
import java.io.*;

public class ExportImports extends GhidraScript {
    @Override
    public void run() throws Exception {
        MemoryBlock b = currentProgram.getMemory().getBlock("IMPORTS");
        SymbolTable st = currentProgram.getSymbolTable();
        int n = 0;
        try (PrintWriter w = new PrintWriter(new FileWriter(getScriptArgs()[0]))) {
            SymbolIterator it = st.getSymbolIterator(b.getStart(), true);
            while (it.hasNext()) {
                Symbol s = it.next();
                if (!b.contains(s.getAddress())) break;
                w.printf("%s %s%n", s.getAddress(), s.getName(true));
                n++;
            }
        }
        println("ExportImports: " + n + " imports");
    }
}
