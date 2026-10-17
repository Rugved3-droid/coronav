"""
D:\\steve\\pilot\\analysis\\analyze_coronary.py
Analyzes a coronary VLM operator run (from run_coronary.py) and writes
analysis.md into the run directory.

Ported from analyze_success.py (arch) with these changes:
  - Accepts run directory as CLI argument (not hardcoded)
  - Reads all arm_coronary_* subdirs found in the run dir
  - Cross-reference removed (no prior coronary arms yet)
  - Failure categorisation: adds lm_bend_confusion category
    (model retracts during early LM phase when d_tgt is still rising)
  - Section 6 (cross-arm): replaced with mode comparison (wire_only vs overlay vs contrast)
  - Perception thresholds: 5 / 15 / 50mm (coronary scale)

Usage:
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\analysis\\analyze_coronary.py
        --run D:\\steve\\pilot\\runs\\2026-06-28_HH-MM-SS

    Or for a single arm trace:
        --trace D:\\steve\\pilot\\runs\\TIMESTAMP\\arm_coronary_wire_only\\trace.jsonl
"""

import argparse
import json
import math
from pathlib import Path
from collections import defaultdict

# ── helpers (identical to analyze_success.py) ─────────────────────────────────

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


def first_dist(steps):  return steps[0]["tip_target_dist"] if steps else None
def min_dist(steps):    return min(s["tip_target_dist"] for s in steps) if steps else None
def final_dist(steps):  return steps[-1]["tip_target_dist"] if steps else None


def success_step(steps):
    for s in steps:
        if s.get("terminal") and not s.get("truncation"):
            return s["step"]
    return None


def is_rotation(s):
    r = s.get("parsed_action", {}).get("rotation", 0.0)
    return r is not None and abs(r) > 0.01


def trunc(txt, n=80):
    if txt is None: return ""
    txt = txt.replace("\n", " ").replace("|", "/")
    return txt[:n] + "…" if len(txt) > n else txt


# ── Episode table ──────────────────────────────────────────────────────────────

