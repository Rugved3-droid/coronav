"""CoroNav installation smoke test.

Checks Python deps, SOFA import, anatomy data, and API key config
WITHOUT launching a full SOFA simulation or making any API calls.

Run:
    python scripts/check_install.py
"""
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PASS = "[OK]"
WARN = "[WARN]"
FAIL = "[FAIL]"

errors = []
warnings = []


def check(label: str, fn):
    try:
        result = fn()
        tag = PASS if result is not False else FAIL
        if tag == FAIL:
            errors.append(label)
        print(f"  {tag}  {label}")
        return result is not False
    except Exception as e:
        print(f"  {FAIL}  {label}: {e}")
        errors.append(label)
        return False


def warn(label: str, msg: str):
    print(f"  {WARN}  {label}: {msg}")
    warnings.append(label)


print("\n=== CoroNav Installation Check ===\n")

print("[ Python environment ]")
check("Python >= 3.8",
      lambda: sys.version_info >= (3, 8))
check("Python < 3.12 (SOFA 23.06 not tested above 3.11)",
      lambda: sys.version_info < (3, 12) or warnings.append("python_version") or True)

print("\n[ Required Python packages ]")
for pkg, import_name in [
    ("numpy", "numpy"),
    ("anthropic", "anthropic"),
    ("Pillow", "PIL"),
    ("scipy", "scipy"),
]:
    check(f"import {import_name}",
          lambda imp=import_name: importlib.import_module(imp) is not None)

print("\n[ stEVE / SOFA ]")
check("import eve (stEVE package)",
      lambda: importlib.import_module("eve") is not None)
check("import eve.intervention.simulation.sofabeamadapter",
      lambda: importlib.import_module("eve.intervention.simulation.sofabeamadapter") is not None)

print("\n[ CoroNav package ]")
check("import coronav",
      lambda: importlib.import_module("coronav") is not None)
check("import coronav.operator.claude",
      lambda: importlib.import_module("coronav.operator.claude") is not None)
check("import coronav.env",
      lambda: importlib.import_module("coronav.env") is not None)
check("import coronav.metrics",
      lambda: importlib.import_module("coronav.metrics") is not None)
check("import coronav.sim.coronary_sim",
      lambda: importlib.import_module("coronav.sim.coronary_sim") is not None)

print("\n[ Anatomy data (A1 — bundled) ]")
a1_dir = ROOT / "data" / "anatomy" / "a1_vmr0066"
check("A1 directory exists",
      lambda: a1_dir.exists())
check("A1 mesh file (clipped_left.obj)",
      lambda: (a1_dir / "clipped_left.obj").exists())
check("A1 .vtp file (clipped_left.vtp)",
      lambda: (a1_dir / "clipped_left.vtp").exists())
check("A1 paths/ directory",
      lambda: (a1_dir / "paths").exists())
check("A1 LAD.pth centerline",
      lambda: (a1_dir / "paths" / "LAD.pth").exists())
check("A1 LCX.pth centerline",
      lambda: (a1_dir / "paths" / "LCX.pth").exists())
check("A1 VMR license file",
      lambda: (a1_dir / "LICENSE_VMR0066").exists())

pth_count = len(list((a1_dir / "paths").glob("*.pth"))) if (a1_dir / "paths").exists() else 0
check(f"A1 has >= 10 .pth centerline files (found {pth_count})",
      lambda: pth_count >= 10)

def _centerlines_loadable():
    from coronav.sim.pth_centerlines import left_coronary_branches
    branches, ins_pt, ins_dir = left_coronary_branches(str(a1_dir / "paths"))
    return len(branches) > 0 and any(b.name == "lad" for b in branches)

check("A1 centerlines are loadable (left_coronary_branches parses LAD/LCX)",
      _centerlines_loadable)

print("\n[ Anatomy data (A2/A3 — optional, requires ASOCA registration) ]")
for akey, dname in [("a2", "a2_asoca_n12"), ("a3", "a3_asoca_n5")]:
    adir = ROOT / "data" / "anatomy" / dname
    if adir.exists():
        check(f"{akey.upper()} directory found", lambda d=adir: d.exists())
    else:
        warn(f"{akey.upper()} not installed",
             "run scripts/download_asoca.py after registering at asoca.grand-challenge.org")

print("\n[ API key (optional here — required to run) ]")
api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if api_key:
    if api_key.startswith("sk-ant-"):
        print(f"  {PASS}  ANTHROPIC_API_KEY is set (starts with sk-ant-...)")
    else:
        warn("ANTHROPIC_API_KEY", "set but does not look like an Anthropic key")
else:
    warn("ANTHROPIC_API_KEY",
         "not set — needed to run ClaudeOperator. See .env.example")

print("\n[ Protocol file ]")
proto = ROOT / "benchmarks" / "protocol.json"
check("benchmarks/protocol.json exists", lambda: proto.exists())
if proto.exists():
    import json
    p = json.loads(proto.read_text(encoding="utf-8"))
    check("protocol.json has 'a1' anatomy block",
          lambda: "a1" in p.get("anatomies", {}))

print()
if errors:
    print(f"FAILED: {len(errors)} check(s) failed — {', '.join(errors)}")
    print("Fix the errors above before running the benchmark.")
    sys.exit(1)
elif warnings:
    print(f"OK with {len(warnings)} warning(s). A1 quickstart should work.")
    print("Run:  python examples/quickstart.py")
else:
    print("All checks passed. Ready to run:")
    print("  python examples/quickstart.py")
    print("  python benchmarks/run_benchmark.py --operator claude --anatomy a1")
