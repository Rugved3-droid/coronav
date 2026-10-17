"""Re-run the original analysis scripts against the traces in artifacts/traces/.

The scripts in artifacts/analysis/ are kept exactly as they were run. They read
traces from the absolute folder they were written against (R = r"D:\\steve\\pilot\\runs").
artifacts/traces/ keeps the same relative layout as that folder, so this runner
substitutes that one literal in memory, at import time, and changes nothing else.
The files on disk are never edited. Outputs are written where the scripts always wrote
them: artifacts/results/. After a run, `git status artifacts/results` shows what changed.

    python artifacts/reproduce.py            # every trace-consuming phase, in order
    python artifacts/reproduce.py phase4_primary phase6h_a2_steps
    python artifacts/reproduce.py --check    # run all, then diff against the committed outputs

Requires Python >= 3.10 with numpy, scipy, statsmodels and matplotlib. No simulator,
no network, no model calls.
"""
import importlib.machinery
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE / "analysis"
TRACES = HERE / "traces"
ORIGINAL_R = 'r"D:\\steve\\pilot\\runs"'

# Order matters only where a later phase reads an earlier phase's output.
PHASES = [
    "phase3_selection_bias",      # A1 navigation: worst-rank Wilcoxon, win ratio, log-rank, Fisher
    "phase4_primary",             # A1 f_rot_LM paired Wilcoxon, HL, MWU sensitivity
    "phase5_multiplicity",        # confirmatory family, Holm; per-arm f_rot_LM
    "phase6_leave_a3_out",
    "phase6c_integrity",
    "phase6d_denominators",       # exclusions / non-attempts
    "phase6e_api_audit",          # transmission failures
    "phase6h_a2_steps",           # A2 steps: paired Wilcoxon, HL, ranges
    "phase6i_hold_sensitivity",
    "phase6j_validity_threshold",
    "phase6k_a3_stall",
    "phase7_operator_speed",
    "phase7h_dispersion",
    "phase7i_pairing",            # within-pair correlations
    "phase7i_worstrank_corr",
    "esm_tables",                 # Supplementary Table S1
]
# Not run here: claims_table.py and build_manuscript.py read the manuscript sources
# (manuscript/*.md), which are not part of this release; their committed outputs are
# results/numeric_claims_table.* and results/manifest.csv. The phase7a/7c/7d/7e/7g/7j and
# always_advance scripts drive the SOFA simulator and need the A2 mesh (see README).


def patched(source: str) -> str:
    return source.replace(ORIGINAL_R, repr(str(TRACES)))


class _Loader(importlib.machinery.SourceFileLoader):
    def get_data(self, path):
        if path.endswith(".pyc"):
            raise OSError("bytecode cache disabled")   # always compile the patched source
        data = super().get_data(path)
        if path.endswith(".py"):
            data = patched(data.decode("utf-8")).encode("utf-8")
        return data


def _run_one(name: str) -> None:
    sys.dont_write_bytecode = True
    hook = importlib.machinery.FileFinder.path_hook((_Loader, [".py"]))
    sys.path_hooks.insert(0, lambda p: hook(p) if Path(p).resolve() == ANALYSIS else (_ for _ in ()).throw(ImportError))
    sys.path_importer_cache.clear()
    sys.path.insert(0, str(ANALYSIS))
    path = ANALYSIS / f"{name}.py"
    code = compile(patched(path.read_text(encoding="utf-8")), str(path), "exec")
    sys.argv = [str(path)]
    exec(code, {"__name__": "__main__", "__file__": str(path)})


def check() -> int:
    """Compare every regenerated file in artifacts/results/ with the committed version.

    Line endings are ignored (Windows writes CRLF, the committed files are LF); nothing
    else is. PDFs differ only in their embedded CreationDate and are reported separately.
    """
    root = HERE.parent
    changed = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "artifacts/results"],
                             capture_output=True, text=True, check=True).stdout.splitlines()
    differ = []
    for line in changed:
        rel = line[3:].strip()
        if rel.endswith(".pdf"):
            print(f"  (pdf, compare visually)  {rel}")
            continue
        old = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{rel}"], capture_output=True).stdout
        new = (root / rel).read_bytes()
        if old.replace(b"\r", b"") != new.replace(b"\r", b""):
            differ.append(rel)
    for rel in differ:
        print(f"  CONTENT DIFFERS          {rel}")
    print(f"{len(differ)} file(s) differ from the committed artifacts (line endings ignored)")
    return 1 if differ else 0


def main(argv):
    if argv[:1] == ["--one"]:
        _run_one(argv[1])
        return 0
    do_check = "--check" in argv
    names = [a for a in argv if a != "--check"] or PHASES
    failed = []
    for name in names:
        r = subprocess.run([sys.executable, __file__, "--one", name], capture_output=True, text=True)
        print(f"{name:32s} exit={r.returncode}")
        if r.returncode:
            failed.append(name)
            print(r.stderr[-2000:])
    if do_check:
        return check() or (1 if failed else 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