def episode_table(steps):
    lines = [
        "| St | Intent | T(mm) | R(°) | dist(mm) | Δ(mm) | trend | gate | Tip | Target |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in steps:
        pa     = s.get("parsed_action") or {}
        t      = pa.get("translation", 0.0) or 0.0
        r      = pa.get("rotation", 0.0) or 0.0
        d      = s["tip_target_dist"]
        delta  = s.get("dist_delta", 0.0) or 0.0
        intent = s.get("intended_direction", "?") or "?"
        trend  = s.get("dist_trend", "") or ""
        gate   = "Y" if s.get("gate_active") else ""
        tip    = trunc(s.get("tip_location_statement", ""), 60)
        tgt    = trunc(s.get("target_location_statement", ""), 60)
        tflag  = " **[TARGET]**" if (s.get("terminal") and not s.get("truncation")) else ""
        rflag  = " **[ROT]**" if abs(r) > 0.01 else ""
        bflag  = " **[BUDGET]**" if s.get("budget_enforced") else ""
        gflag  = " **[GATE]**" if s.get("gate_suppressed_rotation") else ""
        lines.append(
            f"| {s['step']} | {intent}{rflag}{bflag}{gflag} | {t:+.0f} | {r:+.2f} | "
            f"{d:.1f} | {delta:+.2f}{tflag} | {trend} | {gate} | {tip} | {tgt} |"
        )
    return "\n".join(lines)


def annotate_episode(steps):
    lines = []

    # Rotation steps with context
    rot_steps = [s for s in steps if is_rotation(s)]
    if rot_steps:
        lines.append(f"**Rotation steps ({len(rot_steps)} total):**\n")
        for s in rot_steps:
            st  = s["step"]; rot = s.get("parsed_action", {}).get("rotation", 0.0)
            d   = s["tip_target_dist"]; dd = s.get("dist_delta", 0.0)
            prev2 = [x for x in steps if x["step"] in (st-2, st-1)]
            next2 = [x for x in steps if x["step"] in (st+1, st+2)]
            pstr = ", ".join(f"s{x['step']}:{x.get('intended_direction','?')}({x['tip_target_dist']:.1f}mm)"
                             for x in prev2)
            nstr = ", ".join(f"s{x['step']}:{x.get('intended_direction','?')}({x['tip_target_dist']:.1f}mm)"
                             for x in next2)
            lines.append(
                f"- **Step {st}**: rotation={rot:+.2f}, dist={d:.1f}mm, Δ={dd:+.2f}mm\n"
                f"  - Before: {pstr or 'n/a'}\n"
                f"  - After:  {nstr or 'n/a'}\n"
                f"  - Safety: _{trunc(s.get('safety_rationale',''), 120)}_\n"
            )
    else:
        lines.append("**Rotation steps:** None\n")

    # LM-bend confusion: retraction while tip was still in left_main (proximal to bifurcation)
    lm_retracts = [s for s in steps
                   if s.get("parsed_action", {}).get("translation", 0.0) < 0
                   and s.get("tip_branch_obs") == "left_main"]
    if lm_retracts:
        lines.append(f"\n**LM-bend confusion retractions ({len(lm_retracts)}) — "
                     f"retracted while tip was in left_main (proximal to bifurcation):**\n")
        for s in lm_retracts:
            lines.append(
                f"- Step {s['step']}: branch={s.get('tip_branch_obs','?')}  "
                f"dist={s['tip_target_dist']:.1f}mm  "
                f"safety: _{trunc(s.get('safety_rationale',''), 100)}_\n"
            )
    else:
        lines.append("\n**LM-bend confusion retractions:** None\n")

    # Decisive moment — longest consecutive improvement run
    dists    = [(s["step"], s["tip_target_dist"]) for s in steps]
    best_run = []; cur_run = []
    for i in range(1, len(dists)):
        if dists[i][1] < dists[i-1][1]:
            cur_run.append(dists[i])
        else:
            if len(cur_run) > len(best_run): best_run = cur_run[:]
            cur_run = []
    if len(cur_run) > len(best_run): best_run = cur_run[:]
    if best_run:
        s0 = best_run[0][0] - 1
        d0 = next((s["tip_target_dist"] for s in steps if s["step"] == s0), dists[0][1])
        d1 = best_run[-1][1]
        lines.append(
            f"\n**Decisive moment:** Steps {s0}–{best_run[-1][0]} — "
            f"{len(best_run)}-step advance streak, {d0:.1f}mm → {d1:.1f}mm "
            f"(−{d0-d1:.1f}mm)\n"
        )
    return "\n".join(lines)


# ── Failure categorisation (coronary-specific additions) ──────────────────────

def categorise_failure(steps):
    """
    Returns (category_label, detail_string).

    Categories (in priority order):
      lm_bend_confusion : model retracted >= 2 times while dist > 75mm
                          (retracting during LM traversal when distance was rising)
      wrong_branch      : model names LCX/wrong branch >= 2 times OR retracts
                          AFTER dist has been < 75mm (bifurcation passed)
      monotonic_progress: truncated with last 10 steps all improving
      stuck             : plateau >= 5 steps
      oscillation       : oscillation rate > 0.55
      other
    """
    dists   = [s["tip_target_dist"] for s in steps]
    safety  = " ".join((s.get("safety_rationale") or "") for s in steps).lower()

    truncated   = any(s.get("truncation") for s in steps)
    net_progress = dists[0] - dists[-1]

    # LM-bend confusion: retraction while tip is anatomically in the left_main
    # (proximal to the LM-LAD/LCX bifurcation, independent of absolute distance).
    # Requires tip_branch_obs field logged by run_coronary.py v2+.
    lm_ret = [s for s in steps
               if (s.get("parsed_action", {}).get("translation", 0.0) < 0)
               and s.get("tip_branch_obs") == "left_main"]

    # Wrong branch: explicit LCX/wrong-branch language OR retraction after passing
    # the bifurcation (tip is no longer in left_main = wire reached LAD/LCX choice).
    lcx_count   = (safety.count("lcx") + safety.count("wrong branch")
                   + safety.count("circumflex"))
    post_lm_ret = [s for s in steps
                   if (s.get("parsed_action", {}).get("translation", 0.0) < 0)
                   and s.get("tip_branch_obs") not in (None, "left_main")]

    # Last-10 monotone
    last10_mono = False
    if len(dists) >= 10:
        last10 = dists[-10:]
        last10_mono = all(last10[i] <= last10[i-1] for i in range(1, len(last10)))

    # Stuck (plateau)
    max_plateau = 0; cur_plateau = 0
    for i in range(1, len(dists)):
        if abs(dists[i] - dists[i-1]) < 2.0:
            cur_plateau += 1; max_plateau = max(max_plateau, cur_plateau)
        else:
            cur_plateau = 0

    # Oscillation
    sign_changes = 0
    for i in range(1, len(dists) - 1):
        if (dists[i] - dists[i-1]) * (dists[i+1] - dists[i]) < 0:
            sign_changes += 1
    osc_rate = sign_changes / max(len(dists) - 2, 1)

    if len(lm_ret) >= 2:
        return ("lm_bend_confusion",
                f"{len(lm_ret)} retractions in left_main; net progress {net_progress:+.1f}mm")
    if lcx_count >= 2 or len(post_lm_ret) >= 1:
        return ("wrong_branch",
                f"LCX/wrong-branch mentions: {lcx_count}; post-LM retracts: {len(post_lm_ret)}; "
                f"net progress {net_progress:+.1f}mm")
    if last10_mono and net_progress > 20 and truncated:
        return ("monotonic_progress",
                f"net progress {net_progress:+.1f}mm; last 10 steps monotonically improving; "
                f"truncated at step {steps[-1]['step']}")
    if max_plateau >= 5:
        return ("stuck",
                f"max plateau {max_plateau} steps; net progress {net_progress:+.1f}mm")
    if osc_rate > 0.55:
        return ("oscillation",
                f"osc rate {osc_rate:.2f} ({sign_changes} reversals/{len(dists)} steps); "
                f"net progress {net_progress:+.1f}mm")
    return ("other",
            f"net progress {net_progress:+.1f}mm, osc {osc_rate:.2f}, plateau {max_plateau}")


# ── Rotation effect ────────────────────────────────────────────────────────────

def rotation_effect(steps):
    results = []
    step_idx = {s["step"]: i for i, s in enumerate(steps)}
    for s in steps:
        if not is_rotation(s): continue
        i      = step_idx[s["step"]]
        before = [steps[i-k]["tip_target_dist"] for k in range(1, 4) if i-k >= 0]
        after  = [steps[i+k]["tip_target_dist"] for k in range(1, 4) if i+k < len(steps)]
        pre_d  = (before[0] - before[-1]) / len(before) if len(before) > 1 else 0.0
        post_d = (after[0]  - after[-1])  / len(after)  if len(after)  > 1 else 0.0
        results.append({
            "ep": s["episode"], "step": s["step"],
            "rotation": s.get("parsed_action", {}).get("rotation", 0.0),
            "dist_at": s["tip_target_dist"],
            "pre_delta": pre_d, "post_delta": post_d,
        })
    return results


# ── Build report for one arm ───────────────────────────────────────────────────

def build_arm_report(arm_label: str, rows: list) -> list:
    eps        = group_by_episode(rows)
    mode       = rows[0].get("fluoro_mode", "unknown") if rows else "unknown"
    successful = {k: v for k, v in eps.items() if success_step(v) is not None}
    failed     = {k: v for k, v in eps.items() if success_step(v) is None}
    n_ep       = len(eps)

    md = []
    md.append(f"## Arm: {arm_label}  (mode={mode})\n")
    md.append(f"Episodes: {n_ep} repetitions of a single fixed scenario "
              f"(fixed anatomy/target/start; variance = VLM sampling)  \n")
    md.append(f"Target reached: {len(successful)}/{n_ep}  \n")
    md.append(f"Start dist (ep1): {first_dist(eps[1]):.1f}mm\n" if 1 in eps and eps[1] else "")

    # ── Success table ──────────────────────────────────────────────────────────
    md.append("### Successful episodes\n")
    if successful:
        md.append("| Ep | Seed | Start dist | Success step | Final dist |")
        md.append("|---|---|---|---|---|")
        for ep_num in sorted(successful):
            s = successful[ep_num]; seed = s[0]["seed"]
            md.append(f"| {ep_num} | {seed} | {first_dist(s):.1f}mm | "
                      f"step {success_step(s)} | {final_dist(s):.1f}mm |")
    else:
        md.append("_None_\n")

    # ── Full trajectories ──────────────────────────────────────────────────────
    md.append("\n### Full trajectories — successful episodes\n")
    for ep_num in sorted(successful):
        steps = successful[ep_num]; seed = steps[0]["seed"]
        md.append(f"#### Episode {ep_num} (seed={seed})\n")
        md.append(episode_table(steps))
        md.append("\n#### Annotations\n")
        md.append(annotate_episode(steps))
        md.append("\n---\n")

    # ── Failure categorisation ─────────────────────────────────────────────────
    md.append("### Failed episode failure modes\n")
    cat_counts  = defaultdict(int)
    cat_details = defaultdict(list)
    for ep_num in sorted(failed):
        cat, detail = categorise_failure(failed[ep_num])
        cat_counts[cat] += 1
        cat_details[cat].append((ep_num, failed[ep_num][0]["seed"], detail))

    cat_labels = {
        "lm_bend_confusion": "LM-bend confusion (retracted during LM traversal)",
        "wrong_branch":      "Wrong branch (LCX, couldn't recover)",
        "monotonic_progress":"Ran out of steps (was making progress)",
        "stuck":             "Stuck (plateau ≥5 steps)",
        "oscillation":       "Oscillated (no net progress)",
        "other":             "Other",
    }
    md.append("| Category | Count |")
    md.append("|---|---|")
    for cat, label in cat_labels.items():
        md.append(f"| {label} | {cat_counts.get(cat, 0)} |")

    md.append("\n| Ep | Seed | Category | Start dist | Min dist | Final dist | Detail |")
    md.append("|---|---|---|---|---|---|---|")
    for ep_num in sorted(failed):
        steps = failed[ep_num]; seed = steps[0]["seed"]
        cat, detail = categorise_failure(steps)
        md.append(f"| {ep_num} | {seed} | {cat} | "
                  f"{first_dist(steps):.1f}mm | {min_dist(steps):.1f}mm | "
                  f"{final_dist(steps):.1f}mm | {detail} |")

    # ── Rotation effect ────────────────────────────────────────────────────────
    md.append("\n### Rotation effect — failed episodes\n")
    all_rot = []
    for ep_num in sorted(failed):
        all_rot.extend(rotation_effect(failed[ep_num]))
    if all_rot:
        helped  = sum(1 for e in all_rot if e["post_delta"] > e["pre_delta"] + 0.5)
        neutral = sum(1 for e in all_rot if abs(e["post_delta"] - e["pre_delta"]) <= 0.5)
        hindered= sum(1 for e in all_rot if e["post_delta"] < e["pre_delta"] - 0.5)
        md.append(f"Total rotation steps in failed episodes: {len(all_rot)}  ")
        md.append(f"- Helped (better post-3-step): {helped}  ")
        md.append(f"- Neutral: {neutral}  ")
        md.append(f"- Hindered: {hindered}\n")
        md.append("| Ep | Step | Rotation | dist_at | pre-Δ | post-Δ | Effect |")
        md.append("|---|---|---|---|---|---|---|")
        for e in all_rot:
            eff = ("helped" if e["post_delta"] > e["pre_delta"] + 0.5
                   else "hindered" if e["post_delta"] < e["pre_delta"] - 0.5
                   else "neutral")
            md.append(f"| {e['ep']} | {e['step']} | {e['rotation']:+.2f} | "
                      f"{e['dist_at']:.1f} | {e['pre_delta']:+.2f} | "
                      f"{e['post_delta']:+.2f} | {eff} |")
    else:
        md.append("_No rotation steps in failed episodes._\n")

    return md


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--run",   type=str, help="Run directory (contains arm_coronary_* subdirs)")
    grp.add_argument("--trace", type=str, help="Path to a single trace.jsonl")
    args = parser.parse_args()

    # Collect arm traces
    arms = {}
    if args.run:
        run_dir = Path(args.run)
        for arm_dir in sorted(run_dir.glob("arm_coronary_*")):
            tf = arm_dir / "trace.jsonl"
            if tf.exists():
                arms[arm_dir.name] = load_trace(tf)
                print(f"Loaded {arm_dir.name}: {len(arms[arm_dir.name])} rows")
        out_dir = run_dir
    else:
        tf_path = Path(args.trace)
        arms[tf_path.parent.name] = load_trace(tf_path)
        out_dir = tf_path.parent

    if not arms:
        print("No traces found."); return

    md = [
        "# Coronary VLM Operator — Analysis\n",
        "> **Framing**: Each 'episode' is a repetition of a **single fixed left-coronary",
        "> scenario**. Anatomy (`clipped_left.vtp`), target (mid-LAD, BranchIndex), and",
        "> start (MaxDeviceLength, 0 insertion) are **identical across all episodes**.",
        "> Observed variance reflects **VLM sampling stochasticity**, not anatomical variation.",
        "> Do not interpret n=15 as 15 distinct navigation problems.",
        ">",
        "> The fixed scenario is a **strength for condition comparison**: any performance",
        "> difference between wire\\_only / overlay / contrast is attributable **purely to the",
        "> observation condition**, with zero anatomical confound. The LM-bend illusion",
        "> (d\\_tgt rises +4.3 mm at step 6, confirmed deterministic across 15 seeds) occurs",
        "> at the same anatomical point in every episode; the per-condition illusion failure",
        "> rate is therefore a **within-scenario, same-anatomy comparison** — a clean causal",
        "> claim about whether visual augmentation reduces the illusion.\n",
    ]

    # Per-arm reports
    for arm_label, rows in arms.items():
        md.extend(build_arm_report(arm_label, rows))
        md.append("\n---\n")

    # Cross-arm success rate comparison (if multiple arms)
    if len(arms) > 1:
        md.append("## Cross-mode comparison\n")
        md.append("> Fixed anatomy: condition differences are causally attributable to the "
                  "observation condition only.\n")
        md.append("> **Note on overlay_bright**: post-hoc contrast-control arm (n=5), "
                  "NOT a primary condition. Wire fill=20 restores local tip contrast at the "
                  "bifurcation (58.6→78.5 gray levels) while keeping vessel topology visible. "
                  "Purpose: rule out rendering artifact (Cause A) vs bifurcation-information "
                  "effect (Cause B). Do not compare success rates against n=15 primary arms.\n")
        md.append("| Mode | Reached | Episodes | Success rate | "
                  "LM-bend illusion failures | Mean min-dist | Mean final-dist |")
        md.append("|---|---|---|---|---|---|---|")
        for arm_label, rows in arms.items():
            eps    = group_by_episode(rows)
            succ   = sum(1 for v in eps.values() if success_step(v) is not None)
            n_ep   = len(eps)
            mnd    = [min_dist(v)   for v in eps.values() if min_dist(v) is not None]
            fnd    = [final_dist(v) for v in eps.values() if final_dist(v) is not None]
            avg_mn = sum(mnd)/len(mnd) if mnd else float("nan")
            avg_fn = sum(fnd)/len(fnd) if fnd else float("nan")
            mode   = rows[0].get("fluoro_mode", "?") if rows else "?"
            rate   = f"{100*succ/n_ep:.0f}%" if n_ep else "N/A"
            lm_illu = sum(
                1 for v in eps.values()
                if success_step(v) is None and categorise_failure(v)[0] == "lm_bend_confusion"
            )
            lm_str = f"{lm_illu}/{n_ep - succ} failed" if n_ep - succ > 0 else "0/0"
            md.append(f"| {mode} | {succ} | {n_ep} | {rate} | {lm_str} | "
                      f"{avg_mn:.1f}mm | {avg_fn:.1f}mm |")

    report = "\n".join(md)
    out_path = out_dir / "analysis.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"\nWritten: {out_path}  ({len(report):,} chars)")


if __name__ == "__main__":
    main()
