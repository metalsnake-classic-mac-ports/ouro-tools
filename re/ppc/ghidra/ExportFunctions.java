// Ghidra headless post-script: list every function as "address size name".
// Argument: output file path.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.*;

public class ExportFunctions extends GhidraScript {
    @Override
    public void run() throws Exception {
        try (PrintWriter w = new PrintWriter(new FileWriter(getScriptArgs()[0]))) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                w.printf("%s %d %s%n", f.getEntryPoint(), f.getBody().getNumAddresses(), f.getName());
            }
        }
    }
}
