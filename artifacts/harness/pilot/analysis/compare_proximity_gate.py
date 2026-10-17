"""
Comparison report: full_intervention vs proximity_gate
Outputs: D:\steve\pilot\runs\2026-06-15_22-18-15\comparison_report.md
"""
import json
from pathlib import Path
from collections import defaultdict

GATE_RUN  = Path(r"D:\steve\pilot\runs\2026-06-15_22-18-15")
GATE_TRACE = GATE_RUN / "arm_proximity_gate" / "trace.jsonl"

BASE_RUN  = Path(r"D:\steve\pilot\runs\2026-06-14_21-20-25")
BASE_TRACE = BASE_RUN / "arm_full_intervention" / "trace.jsonl"

OUT = GATE_RUN / "comparison_report.md"

def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def group_eps(rows):
    eps = defaultdict(list)
    for r in rows:
        eps[r["episode"]].append(r)
    for k in eps:
        eps[k].sort(key=lambda x: x["step"])
    return eps

def ep_stats(steps):
    dists   = [s["tip_target_dist"] for s in steps]
    success_step = next((s["step"] for s in steps if s.get("terminal") and not s.get("truncation")), None)
    rot_all  = [s for s in steps if abs((s.get("parsed_action") or {}).get("rotation", 0) or 0) > 0.01]
    gate_act = [s for s in steps if s.get("gate_active")]
    gate_fir = [s for s in steps if s.get("gate_suppressed_rotation")]

    # late-episode rotation: steps where dist < 80mm
    rot_sub80 = [s for s in rot_all if s["tip_target_dist"] < 80.0]

    return {
        "seed":          steps[0]["seed"],
        "n_steps":       len(steps),
        "success_step":  success_step,
        "start_dist":    dists[0],          # dist_obs of step 1 (actually dist_post)
        "min_dist":      min(dists),
        "final_dist":    dists[-1],
        "mean_dist":     sum(dists)/len(dists),
        "rot_total":     len(rot_all),
        "rot_sub80":     len(rot_sub80),    # rotation steps when dist < 80mm
        "gate_active_steps": len(gate_act),
        "gate_fires":    len(gate_fir),
        "retractions":   steps[-1].get("retractions_used_so_far", 0),
    }

base_eps  = group_eps(load(BASE_TRACE))
gate_eps  = group_eps(load(GATE_TRACE))

base_stats = {ep: ep_stats(steps) for ep, steps in base_eps.items()}
gate_stats = {ep: ep_stats(steps) for ep, steps in gate_eps.items()}

# categorise baseline failures
BASE_SUBTYPE_A = {1, 2, 6, 7}   # got close (<80mm min dist) then regressed
BASE_SUBTYPE_B = {8, 9, 10, 11, 12, 13, 14, 15}   # never got close
BASE_SUCCESS   = {3, 4, 5}

# ── build report ──────────────────────────────────────────────────────────────
md = []
md.append("# Proximity Gate vs Full Intervention — Comparison Report\n")
md.append(f"**Baseline:** `{BASE_RUN.name}` — arm_full_intervention  ")
md.append(f"**Gate run:** `{GATE_RUN.name}` — arm_proximity_gate\n")

# ── headline ──────────────────────────────────────────────────────────────────
md.append("---\n")
md.append("## Headline Results\n")
md.append("| Metric | Full Intervention | Proximity Gate | Change |")
md.append("|---|---|---|---|")

base_succ = sum(1 for s in base_stats.values() if s["success_step"])
gate_succ = sum(1 for s in gate_stats.values() if s["success_step"])
base_rot  = sum(s["rot_total"] for s in base_stats.values())
gate_rot  = sum(s["rot_total"] for s in gate_stats.values())
base_rot80 = sum(s["rot_sub80"] for s in base_stats.values())
gate_rot80 = sum(s["rot_sub80"] for s in gate_stats.values())
base_ret  = sum(s["retractions"] for s in base_stats.values())
gate_ret  = sum(s["retractions"] for s in gate_stats.values())

