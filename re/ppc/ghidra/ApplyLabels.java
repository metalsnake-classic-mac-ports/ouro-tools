// Ghidra headless post-script: label globals from a list file (e.g. re/ghidra/globals.txt).
// Line format: "<address> <name>[:type] [comment]" labels that address;
// "@<toc slot> <name>[:type] [comment]" labels the address the TOC slot
// points to and names the slot itself "p_<name>" (typed as a pointer).
// type: short, ushort, int, char, byte, ptr (default: none - keep).
// The data at the address is cleared first so that no larger data item
// overlaps it. '#' starts a comment line. Argument: the list file.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;

public class ApplyLabels extends GhidraScript {
    DataType type(String t) {
        switch (t) {
            case "short": return ShortDataType.dataType;
            case "ushort": return UnsignedShortDataType.dataType;
            case "int": return IntegerDataType.dataType;
            case "char": return CharDataType.dataType;
            case "byte": return ByteDataType.dataType;
            case "ptr": return PointerDataType.dataType;
            default: return null;
        }
    }

    void define(Address a, DataType t) throws Exception {
        if (t == null) return;
        clearListing(a, a.add(t.getLength() - 1));
        createData(a, t);
    }

    @Override
    public void run() throws Exception {
        int n = 0;
        for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] p = line.split("\\s+", 3);
            String[] nt = p[1].split(":");
            String name = nt[0];
            DataType t = nt.length > 1 ? type(nt[1]) : null;
            Address a;
            if (p[0].startsWith("@")) {
                Address slot = toAddr(Long.parseLong(p[0].substring(1), 16));
                a = toAddr(getInt(slot) & 0xffffffffL);
                DataType pt = t != null ? new PointerDataType(t) : PointerDataType.dataType;
                clearListing(slot, slot.add(3));
                createData(slot, pt);
                createLabel(slot, "p_" + name, true, SourceType.USER_DEFINED);
            } else {
                a = toAddr(Long.parseLong(p[0], 16));
            }
            try {
                define(a, t);
            } catch (Exception e) {
                println("ApplyLabels: cannot type " + name + " at " + a + ": " + e.getMessage());
            }
            createLabel(a, name, true, SourceType.USER_DEFINED);
            if (p.length > 2) setEOLComment(a, p[2]);
            n++;
        }
        println("ApplyLabels: " + n + " labels");
    }
}
