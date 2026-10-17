import json, numpy as np, sys
from pathlib import Path

def load_trace(p):
    if not Path(p).exists(): return []
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]

def collect_arm(mode):
    RUNS = Path('D:/steve/pilot/runs')
    episodes = {}

    if mode == 'wire_only':
        for r in load_trace(RUNS/'2026-06-29_17-34-17/arm_coronary_wire_only/trace.jsonl'):
            episodes.setdefault(r['episode'], []).append(r)
        for r in load_trace(RUNS/'2026-06-29_wire_only_cont/arm_coronary_wire_only/trace.jsonl'):
            episodes.setdefault(5, []).append(r)
        for d in sorted(RUNS.glob('batch_wire_only_ep*')):
            ep_num = int(d.name.split('ep')[1])
            for r in load_trace(d/'arm_coronary_wire_only/trace.jsonl'):
                episodes.setdefault(ep_num, []).append(r)
    else:
        for r in load_trace(RUNS/'2026-06-29_17-59-24/arm_coronary_overlay/trace.jsonl'):
            episodes.setdefault(r['episode'], []).append(r)
        for d in sorted(RUNS.glob('batch_overlay_ep*')):
            ep_num = int(d.name.split('ep')[1])
            for r in load_trace(d/'arm_coronary_overlay/trace.jsonl'):
                episodes.setdefault(ep_num, []).append(r)

    return episodes

def classify(steps):
    min_dist = min(s.get('tip_target_dist', 999) for s in steps)
    success_step = None
    for s in steps:
        if s.get('terminal') and s.get('tip_target_dist', 999) < 5:
            success_step = s['step']
            break
    last_branch = steps[-1].get('tip_branch_obs', '?')

    # Primary branch: outcome-based
    # Success => must be LAD (target is mid-LAD). Failure => use final tip branch.
    if success_step is not None:
        primary_branch = 'lad'
    elif 'lcx' in (last_branch or ''):
        primary_branch = 'lcx'
    else:
        primary_branch = last_branch  # 'lad' or 'left_main' (stalled)

    # First-transition (kept for supplemental)
    prev = 'left_main'
    bif_branch = None; bif_step = None
    for s in steps:
        b = s.get('tip_branch_obs', '')
        if prev == 'left_main' and b not in ('left_main', ''):
            bif_branch = b; bif_step = s['step']; break
        prev = b

    return {
        'primary_branch': primary_branch,
        'bif_branch': bif_branch, 'bif_step': bif_step,
        'min_dist': min_dist, 'success_step': success_step,
        'success': success_step is not None,
        'max_step': max(s['step'] for s in steps),
        'last_branch': last_branch,
        'api_errors': sum(1 for s in steps if not s.get('api_ok', True)),
        'parse_fails': sum(1 for s in steps if not s.get('parse_ok', True)),
    }

def lm_rot_per_mm(steps):
    lm = [s for s in steps if s.get('tip_branch_obs') == 'left_main']
    if len(lm) < 2: return None
    tips = [np.array(s['gt_tip_obs']) for s in lm]
    path = sum(np.linalg.norm(tips[i+1]-tips[i]) for i in range(len(tips)-1))
    rots = sum(1 for s in lm if s.get('parsed_action',{}).get('rotation', 0.0) != 0.0)
    return rots / path if path > 0 else 0.0

print('=' * 72)
print('FINDING 2 REPORT  wire_only vs overlay_normal  120 steps  Sonnet 512')
print('=' * 72)

arm_results = {}