md.append(f"| Targets reached | **{base_succ}/15** | **{gate_succ}/15** | {'▲ +'+str(gate_succ-base_succ) if gate_succ>base_succ else '▼ '+str(gate_succ-base_succ)} |")
md.append(f"| Total rotation steps | {base_rot} (5.8%) | {gate_rot} (31.0%) | ▲ +{gate_rot-base_rot} |")
md.append(f"| Rotation steps at dist<80mm | {base_rot80} | {gate_rot80} | {'+' if gate_rot80>=base_rot80 else ''}{gate_rot80-base_rot80} |")
md.append(f"| Total retraction steps | {base_ret} | {gate_ret} | {gate_ret-base_ret:+d} |")
md.append(f"| Gate suppressions (harness) | N/A | 0 | model obeyed prompt voluntarily |")

# ── per-episode paired table ───────────────────────────────────────────────────
md.append("\n---\n")
md.append("## Per-Episode Paired Comparison\n")
md.append("| Ep | Seed | Group | Base result | Gate result | Min dist Δ | Final dist Δ | Rot steps Δ | Gate-active steps | Assessment |")
md.append("|---|---|---|---|---|---|---|---|---|---|")

for ep in range(1, 16):
    bs = base_stats[ep]
    gs = gate_stats[ep]
    seed = bs["seed"]

    if ep in BASE_SUCCESS:     group = "prev-success"
    elif ep in BASE_SUBTYPE_A: group = "subtype-A"
    else:                      group = "subtype-B"

    def fmt(s):
        if s["success_step"]:
            return f"SUCCESS step {s['success_step']} ({s['final_dist']:.1f}mm)"
        return f"FAIL (min {s['min_dist']:.1f}mm, end {s['final_dist']:.1f}mm)"

    min_delta   = gs["min_dist"]   - bs["min_dist"]
    final_delta = gs["final_dist"] - bs["final_dist"]
    rot_delta   = gs["rot_total"]  - bs["rot_total"]

    base_ok = bs["success_step"] is not None
    gate_ok = gs["success_step"] is not None

    if not base_ok and gate_ok:
        verdict = "**NEW SUCCESS** ✓"
    elif base_ok and not gate_ok:
        verdict = "**REGRESSION** ✗"
    elif base_ok and gate_ok:
        faster = (gs["success_step"] or 99) < (bs["success_step"] or 99)
        verdict = f"still SUCCESS {'(faster)' if faster else '(same speed)'}"
    else:
        if min_delta < -5:
            verdict = "improved (closer)"
        elif min_delta > 5:
            verdict = "worse (farther)"
        else:
            verdict = "no change"

    md.append(
        f"| {ep} | {seed} | {group} | {fmt(bs)} | {fmt(gs)} | "
        f"{min_delta:+.1f}mm | {final_delta:+.1f}mm | {rot_delta:+d} | {gs['gate_active_steps']} | {verdict} |"
    )

# ── by group ──────────────────────────────────────────────────────────────────
md.append("\n---\n")
md.append("## Results by Group\n")

groups = [
    ("Previously successful (eps 3, 4, 5)", BASE_SUCCESS),
    ("Subtype A — got close, then regressed (eps 1, 2, 6, 7)", BASE_SUBTYPE_A),
    ("Subtype B — never got close (eps 8–15)", BASE_SUBTYPE_B),
]
for label, ep_set in groups:
    md.append(f"### {label}\n")
    for ep in sorted(ep_set):
        bs = base_stats[ep]; gs = gate_stats[ep]
        base_r = "SUCCESS step "+str(bs["success_step"]) if bs["success_step"] else f"FAIL (min {bs['min_dist']:.1f}mm)"
        gate_r = "SUCCESS step "+str(gs["success_step"]) if gs["success_step"] else f"FAIL (min {gs['min_dist']:.1f}mm)"
        delta  = gs["min_dist"] - bs["min_dist"]
        rot_d  = gs["rot_total"] - bs["rot_total"]
        md.append(f"- **Ep {ep} (seed {bs['seed']}):** {base_r} → {gate_r}  "
                  f"min dist Δ={delta:+.1f}mm  rot Δ={rot_d:+d} steps  gate-active={gs['gate_active_steps']} steps")
    md.append("")

