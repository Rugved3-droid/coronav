"""Pool every artifact-backed always-advance draw at the harness default speed (35 mm/s).

WHY. The open-loop floor has been quoted as the single Phase 7a draw (A1 17/25 = 68%). That
anatomy has since been drawn at the same speed, seeds, budget and policy six more times - five
in Phase 7g, one in Phase 7c - and 68% is the top of the resulting distribution, drawn once.
Phase 7h showed the across-repetition variance is consistent with independent binomial draws, so
pooling the draws as independent trials is the defensible estimate of the floor.

WHAT IS POOLED. Only draws with a surviving artifact:
  7a  results/baselines/always_advance_a{1,2}_summary.json      one draw each
  7g  results/baselines/nondeterminism_floor_a{1,2}.json        five draws each
  7c  results/baselines/phase7c_shards/phase7c_a{1,2}_35_r1.json one draw each

WHAT IS NOT, AND WHY. Two further A2 draws at 35 mm/s were observed during the 7c smoke tests
(15/25 and 17/25). Their artifacts were deleted when the single-process runner was replaced by
the sharded one. A number with no artifact cannot enter the manifest, so they are excluded - and
the sensitivity of the pooled A2 figure to including them is printed rather than hidden.

RUN WITH THE SOFA ENV PYTHON (imports the single Wilson implementation from phase7c).
"""
from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase7c_speed_sweep import OUT_DIR, RESULTS_DIR, wilson

SHARDS = os.path.join(OUT_DIR, "phase7c_shards")

# Observed but artifact-less; reported as a sensitivity only.
UNBACKED = {"a2": [(15, 25), (17, 25)]}


def draw(k: int, n: int, phase: str, src: str) -> dict:
    return {"k": k, "n": n, "rate": k / n, "phase": phase, "source": src}


def collect(anat: str) -> list[dict]:
    out = []
    p7a = os.path.join(OUT_DIR, f"always_advance_{anat}_summary.json")
    s = json.load(open(p7a, encoding="utf-8"))
    assert float(s["advance_mm_s"]) == 35.0
    out.append(draw(int(s["n_success"]), int(s["n_run"]), "7a", p7a))

    p7g = os.path.join(OUT_DIR, f"nondeterminism_floor_{anat}.json")
    g = json.load(open(p7g, encoding="utf-8"))
    assert float(g["advance_mm_s"]) == 35.0
    for i, rep in enumerate(g["passes"], start=1):
        run = [e for e in rep if not e["reset_failed"]]
        out.append(draw(sum(1 for e in run if e["success"]), len(run), f"7g r{i}", p7g))

    for fn in sorted(os.listdir(SHARDS)):
        if fn.startswith(f"phase7c_{anat}_35_") and fn.endswith(".json"):
            p = os.path.join(SHARDS, fn)
            c = json.load(open(p, encoding="utf-8"))
            assert float(c["speed"]) == 35.0
            out.append(draw(int(c["n_success"]), int(c["n_run"]), "7c", p))
    return out


def main() -> int:
    lines = []
    def emit(s=""):
        print(s, flush=True)
        lines.append(s)

    emit("=" * 84)
    emit("POOLED OPEN-LOOP FLOOR AT THE HARNESS DEFAULT, 35 mm/s")
    emit("=" * 84)
    rows = []
    for anat, label in (("a1", "A1 VMR0066"), ("a2", "A2 ASOCA Normal_12")):
        ds = collect(anat)
        k = sum(d["k"] for d in ds)
        n = sum(d["n"] for d in ds)
        lo, hi = wilson(k, n)
        rates = [d["rate"] for d in ds]
        emit("")
        emit(f"{label}: {len(ds)} artifact-backed draws")
        for d in ds:
            emit(f"   {d['phase']:<6} {d['k']:>2}/{d['n']}  {100*d['rate']:5.1f}%")
        emit(f"   POOLED {k}/{n} = {100*k/n:.1f}%   Wilson 95% CI [{100*lo:.1f}, {100*hi:.1f}]")
        emit(f"   RANGE across draws {100*min(rates):.0f}-{100*max(rates):.0f}%")
        extra = UNBACKED.get(anat, [])
        if extra:
            k2 = k + sum(a for a, _ in extra)
            n2 = n + sum(b for _, b in extra)
            emit(f"   sensitivity: adding {len(extra)} artifact-less smoke draws "
                 f"{[f'{a}/{b}' for a, b in extra]} would give {k2}/{n2} = {100*k2/n2:.1f}%."
                 f" Excluded: no artifact.")
        rows.append([label, len(ds), k, n, f"{k/n:.4f}", f"{lo:.4f}", f"{hi:.4f}",
                     f"{min(rates):.4f}", f"{max(rates):.4f}",
                     " ".join(f"{d['k']}/{d['n']}" for d in ds)])

    with open(os.path.join(RESULTS_DIR, "phase7c_pooled_default.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "draws", "successes", "episodes", "pooled_rate", "wilson_lo",
                    "wilson_hi", "min_draw_rate", "max_draw_rate", "draws_k_over_n"])
        w.writerows(rows)
    with open(os.path.join(RESULTS_DIR, "phase7c_pooled_default_report.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    emit("")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7c_pooled_default.csv')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
