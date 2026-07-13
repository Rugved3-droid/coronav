"""CoroNav benchmark runner.

Usage
-----
# A1 quickstart (bundled anatomy, no registration required):
    python benchmarks/run_benchmark.py --operator claude --anatomy a1

# Full benchmark (A2/A3 require ASOCA registration — run scripts/download_asoca.py first):
    python benchmarks/run_benchmark.py --operator claude --anatomy a1 a2 a3

# Custom operator:
    python benchmarks/run_benchmark.py --operator mypackage.MyOperator --anatomy a1

# Dry-run (check env + anatomy, don't run SOFA):
    python benchmarks/run_benchmark.py --operator claude --anatomy a1 --dry-run
"""
import argparse
import importlib
import json
import os
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
    parts = spec.rsplit(".", 1)
    if len(parts) != 2:
        print(f"ERROR: --operator must be 'claude', 'template', or 'module.ClassName'")
        sys.exit(1)
    mod = importlib.import_module(parts[0])
    cls = getattr(mod, parts[1])
    return cls()


def check_anatomy(anatomy_key: str, protocol: dict) -> bool:
    adir = ANATOMY_DIRS.get(anatomy_key)
    if adir is None:
        print(f"  ERROR: Unknown anatomy '{anatomy_key}'. Valid: {list(ANATOMY_DIRS.keys())}")
        return False
    if not adir.exists():
        src = protocol["anatomies"][anatomy_key]["source"]
        print(f"  ERROR: Anatomy directory not found: {adir}")
        print(f"         Source: {src}")
        if anatomy_key in ("a2", "a3"):
            print("         Run:  python scripts/download_asoca.py  (after registering)")
        return False
    return True


def run_anatomy(anatomy_key: str, protocol: dict, operator, out_dir: Path, dry_run: bool):
    from coronav.env import build_env, run_episode

    aconf = protocol["anatomies"][anatomy_key]
    adir = str(ANATOMY_DIRS[anatomy_key])
    seeds = aconf["seeds"]
    n_steps = aconf["step_budget"]
    n_eps = aconf["n_episodes"]
    mode = protocol["imaging"]["mode"]

    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.jsonl"

    print(f"\n[{anatomy_key.upper()}] {aconf['name']}")
    print(f"  n={n_eps} episodes, {n_steps} steps each, mode={mode}")
    print(f"  Output: {trace_path}")

    if dry_run:
        print("  [dry-run] Skipping SOFA launch.")
        return

    env, sim, fluoro, branch_kds, mid_lad, binary_mask = build_env(
        anatomy_dir=adir,
        n_steps=n_steps,
        image_rot_zx=protocol["imaging"]["image_rot_zx"],
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
            terminal = any(r.get("terminal") for r in rows)
            success = any(
                r.get("terminal") and not r.get("truncation", True) for r in rows
            )
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
        help="'claude', 'template', or 'module.ClassName'",
    )
    parser.add_argument(
        "--anatomy",
        nargs="+",
        default=["a1"],
        choices=["a1", "a2", "a3"],
        help="Anatomy key(s). Default: a1 (bundled, no registration).",
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

    for anat in args.anatomy:
        if not check_anatomy(anat, protocol):
            sys.exit(1)

    operator = resolve_operator(args.operator)

    for anat in args.anatomy:
        run_anatomy(anat, protocol, operator, out_root / anat, args.dry_run)

    print(f"\nBenchmark complete. To view results:")
    print(f"  python benchmarks/report.py --run-dir {out_root}")


if __name__ == "__main__":
    main()
