"""CoroNav benchmark runner.

Every run produced by this script is a NEW run. It is not a reproduction of
the manuscript's results, whose original traces are not in this repository
(see docs/MANUSCRIPT_CONCORDANCE.md). A ``run_meta.json`` saying so is written
next to each trace.

Usage
-----
# Image-free open-loop control (no API calls, no cost):
    python benchmarks/run_benchmark.py --operator open_loop --anatomy a1

# One operator arm (bundled A1, no registration required):
    python benchmarks/run_benchmark.py --operator claude --anatomy a1 --mode wire_only
    python benchmarks/run_benchmark.py --operator claude --anatomy a1 --mode overlay

# Both observation conditions on both retained anatomies (A2 requires ASOCA
# registration and a prepared anatomy directory — see scripts/download_asoca.py):
    python benchmarks/run_benchmark.py --operator claude --anatomy a1 a2 --mode wire_only overlay

# Custom operator:
    python benchmarks/run_benchmark.py --operator mypackage.MyOperator --anatomy a1

# Dry-run (check env + anatomy, don't run SOFA):
    python benchmarks/run_benchmark.py --operator claude --anatomy a1 --dry-run
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PROTOCOL_PATH = Path(__file__).parent / "protocol.json"
DATA_ROOT = ROOT / "data" / "anatomy"

ANATOMY_DIRS = {
    "a1": DATA_ROOT / "a1_vmr0066",
    "a2": DATA_ROOT / "a2_asoca_n12",
    "a3": DATA_ROOT / "a3_asoca_n5",
}


def load_protocol():
    with open(PROTOCOL_PATH, encoding="utf-8") as f:
        return json.load(f)


def resolve_operator(spec: str):
    """Resolve 'claude' -> ClaudeOperator, or 'pkg.ClassName' -> that class."""
    if spec == "claude":
        from coronav.operator.claude import ClaudeOperator
        return ClaudeOperator()
    if spec == "template":
        from coronav.operator.template import TemplateOperator
        return TemplateOperator()
    if spec == "open_loop":
        from coronav.operator.open_loop import OpenLoopOperator
        return OpenLoopOperator()
    parts = spec.rsplit(".", 1)
    if len(parts) != 2:
        print(f"ERROR: --operator must be 'claude', 'open_loop', 'template', or 'module.ClassName'")
        sys.exit(1)
    mod = importlib.import_module(parts[0])
    cls = getattr(mod, parts[1])
    return cls()


def check_anatomy(anatomy_key: str, protocol: dict, allow_excluded: bool = False) -> bool:
    adir = ANATOMY_DIRS.get(anatomy_key)
    if adir is None:
        print(f"  ERROR: Unknown anatomy '{anatomy_key}'. Valid: {list(ANATOMY_DIRS.keys())}")
        return False
    aconf = protocol["anatomies"][anatomy_key]
    if aconf.get("status") == "excluded":
        if not allow_excluded:
            print(f"  ERROR: '{anatomy_key}' ({aconf['name']}) is EXCLUDED from the manuscript:")
            print(f"         {aconf['exclusion_reason']}")
            print("         Pass --allow-excluded to run it for archival inspection only.")
            return False
        print(f"  WARNING: running EXCLUDED anatomy '{anatomy_key}'. Its results support no manuscript claim.")
    if not adir.exists():
        src = protocol["anatomies"][anatomy_key]["source"]
        print(f"  ERROR: Anatomy directory not found: {adir}")
        print(f"         Source: {src}")
        if anatomy_key in ("a2", "a3"):
            print("         Run:  python scripts/download_asoca.py  (after registering)")
        return False
    return True


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def write_run_meta(out_dir: Path, anatomy_key: str, mode: str, protocol: dict,
                   operator, operator_spec: str):
    aconf = protocol["anatomies"][anatomy_key]
    meta = {
        "provenance": (
            "New run generated with this repository. NOT a reproduction of the "
            "manuscript's original runs, whose traces are not in this repository."
        ),
        "created": datetime.now().isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "protocol_version": protocol.get("_version"),
        "anatomy": anatomy_key,
        "anatomy_status": aconf.get("status", "retained"),
        "mode": mode,
        "step_budget": aconf["step_budget"],
        "seeds": aconf["seeds"][: aconf["n_episodes"]],
        "dt_simulation_s": protocol["simulation"]["dt_simulation_s"],
        "operator_spec": operator_spec,
        "operator_class": type(operator).__name__,
        "operator_model": getattr(operator, "model", None),
        "decoding": "operator decoding is not seeded by this harness; seeds fix the simulator reset only",
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def run_anatomy(anatomy_key: str, protocol: dict, operator, out_dir: Path, dry_run: bool,
                mode: str = "wire_only", operator_spec: str = ""):
    from coronav.env import build_env, run_episode

    aconf = protocol["anatomies"][anatomy_key]
    adir = str(ANATOMY_DIRS[anatomy_key])
    seeds = aconf["seeds"]
    n_steps = aconf["step_budget"]
    n_eps = aconf["n_episodes"]
    dt = protocol["simulation"]["dt_simulation_s"]

    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"

    print(f"\n[{anatomy_key.upper()}] {aconf['name']}")
    print(f"  n={n_eps} episodes, {n_steps} steps each, mode={mode}, dt={dt} s")
    print(f"  Output: {trace_path}")

    if dry_run:
        print("  [dry-run] Skipping SOFA launch.")
        return

    write_run_meta(out_dir, anatomy_key, mode, protocol, operator, operator_spec)
    env, sim, fluoro, branch_kds, mid_lad, binary_mask = build_env(
        anatomy_dir=adir,
        n_steps=n_steps,
        image_rot_zx=protocol["imaging"]["image_rot_zx"],
        dt_simulation=dt,
    )

    total_rows = 0
    with open(trace_path, "w", encoding="utf-8") as fout:
        for i, seed in enumerate(seeds[:n_eps]):
            t0 = time.time()
            operator.reset()
            rows = run_episode(
                env=env,
                sim=sim,
                fluoro=fluoro,
                binary_mask=binary_mask,
                branch_kds=branch_kds,
                mid_lad=mid_lad,
                operator=operator,
                seed=seed,
                episode_num=i,
                n_steps=n_steps,
                mode=mode,
                verbose=False,
            )
            for r in rows:
                fout.write(json.dumps(r) + "\n")
            total_rows += len(rows)
            dt = time.time() - t0
            success = any(r.get("terminal") for r in rows)
            print(
                f"  ep {i+1:02d}/{n_eps}  seed={seed}"
                f"  steps={len(rows)}"
                f"  {'SUCCESS' if success else 'timeout'}"
                f"  {dt:.1f}s"
            )
            fout.flush()

    env.close()
    print(f"  Done. {total_rows} rows written to {trace_path}")


def main():
    parser = argparse.ArgumentParser(description="CoroNav benchmark runner")
    parser.add_argument(
        "--operator",
        default="claude",
        help="'claude', 'open_loop' (image-free control, no API calls), "
             "'template', or 'module.ClassName'",
    )
    parser.add_argument(
        "--anatomy",
        nargs="+",
        default=["a1"],
        choices=["a1", "a2", "a3"],
        help="Anatomy key(s). Default: a1 (bundled, no registration). "
             "a3 is excluded from the manuscript and needs --allow-excluded.",
    )
    parser.add_argument(
        "--mode",
        nargs="+",
        default=None,
        choices=["wire_only", "overlay", "contrast"],
        help="Observation condition(s). The manuscript compares wire_only and "
             "overlay; contrast is exploratory. Default: protocol default_mode.",
    )
    parser.add_argument(
        "--allow-excluded",
        action="store_true",
        help="Allow running anatomies marked excluded in protocol.json (archival only).",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for trace files. Default: runs/<timestamp>/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check setup without launching SOFA.",
    )
    args = parser.parse_args()

    protocol = load_protocol()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = Path(args.out_dir) if args.out_dir else ROOT / "runs" / ts

    print("=== CoroNav Benchmark ===")
    print(f"Operator: {args.operator}")
    print(f"Anatomies: {args.anatomy}")
    print(f"Output root: {out_root}")

    modes = args.mode or [protocol["imaging"]["default_mode"]]
    print(f"Modes: {modes}")
    print(f"Simulation timestep: {protocol['simulation']['dt_simulation_s']} s")

    for anat in args.anatomy:
        if not check_anatomy(anat, protocol, args.allow_excluded):
            sys.exit(1)

    operator = resolve_operator(args.operator)

    for anat in args.anatomy:
        for mode in modes:
            # Single-mode runs keep the original <run>/<anatomy>/trace.jsonl layout.
            out_dir = out_root / anat if len(modes) == 1 else out_root / anat / mode
            run_anatomy(anat, protocol, operator, out_dir, args.dry_run,
                        mode=mode, operator_spec=args.operator)

    print(f"\nBenchmark complete. To view results:")
    print(f"  python benchmarks/report.py --run-dir {out_root}")


if __name__ == "__main__":
    main()
