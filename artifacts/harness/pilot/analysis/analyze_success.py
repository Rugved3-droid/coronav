"""
Full Intervention Success Analysis
Analyzes D:\steve\pilot\runs\2026-06-14_21-20-25\arm_full_intervention\trace.jsonl
and cross-references against earlier arm traces to produce success_analysis.md
"""

import json
import math
from pathlib import Path
from collections import defaultdict

# ── paths ──────────────────────────────────────────────────────────────────────
RUN_DIR   = Path(r"D:\steve\pilot\runs\2026-06-14_21-20-25")
TRACE     = RUN_DIR / "arm_full_intervention" / "trace.jsonl"
OUT_MD    = RUN_DIR / "arm_full_intervention" / "success_analysis.md"   # task asks here
OUT_MD2   = RUN_DIR / "success_analysis.md"                             # also at run root

CROSS_REF = {
    "v4_arm_a":       Path(r"D:\steve\pilot\runs\2026-06-14_11-21-23\arm_a\trace.jsonl"),
    "arm_a_topology": Path(r"D:\steve\pilot\runs\2026-06-14_13-39-15\arm_a_topology\trace.jsonl"),
    "arm_a_budget":   Path(r"D:\steve\pilot\runs\2026-06-14_19-31-14\arm_a_budget\trace.jsonl"),
}

