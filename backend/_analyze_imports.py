import ast, sys
from pathlib import Path

root = Path(__file__).parent / "app"

module_imports = {}
for f in sorted(root.rglob("*.py")):
    if "__pycache__" in str(f):
        continue
    rel = f.relative_to(root.parent).with_suffix("").as_posix().replace("/", ".")
    try:
        with open(f, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except SyntaxError:
        continue
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    parts = alias.name.split(".")
                    if len(parts) >= 2:
                        imports.add("app." + parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app."):
                parts = node.module.split(".")
                if len(parts) >= 2:
                    imports.add("app." + parts[1])
    module_imports[rel] = sorted(imports)

layers = {
    "api": [m for m in module_imports if m.startswith("app.api.") and m != "app.api"],
    "agents": [m for m in module_imports if m.startswith("app.agents.")],
    "engine": [m for m in module_imports if m.startswith("app.engine.")],
    "integrations": [m for m in module_imports if m.startswith("app.integrations.")],
    "models": [m for m in module_imports if m.startswith("app.models.")],
    "schemas": [m for m in module_imports if m.startswith("app.schemas.")],
    "services": [m for m in module_imports if m.startswith("app.services.")],
}

print("CROSS-LAYER DEPENDENCY MATRIX")
print("="*60)
for layer_name, files in sorted(layers.items()):
    all_imports = set()
    for f in files:
        all_imports.update(module_imports.get(f, []))
    # Only show imports to OTHER layers
    cross = sorted(all_imports)
    if cross:
        print(f"\n{layer_name} ({len(files)} files):")
        for imp in cross:
            print(f"  -> {imp}")

# Check for cycles: mutual imports between two non-overlapping modules
print("\n\nCYCLE DETECTION (any pair where each imports the other's module)")
print("="*60)
mods = list(module_imports.keys())
cycles_found = 0
for i, m1 in enumerate(mods):
    for m2 in mods[i+1:]:
        i1 = module_imports.get(m1, [])
        i2 = module_imports.get(m2, [])
        m1_prefix = ".".join(m1.split(".")[:2])  # e.g. "app.api"
        m2_prefix = ".".join(m2.split(".")[:2])
        # Check if m1 imports from m2's layer and vice versa
        m1_imports_m2_layer = any(imp.startswith(m2_prefix) for imp in i1)
        m2_imports_m1_layer = any(imp.startswith(m1_prefix) for imp in i2)
        if m1_imports_m2_layer and m2_imports_m1_layer:
            print(f"  LAYER CYCLE: {m1_prefix} <-> {m2_prefix}")
            print(f"    {m1} imports {[i for i in i1 if i.startswith(m2_prefix)]}")
            print(f"    {m2} imports {[i for i in i2 if i.startswith(m1_prefix)]}")
            cycles_found += 1
            break

if cycles_found == 0:
    print("  None detected (at layer level)")

# Also check specific file-level cycles
print("\n\nFILE-LEVEL CYCLE DETECTION")
for i, m1 in enumerate(mods):
    for m2 in mods[i+1:]:
        i1 = module_imports.get(m1, [])
        i2 = module_imports.get(m2, [])
        if any(m2.startswith(imp) for imp in i1) and any(m1.startswith(imp) for imp in i2):
            print(f"  CYCLE: {m1} <-> {m2}")
            cycles_found += 1