for mode in ['wire_only', 'overlay']:
    eps = collect_arm(mode)
    label = 'overlay_normal' if mode == 'overlay' else 'wire_only'
    res = {ep: classify(eps[ep]) for ep in eps}
    arm_results[label] = (eps, res)

    lad = {ep: r for ep, r in res.items() if r['primary_branch'] == 'lad'}
    lcx = {ep: r for ep, r in res.items() if r['primary_branch'] == 'lcx'}
    unk = {ep: r for ep, r in res.items() if ep not in lad and ep not in lcx}
    succ_all = [ep for ep, r in res.items() if r['success']]
    succ_lad = [ep for ep in lad if res[ep]['success']]
    fail_lad = [ep for ep in lad if not res[ep]['success']]
    steps_succ = [res[ep]['success_step'] for ep in succ_all]
    # LM rot/mm on LAD-only episodes (apples-to-apples)
    rms_lad = [v for ep in lad for v in [lm_rot_per_mm(eps[ep])] if v is not None]
    rms_all = [v for ep in eps for v in [lm_rot_per_mm(eps[ep])] if v is not None]

    missing = [i for i in range(1, 16) if i not in res]
    tech_fail = [ep for ep, r in res.items() if r['api_errors'] > 10 or r['parse_fails'] > 10]

    print(f'\n--- {label.upper()} ---')
    if missing: print(f'  MISSING episodes: {missing}')
    if tech_fail: print(f'  TECH-FAIL episodes (>10 errors): {tech_fail}')

    print(f'  BRANCH SELECTION  (classification = final/outcome branch)')
    print(f'    LAD (correct) : {len(lad)}/15  eps={sorted(lad)}')
    print(f'    LCX (wrong)   : {len(lcx)}/15  eps={sorted(lcx)}')
    if unk: print(f'    Unknown/stuck  : {len(unk)}/15  eps={sorted(unk)}')
    print(f'    Wrong-branch rate: {len(lcx)/15*100:.0f}%')

    print(f'  SUCCESS RATE')
    print(f'    Overall (all 15)     : {len(succ_all)}/15  ({len(succ_all)/15*100:.0f}%)')
    print(f'    Among LAD eps only   : {len(succ_lad)}/{len(lad)}  ({len(succ_lad)/max(len(lad),1)*100:.0f}%)')
    if fail_lad:
        mdists = [f"{res[ep]['min_dist']:.1f}" for ep in fail_lad]
        print(f'    LAD failures        : eps={fail_lad}  min_d={mdists}mm')
    if steps_succ:
        print(f'    Steps-to-target     : mean={np.mean(steps_succ):.1f}  '
              f'med={np.median(steps_succ):.0f}  range=[{min(steps_succ)},{max(steps_succ)}]')
        for ep in sorted(succ_all):
            print(f'      ep{ep:02d}: step {res[ep]["success_step"]:3d}  '
                  f'min_d={res[ep]["min_dist"]:.1f}mm')

    print(f'  LM rot/mm (LAD eps only)  mean={np.mean(rms_lad) if rms_lad else float("nan"):.4f}  n={len(rms_lad)}')
    print(f'  LM rot/mm (all eps)       mean={np.mean(rms_all) if rms_all else float("nan"):.4f}  n={len(rms_all)}')

print()
print('=' * 72)
print('CROSS-ARM SUMMARY TABLE')
print('=' * 72)

summary = {}
for label, (eps, res) in arm_results.items():
    lad = {ep: r for ep, r in res.items() if r['primary_branch'] == 'lad'}
    lcx = {ep: r for ep, r in res.items() if r['primary_branch'] == 'lcx'}
    succ_all = [ep for ep, r in res.items() if r['success']]
    succ_lad = [ep for ep in lad if res[ep]['success']]
    steps_succ = [res[ep]['success_step'] for ep in succ_all]
    rms_lad = [v for ep in lad for v in [lm_rot_per_mm(eps[ep])] if v is not None]
    summary[label] = {
        'n_lad': len(lad), 'n_lcx': len(lcx),
        'n_succ': len(succ_all), 'n_lad_succ': len(succ_lad),
        'mean_steps': np.mean(steps_succ) if steps_succ else float('nan'),
        'lm_rotmm_lad': np.mean(rms_lad) if rms_lad else float('nan'),
        'lad_set': set(lad), 'succ_set': set(succ_all),
    }