# ── gate mechanism post-mortem ─────────────────────────────────────────────────
md.append("---\n")
md.append("## Gate Mechanism Post-Mortem — Why 0 Suppressions?\n")
md.append(
    "The harness gate (hard suppression) never fired. Two reasons:\n\n"
    "**1. The system prompt instruction worked.** In the 4 successful episodes "
    "(eps 1, 3, 5, 6), the gate condition (dist<80mm AND trend=decreasing) was "
    "active for 14–19 steps each — yet the model chose 0 rotation steps in those "
    "windows. The model read the PROXIMITY GATE instruction and voluntarily obeyed it. "
    "Hard enforcement was not needed.\n\n"
    "**2. Failed episodes rotated before reaching 80mm.** The 254 rotation steps in "
    "failed episodes occurred predominantly at dist>80mm. In episodes that never "
    "reached 80mm (e.g. ep12: 213mm final), all 57 rotation steps were at large "
    "distances. In episodes that approached 80mm (eps 4, 9, 10, 11), the rotation "
    "happened in earlier steps before entering the gate zone — so the gate condition "
    "was not yet active when rotation occurred.\n\n"
    "The gate solved the specific Subtype-A regression (ep1 and ep6 converted to "
    "successes). But a new problem emerged: the system prompt's framing of rotation "
    "as a valid 'wrong-branch escape' tool appears to have encouraged much higher "
    "rotation rates in stuck episodes (31% of steps vs 5.8% baseline), causing ep4 "
    "to regress and keeping Subtype-B episodes stuck.\n"
)

# ── rotation distribution ──────────────────────────────────────────────────────
md.append("---\n")
md.append("## Late-Episode Rotation Comparison (dist < 80mm)\n")
md.append("| Ep | Group | Base rot@<80mm | Gate rot@<80mm | Gate-active steps | Gate fires |")
md.append("|---|---|---|---|---|---|")
for ep in range(1, 16):
    bs = base_stats[ep]; gs = gate_stats[ep]
    if ep in BASE_SUCCESS: g = "prev-success"
    elif ep in BASE_SUBTYPE_A: g = "subtype-A"
    else: g = "subtype-B"
    md.append(f"| {ep} | {g} | {bs['rot_sub80']} | {gs['rot_sub80']} | {gs['gate_active_steps']} | {gs['gate_fires']} |")

# ── key findings ───────────────────────────────────────────────────────────────
md.append("\n---\n")
md.append("## Key Findings\n")
md.append(
    "1. **Net improvement: +1 target** (3/15 → 4/15). Two Subtype-A episodes converted "
    "(eps 1 and 6); one previously successful episode regressed (ep4).\n\n"
    "2. **Gate instruction worked without enforcement.** The model followed the PROXIMITY "
    "GATE rule voluntarily in all successful episodes. The harness suppression was never "
    "needed — the prompt alone was sufficient for the cases where the hypothesis was correct.\n\n"
    "3. **Unintended side effect: rotation explosion.** Total rotation steps: 49 → 256 "
    "(5× increase). The gate framing ('reserve rotation for early-episode wrong-branch "
    "escape') appears to have licensed more rotation in failed episodes, not less. Ep12 "
    "spent 57/60 steps rotating without ever advancing meaningfully (final: 213mm).\n\n"
    "4. **Ep4 regression is a rotation casualty.** Ep4 used 31 rotation steps and failed "
    "at 44.1mm. In the full intervention it succeeded with near-zero rotation in 38 steps. "
    "The gate framing changed the model's policy in this episode from 'advance relentlessly' "
    "to 'rotate when stuck' — and the rotation trapped it.\n\n"
    "5. **Subtype-B episodes improved in mean distance but not in success rate.** Episodes "
    "8–11, 13–15 all showed dramatically lower mean distances (e.g. ep8: 215mm → 100mm mean) "
    "but none reached the target. They are getting closer but spending steps on rotation "
    "rather than converting proximity into success.\n\n"
    "6. **The core hypothesis was partially correct.** Preventing rotation in the final "
    "approach DID help (Subtype-A conversions). But the framing introduced a rotation "
    "incentive elsewhere. The next experiment should decouple these effects.\n\n"
    "**Recommended next experiment:** Remove the 'reserve rotation for wrong-branch escape' "
    "framing entirely. Instead, make the rotation rule purely mechanical: 'only rotate when "
    "consecutive_no_progress >= 3.' The gate (no rotation near target with decreasing trend) "
    "stays. This removes the wrong-branch rotation incentive while preserving the proximity "
    "gate benefit.\n"
)

report = "\n".join(md)
OUT.write_text(report, encoding="utf-8")
print(f"Written: {OUT}  ({len(report):,} chars)")
