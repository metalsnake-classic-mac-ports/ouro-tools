// Ghidra headless post-script: name TOC slots and transition vectors after
// the functions they lead to. A TVector is 8 bytes {code address, TOC};
// a TOC slot (r2 - 0x8000 ... r2 + 0x7fff) holding the address of a
// TVector becomes "TV_<function>", the TVector itself "tvec_<function>".
// Writes "slot target name" lines to the argument file.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.math.BigInteger;

public class NameTOC extends GhidraScript {
    @Override
    public void run() throws Exception {
        Memory mem = currentProgram.getMemory();
        Register r2 = currentProgram.getProgramContext().getRegister("r2");
        BigInteger toc = null;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            toc = currentProgram.getProgramContext().getValue(r2, f.getEntryPoint(), false);
            if (toc != null) break;
        }
        long t = toc.longValue();
        int n = 0;
        try (PrintWriter w = new PrintWriter(new FileWriter(getScriptArgs()[0]))) {
            for (long s = t - 0x8000; s < t + 0x8000; s += 4) {
                Address slot = toAddr(s);
                long v, code, tvtoc;
                Address tv;
                try {   // uninitialised (bss) bytes cannot be read
                    v = mem.getInt(slot) & 0xffffffffL;
                    tv = toAddr(v);
                    if (!mem.contains(tv) || mem.getBlock(tv).isExecute()) continue;
                    code = mem.getInt(tv) & 0xffffffffL;
                    tvtoc = mem.getInt(tv.add(4)) & 0xffffffffL;
                } catch (MemoryAccessException | AddressOutOfBoundsException e) {
                    continue;
                }
                if (tvtoc != t) continue;
                Function f = getFunctionAt(toAddr(code));
                if (f == null) continue;
                String name = f.getName().replaceAll("^\\.(debug|glue)::", "").replaceAll("^\\.", "");
                createLabel(slot, "TV_" + name, true, SourceType.ANALYSIS);
                createLabel(tv, "tvec_" + name, true, SourceType.ANALYSIS);
                w.printf("%s %s %s%n", slot, tv, name);
                n++;
            }
        }
        println("NameTOC: " + n + " TOC slots name a function");
    }
}