wo = summary['wire_only']
ov = summary['overlay_normal']
W = 14

def row(label, wv, ov_v):
    print(f'  {label:<38} {wv:>{W}} {ov_v:>{W}}')

print(f'\n  {"Metric":<38} {"wire_only":>{W}} {"overlay_normal":>{W}}')
print(f'  {"-"*38} {"-"*W} {"-"*W}')
row("LAD (correct branch)",
    f"{wo['n_lad']}/15", f"{ov['n_lad']}/15")
row("LCX (wrong branch)",
    f"{wo['n_lcx']}/15", f"{ov['n_lcx']}/15")
row("Wrong-branch rate",
    f"{wo['n_lcx']/15*100:.0f}%", f"{ov['n_lcx']/15*100:.0f}%")
row("Overall success rate",
    f"{wo['n_succ']}/15 ({wo['n_succ']/15*100:.0f}%)",
    f"{ov['n_succ']}/15 ({ov['n_succ']/15*100:.0f}%)")
n_lad_w = max(wo['n_lad'], 1); n_lad_o = max(ov['n_lad'], 1)
row("Success among LAD eps",
    f"{wo['n_lad_succ']}/{wo['n_lad']} ({wo['n_lad_succ']/n_lad_w*100:.0f}%)",
    f"{ov['n_lad_succ']}/{ov['n_lad']} ({ov['n_lad_succ']/n_lad_o*100:.0f}%)")
row("Mean steps-to-target",
    f"{wo['mean_steps']:.1f}", f"{ov['mean_steps']:.1f}")
row("LM rot/mm (LAD eps, Finding 1 recheck)",
    f"{wo['lm_rotmm_lad']:.4f}", f"{ov['lm_rotmm_lad']:.4f}")

# Branch-matched: same episode went LAD in BOTH arms
shared_lad = wo['lad_set'] & ov['lad_set']
wo_eps_data, wo_res = arm_results['wire_only']
ov_eps_data, ov_res = arm_results['overlay_normal']
wo_shared_succ = [ep for ep in shared_lad if wo_res[ep]['success']]
ov_shared_succ = [ep for ep in shared_lad if ov_res[ep]['success']]
wo_shared_steps = [wo_res[ep]['success_step'] for ep in wo_shared_succ]
ov_shared_steps = [ov_res[ep]['success_step'] for ep in ov_shared_succ]

wo_ms = np.mean(wo_shared_steps) if wo_shared_steps else float('nan')
ov_ms = np.mean(ov_shared_steps) if ov_shared_steps else float('nan')
print(f'\n  Branch-matched set (both arms went LAD): n={len(shared_lad)} eps={sorted(shared_lad)}')
print(f'    wire_only success in matched set: {len(wo_shared_succ)}/{len(shared_lad)}  mean={wo_ms:.1f} steps')
print(f'    overlay   success in matched set: {len(ov_shared_succ)}/{len(shared_lad)}  mean={ov_ms:.1f} steps')

# per-ep branch table
print(f'\n  Per-episode branch selection:')
print(f'  {"ep":<6} {"wire_only":>12} {"overlay":>12}')
print(f'  {"-"*6} {"-"*12} {"-"*12}')
for ep in range(1, 16):
    def ep_label(rdict, ep):
        r = rdict.get(ep)
        if r is None: return 'MISSING'
        pb = r['primary_branch']
        if r['success']: return 'LAD-S'
        if pb == 'lad': return 'LAD-F'
        if 'lcx' in (pb or ''): return 'LCX'
        return pb or '?'
    wo_out = ep_label(wo_res, ep)
    ov_out = ep_label(ov_res, ep)
    flag = '<<' if wo_out != ov_out else ''
    print(f'  ep{ep:02d}   {wo_out:>12} {ov_out:>12}  {flag}')
