// Ghidra headless post-script: build a structure (e.g. the game's sprite
// record) from a spec file and make it the type of the first parameter of
// every routine whose name matches a pattern.
// Arguments: spec file, struct size (hex), struct name, name pattern (Java
// regex, e.g. "(Setup|Handle|Hit)\\w*Sprite\\w*|DoKick"). The first
// parameter is named after the struct's first letters ("sp" for Sprite).
// Spec lines: "<offset> <type> <name> [comment]"; type short, ushort, int,
// uint, char, byte, ptr, rect; '#' starts a comment line.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.pcode.HighFunctionDBUtil;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;

public class ApplyStruct extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        int size = Integer.parseInt(args[1].replace("0x", ""), 16);
        String structName = args[2];
        String pattern = args[3];
        DataTypeManager dtm = currentProgram.getDataTypeManager();
        StructureDataType rect = new StructureDataType("Rect", 0);
        for (String f : new String[] {"top", "left", "bottom", "right"}) rect.add(ShortDataType.dataType, f, null);
        StructureDataType s = new StructureDataType(structName, size);
        for (String line : Files.readAllLines(Paths.get(args[0]))) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) continue;
            String[] p = line.split("\\s+", 4);
            int off = Integer.decode(p[0]);
            DataType t;
            switch (p[1]) {
                case "short": t = ShortDataType.dataType; break;
                case "int": t = IntegerDataType.dataType; break;
                case "char": t = CharDataType.dataType; break;
                case "Rect": t = rect; break;
                default: t = PointerDataType.dataType;
            }
            s.replaceAtOffset(off, t, t.getLength(), p[2], p.length > 3 ? p[3] : null);
        }
        DataType sd = dtm.addDataType(s, DataTypeConflictHandler.REPLACE_HANDLER);
        DataType sp = new PointerDataType(sd);
        int n = 0;
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            String name = f.getName();
            if (!name.matches(pattern)) continue;
            if (f.getParameterCount() == 0) {
                // parameters exist only in the decompiler until committed
                DecompileResults r = ifc.decompileFunction(f, 60, monitor);
                if (r.decompileCompleted()) {
                    HighFunctionDBUtil.commitParamsToDatabase(r.getHighFunction(), true,
                        HighFunctionDBUtil.ReturnCommitOption.NO_COMMIT, SourceType.ANALYSIS);
                }
            }
            if (f.getParameterCount() == 0) continue;
            Parameter p0 = f.getParameter(0);
            p0.setDataType(sp, SourceType.USER_DEFINED);
            p0.setName(structName.substring(0, Math.min(2, structName.length())).toLowerCase(), SourceType.USER_DEFINED);
            n++;
        }
        println("ApplyStruct: " + structName + " (" + size + " bytes) on " + n + " routines");
    }
}