# ── helpers ────────────────────────────────────────────────────────────────────
def load_trace(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def group_by_episode(rows):
    eps = defaultdict(list)
    for r in rows:
        eps[r["episode"]].append(r)
    for k in eps:
        eps[k].sort(key=lambda x: x["step"])
    return eps


def first_dist(steps):
    return steps[0]["tip_target_dist"] if steps else None


def min_dist(steps):
    return min(s["tip_target_dist"] for s in steps) if steps else None


def success_step(steps):
    for s in steps:
        if s.get("terminal") and not s.get("truncation"):
            return s["step"]
    return None


def is_rotation(s):
    r = s.get("parsed_action", {}).get("rotation", 0.0)
    return r is not None and abs(r) > 0.01


def trunc(txt, n=80):
    if txt is None:
        return ""
    txt = txt.replace("\n", " ").replace("|", "/")
    return txt[:n] + "…" if len(txt) > n else txt


# ── load main trace ────────────────────────────────────────────────────────────
print("Loading main trace …")
main_rows  = load_trace(TRACE)
main_eps   = group_by_episode(main_rows)

# ── load cross-ref traces ──────────────────────────────────────────────────────
print("Loading cross-reference traces …")
cross = {}
for label, path in CROSS_REF.items():
    if path.exists():
        rows = load_trace(path)
        cross[label] = group_by_episode(rows)
    else:
        cross[label] = {}
        print(f"  WARNING: {path} not found")

# ── build seed→episode maps for cross refs ─────────────────────────────────────
def seed_map(eps_dict):
    """seed → list of steps"""
    m = {}
    for ep_num, steps in eps_dict.items():
        if steps:
            seed = steps[0]["seed"]
            m[seed] = steps
    return m

cross_seed = {label: seed_map(eps) for label, eps in cross.items()}

# ── identify successes ─────────────────────────────────────────────────────────
successful = {}   # ep_num → steps
failed     = {}

for ep_num, steps in main_eps.items():
    ss = success_step(steps)
    if ss is not None:
        successful[ep_num] = steps
    else:
        failed[ep_num] = steps

print(f"Successful episodes: {sorted(successful.keys())}")
print(f"Failed episodes:     {sorted(failed.keys())}")

# ── section 1: success summary table ──────────────────────────────────────────
def fmt_cross(steps_list, label):
    if steps_list is None:
        return "N/A (seed not in arm)"
    ss = success_step(steps_list)
    fd = first_dist(steps_list)
    md = min_dist(steps_list)
    if ss:
        return f"SUCCESS step {ss} (start {fd:.1f}mm, min {md:.1f}mm)"
    return f"FAIL (start {fd:.1f}mm, min {md:.1f}mm)"


SEC1_ROWS = []
for ep_num in sorted(successful.keys()):
    steps = successful[ep_num]
    seed  = steps[0]["seed"]
    fd    = first_dist(steps)
    ss    = success_step(steps)
    fin   = steps[ss - 1]["tip_target_dist"]  # dist at terminal step

    row = {
        "ep":    ep_num,
        "seed":  seed,
        "start_dist": fd,
        "success_step": ss,
        "final_dist": fin,
        "v4_arm_a":       fmt_cross(cross_seed["v4_arm_a"].get(seed),       "v4_arm_a"),
        "arm_a_topology": fmt_cross(cross_seed["arm_a_topology"].get(seed), "arm_a_topology"),
        "arm_a_budget":   fmt_cross(cross_seed["arm_a_budget"].get(seed),   "arm_a_budget"),
    }
    SEC1_ROWS.append(row)

# ── section 2+3: full trajectory tables with annotations ──────────────────────
def rotation_intent(r):
    rot = r.get("parsed_action", {}).get("rotation", 0.0) or 0.0
    if rot > 0.01:
        return "rotate_cw"
    elif rot < -0.01:
        return "rotate_ccw"
    return ""

def episode_table(steps):
    lines = []
    lines.append("| St | Intent | T(mm) | R(°) | dist(mm) | Δ(mm) | Tip | Target | Safety |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in steps:
        pa    = s.get("parsed_action") or {}
        t     = pa.get("translation", 0.0) or 0.0
        r     = pa.get("rotation", 0.0) or 0.0
        d     = s["tip_target_dist"]
        delta = s.get("dist_delta", 0.0) or 0.0
        intent = s.get("intended_direction", "?") or "?"
        tip  = trunc(s.get("tip_location_statement",""), 70)
        tgt  = trunc(s.get("target_location_statement",""), 70)
        saf  = trunc(s.get("safety_rationale",""), 70)
        term_flag = " **[TARGET]**" if (s.get("terminal") and not s.get("truncation")) else ""
        rot_flag  = " **[ROT]**" if abs(r) > 0.01 else ""
        lines.append(
            f"| {s['step']} | {intent}{rot_flag} | {t:+.0f} | {r:+.2f} | "
            f"{d:.1f} | {delta:+.2f}{term_flag} | {tip} | {tgt} | {saf} |"
        )
    return "\n".join(lines)


def annotate_episode(steps, ep_num):
    """Return annotation text for an episode."""
    lines = []

    # rotation steps
    rot_steps = [s for s in steps if is_rotation(s)]
    if rot_steps:
        lines.append(f"**Rotation steps ({len(rot_steps)} total):**\n")
        for s in rot_steps:
            st = s["step"]
            rot = s.get("parsed_action",{}).get("rotation",0.0)
            d   = s["tip_target_dist"]
            dd  = s.get("dist_delta",0.0)
            # context
            prev2 = [x for x in steps if x["step"] in (st-2, st-1)]
            next2 = [x for x in steps if x["step"] in (st+1, st+2)]
            prev_str = ", ".join(f"s{x['step']}:{x.get('intended_direction','?')}({x['tip_target_dist']:.1f}mm)" for x in prev2)
            next_str = ", ".join(f"s{x['step']}:{x.get('intended_direction','?')}({x['tip_target_dist']:.1f}mm)" for x in next2)
            lines.append(
                f"- **Step {st}**: rotation={rot:+.2f}°, dist={d:.1f}mm, Δ={dd:+.2f}mm\n"
                f"  - Before: {prev_str or 'n/a'}\n"
                f"  - After:  {next_str or 'n/a'}\n"
                f"  - Safety: _{trunc(s.get('safety_rationale',''),120)}_\n"
            )
    else:
        lines.append("**Rotation steps:** None\n")

    # retraction resistance — steps where safety mentions retract/back/return
    # but intent was advance
    resist_steps = []
    retract_keywords = ["retract", "pull back", "withdrawal", "wrong branch"]
    for s in steps:
        saf = (s.get("safety_rationale") or "").lower()
        intent = (s.get("intended_direction") or "").lower()
        if intent == "advance" and any(k in saf for k in retract_keywords):
            resist_steps.append(s)

    if resist_steps:
        lines.append(f"\n**Retraction-resistance steps ({len(resist_steps)} total) — advance chosen despite retract mention in safety:**\n")
        for s in resist_steps:
            lines.append(
                f"- **Step {s['step']}**: dist={s['tip_target_dist']:.1f}mm, Δ={s.get('dist_delta',0.0):+.2f}mm  \n"
                f"  Safety: _{trunc(s.get('safety_rationale',''),120)}_\n"
            )
    else:
        lines.append("\n**Retraction-resistance steps:** None identified (no advance steps with retract-language in safety)\n")

    # decisive moment — longest run of consecutive dist improvement
    dists = [(s["step"], s["tip_target_dist"]) for s in steps]
    best_run = []
    cur_run  = []
    for i in range(1, len(dists)):
        if dists[i][1] < dists[i-1][1]:
            cur_run.append(dists[i])
        else:
            if len(cur_run) > len(best_run):
                best_run = cur_run[:]
            cur_run = []
    if len(cur_run) > len(best_run):
        best_run = cur_run[:]

    if best_run:
        start_s = best_run[0][0] - 1
        end_s   = best_run[-1][0]
        start_d = next(s["tip_target_dist"] for s in steps if s["step"] == start_s) if start_s >= 1 else dists[0][1]
        end_d   = best_run[-1][1]
        gain    = start_d - end_d
        lines.append(
            f"\n**Decisive moment:** Steps {start_s}–{end_s} — {len(best_run)}-step advance streak, "
            f"distance dropped {start_d:.1f}mm → {end_d:.1f}mm (−{gain:.1f}mm)\n"
        )
    return "\n".join(lines)


# ── section 4: failure categorisation ─────────────────────────────────────────
def categorise_failure(steps):
    """
    Returns (category_label, detail_string)
    Categories:
      - monotonic_progress
      - stuck
      - oscillation
      - wrong_branch
      - other
    """
    dists = [s["tip_target_dist"] for s in steps]
    intents = [s.get("intended_direction","") for s in steps]

    # wrong branch: model explicitly names "wrong branch" in safety fields > 2 times
    safety_texts = " ".join((s.get("safety_rationale") or "") for s in steps).lower()
    wrong_branch_count = safety_texts.count("wrong branch")

    # check for terminal truncation (ran out of steps)
    truncated = any(s.get("truncation") for s in steps)

    # monotonic progress: final 10 steps all decreasing dist
    if len(dists) >= 10:
        last10 = dists[-10:]
        last10_mono = all(last10[i] <= last10[i-1] for i in range(1, len(last10)))
    else:
        last10_mono = False

    # net progress (start to end)
    net_progress = dists[0] - dists[-1]

    # stuck: 5+ consecutive steps with |delta| < 2mm
    max_plateau = 0
    cur_plateau  = 0
    for i in range(1, len(dists)):
        if abs(dists[i] - dists[i-1]) < 2.0:
            cur_plateau += 1
            max_plateau = max(max_plateau, cur_plateau)
        else:
            cur_plateau = 0

    # oscillation: reversals (sign change in 3-step window)
    sign_changes = 0
    for i in range(1, len(dists) - 1):
        d0 = dists[i-1]; d1 = dists[i]; d2 = dists[i+1]
        if (d1 - d0) * (d2 - d1) < 0:
            sign_changes += 1
    ep_len = len(dists)
    osc_rate = sign_changes / max(ep_len - 2, 1)

    # categorise
    if wrong_branch_count >= 3:
        detail = f"wrong-branch mentions in safety: {wrong_branch_count}; net progress {net_progress:+.1f}mm"
        return "wrong_branch", detail

    if last10_mono and net_progress > 20 and truncated:
        detail = f"net progress {net_progress:+.1f}mm; last 10 steps monotonically improving; truncated at step {steps[-1]['step']}"
        return "monotonic_progress", detail

    if max_plateau >= 5:
        plateau_detail = f"max plateau run {max_plateau} steps; net progress {net_progress:+.1f}mm"
        if osc_rate > 0.5:
            plateau_detail += f"; osc rate {osc_rate:.2f}"
        return "stuck", plateau_detail

    if osc_rate > 0.55:
        detail = f"oscillation rate {osc_rate:.2f} ({sign_changes} reversals/{ep_len} steps); net progress {net_progress:+.1f}mm"
        return "oscillation", detail

    # default
    detail = f"net progress {net_progress:+.1f}mm, osc rate {osc_rate:.2f}, max plateau {max_plateau}"
    return "other", detail


# ── section 5: rotation effect in failed episodes ─────────────────────────────
def rotation_effect(steps):
    """
    For each rotation step in the episode, compute:
      - mean dist delta in 3 steps BEFORE rotation
      - mean dist delta in 3 steps AFTER rotation
    Returns list of dicts.
    """
    results = []
    step_idx = {s["step"]: i for i, s in enumerate(steps)}
    for s in steps:
        if not is_rotation(s):
            continue
        i = step_idx[s["step"]]
        before = [steps[i-k]["tip_target_dist"] for k in range(1, 4) if i-k >= 0]
        after  = [steps[i+k]["tip_target_dist"] for k in range(1, 4) if i+k < len(steps)]
        # delta = improvement (negative dist = progress)
        pre_delta  = (before[0] - before[-1]) / len(before) if len(before) > 1 else 0.0
        post_delta = (after[0]  - after[-1])  / len(after)  if len(after) > 1  else 0.0
        results.append({
            "ep":         s["episode"],
            "step":       s["step"],
            "rotation":   s.get("parsed_action",{}).get("rotation",0.0),
            "dist_at":    s["tip_target_dist"],
            "pre_delta":  pre_delta,   # >0 = was progressing before
            "post_delta": post_delta,  # >0 = progressed after
        })
    return results


# ════════════════════════════════════════════════════════════════════════════════
#  BUILD THE MARKDOWN REPORT
# ════════════════════════════════════════════════════════════════════════════════

md = []

md.append("# Full Intervention Run — Success Analysis")
md.append(f"\n**Run:** `{RUN_DIR}`  \n**Arm:** `arm_full_intervention`  ")
md.append(f"**Config:** topology primer + retraction budget (3/ep) + rotation enabled  ")
md.append(f"**Model:** claude-sonnet-4-6  \n**Result:** 3 / 15 targets reached\n")

# ────────────────────────────────────────────────────────────────────────────────
md.append("---\n")
md.append("## 1. Successful Episodes — Summary\n")
md.append("| Ep | Seed | Start dist | Success step | Final dist | v4 Arm A (same seed) | Arm A + Topology | Arm A + Budget |")
md.append("|---|---|---|---|---|---|---|---|")
for row in SEC1_ROWS:
    md.append(
        f"| {row['ep']} | {row['seed']} | {row['start_dist']:.1f}mm | step {row['success_step']} | "
        f"{row['final_dist']:.1f}mm | {row['v4_arm_a']} | {row['arm_a_topology']} | {row['arm_a_budget']} |"
    )

# ────────────────────────────────────────────────────────────────────────────────
md.append("\n---\n")
md.append("## 2+3. Full Trajectories and Annotations — Successful Episodes\n")

for ep_num in sorted(successful.keys()):
    steps = successful[ep_num]
    seed  = steps[0]["seed"]
    ss    = success_step(steps)
    fd    = first_dist(steps)

    md.append(f"### Episode {ep_num} (seed={seed})\n")
    md.append(f"**Start dist:** {fd:.1f}mm | **Target reached at step:** {ss} | **Steps total:** {len(steps)}\n")

    # trajectory table
    md.append(episode_table(steps))
    md.append("")

    # annotations
    md.append("#### Annotations\n")
    md.append(annotate_episode(steps, ep_num))
    md.append("\n---\n")


# ────────────────────────────────────────────────────────────────────────────────
md.append("## 4. Failed Episode Failure Modes\n")

category_counts = defaultdict(int)
category_detail = defaultdict(list)  # category -> list of (ep, detail)

for ep_num in sorted(failed.keys()):
    steps = failed[ep_num]
    seed  = steps[0]["seed"]
    cat, detail = categorise_failure(steps)
    category_counts[cat] += 1
    category_detail[cat].append((ep_num, seed, detail))

md.append("### Counts\n")
md.append("| Category | Count |")
md.append("|---|---|")
for cat in ["monotonic_progress", "stuck", "oscillation", "wrong_branch", "other"]:
    n = category_counts.get(cat, 0)
    label = {
        "monotonic_progress": "Ran out of steps (monotonic progress)",
        "stuck":              "Got stuck (plateau ≥5 steps)",
        "oscillation":        "Oscillated (no net progress)",
        "wrong_branch":       "Wrong branch (couldn't recover)",
        "other":              "Other",
    }[cat]
    md.append(f"| {label} | {n} |")

md.append("\n### Per-episode breakdown\n")
md.append("| Ep | Seed | Category | Start dist | Min dist | Final dist | Detail |")
md.append("|---|---|---|---|---|---|---|")
for ep_num in sorted(failed.keys()):
    steps  = failed[ep_num]
    seed   = steps[0]["seed"]
    cat, detail = categorise_failure(steps)
    fd  = first_dist(steps)
    md_ = min_dist(steps)
    fin = steps[-1]["tip_target_dist"]
    md.append(f"| {ep_num} | {seed} | {cat} | {fd:.1f}mm | {md_:.1f}mm | {fin:.1f}mm | {detail} |")

# ────────────────────────────────────────────────────────────────────────────────
md.append("\n---\n")
md.append("## 5. Rotation Effect in Failed Episodes\n")

# Collect all rotation events across failed episodes
all_rot_events = []
failed_rot_total = 0
for ep_num in sorted(failed.keys()):
    steps = failed[ep_num]
    events = rotation_effect(steps)
    failed_rot_total += len(events)
    all_rot_events.extend(events)

# In successful episodes
succ_rot_events = []
for ep_num in sorted(successful.keys()):
    steps = successful[ep_num]
    events = rotation_effect(steps)
    succ_rot_events.extend(events)

total_rot = failed_rot_total + len(succ_rot_events)

md.append(f"**Total rotation steps across all 15 episodes:** {total_rot}  ")
md.append(f"**In successful episodes ({len(successful)}):** {len(succ_rot_events)} rotation steps  ")
md.append(f"**In failed episodes ({len(failed)}):** {failed_rot_total} rotation steps\n")

if all_rot_events:
    helped   = sum(1 for e in all_rot_events if e["post_delta"] > e["pre_delta"])
    neutral  = sum(1 for e in all_rot_events if abs(e["post_delta"] - e["pre_delta"]) <= 0.5)
    hindered = sum(1 for e in all_rot_events if e["post_delta"] < e["pre_delta"] - 0.5)

    md.append(f"**Assessment (3-step pre/post window, failed episodes only):**\n")
    md.append(f"- Rotation followed by better 3-step progress than before: **{helped} / {failed_rot_total}**")
    md.append(f"- Neutral (< 0.5mm/step difference): **{neutral} / {failed_rot_total}**")
    md.append(f"- Rotation followed by worse progress than before: **{hindered} / {failed_rot_total}**")

    md.append("\n#### All rotation events in failed episodes\n")
    md.append("| Ep | Step | Rotation(°) | dist_at(mm) | pre-Δ(mm/step) | post-Δ(mm/step) | Effect |")
    md.append("|---|---|---|---|---|---|---|")
    for e in all_rot_events:
        effect = "helped" if e["post_delta"] > e["pre_delta"] + 0.5 else ("hindered" if e["post_delta"] < e["pre_delta"] - 0.5 else "neutral")
        md.append(
            f"| {e['ep']} | {e['step']} | {e['rotation']:+.2f} | {e['dist_at']:.1f} | "
            f"{e['pre_delta']:+.2f} | {e['post_delta']:+.2f} | {effect} |"
        )
else:
    md.append("_No rotation steps found in failed episodes._\n")

# ────────────────────────────────────────────────────────────────────────────────
md.append("\n---\n")
md.append("## 6. Cross-Reference: Same Seeds Across Arms\n")
md.append("For all 15 seeds, how did each arm perform?\n")
md.append("| Ep | Seed | Full Intervention | v4 Arm A | Arm A + Topology | Arm A + Budget |")
md.append("|---|---|---|---|---|---|")

for ep_num in sorted(main_eps.keys()):
    steps = main_eps[ep_num]
    seed  = steps[0]["seed"]
    ss    = success_step(steps)
    fd    = first_dist(steps)
    fin   = steps[-1]["tip_target_dist"]
    fi_str = f"{'SUCCESS step '+str(ss) if ss else 'FAIL'} (start {fd:.1f}mm, end {fin:.1f}mm)"

    row_cells = [fi_str]
    for label in ["v4_arm_a", "arm_a_topology", "arm_a_budget"]:
        seed_steps = cross_seed[label].get(seed)
        row_cells.append(fmt_cross(seed_steps, label))

    md.append(f"| {ep_num} | {seed} | {row_cells[0]} | {row_cells[1]} | {row_cells[2]} | {row_cells[3]} |")

# ────────────────────────────────────────────────────────────────────────────────
md.append("\n---\n")
md.append("## 7. Key Observations\n")
md.append(
    "> Auto-generated section — edit manually to add interpretation.\n\n"
    "- **What the 3 successes have in common:** (fill after reading trajectories)\n"
    "- **What the 12 failures have in common:** (fill after reading categories)\n"
    "- **Rotation signal:** (fill from Section 5)\n"
    "- **Retraction budget utilisation:** (fill — did budget enforcement block any episode?)\n"
    "- **Recommended next experiment:** (fill)\n"
)

# ── write output ───────────────────────────────────────────────────────────────
report = "\n".join(md)

for outpath in [OUT_MD, OUT_MD2]:
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(report, encoding="utf-8")
    print(f"Written: {outpath}  ({len(report):,} chars)")

print("\nDone.")
