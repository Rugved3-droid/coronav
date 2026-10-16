import json, numpy as np
from pathlib import Path
from scipy import stats
from scipy.stats import fisher_exact, mannwhitneyu

# ── load traces (same logic as merge_report.py) ─────────────────────────────

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
            success_step = s['step']; break
    last_branch = steps[-1].get('tip_branch_obs', '?')
    if success_step is not None:
        primary_branch = 'lad'
    elif 'lcx' in (last_branch or ''):
        primary_branch = 'lcx'
    else:
        primary_branch = last_branch
    return {'primary_branch': primary_branch, 'min_dist': min_dist,
            'success_step': success_step, 'success': success_step is not None}

def lm_rot_per_mm(steps):
    lm = [s for s in steps if s.get('tip_branch_obs') == 'left_main']
    if len(lm) < 2: return None
    tips = [np.array(s['gt_tip_obs']) for s in lm]
    path = sum(np.linalg.norm(tips[i+1]-tips[i]) for i in range(len(tips)-1))
    rots = sum(1 for s in lm if s.get('parsed_action', {}).get('rotation', 0.0) != 0.0)
    return rots / path if path > 0 else 0.0

# ── collect per-episode data ─────────────────────────────────────────────────

arms = {}
for mode in ['wire_only', 'overlay']:
    eps = collect_arm(mode)
    res = {ep: classify(eps[ep]) for ep in eps}
    lad_eps = [ep for ep, r in res.items() if r['primary_branch'] == 'lad']
    lcx_eps = [ep for ep, r in res.items() if r['primary_branch'] == 'lcx']
    steps_lad = [res[ep]['success_step'] for ep in lad_eps if res[ep]['success']]
    rots_lad  = [v for ep in lad_eps for v in [lm_rot_per_mm(eps[ep])] if v is not None]
    label = 'overlay' if mode == 'overlay' else 'wire_only'
    arms[label] = {
        'n_lad': len(lad_eps), 'n_lcx': len(lcx_eps),
        'steps_lad': sorted(steps_lad), 'rots_lad': rots_lad,
        'lad_eps': lad_eps, 'lcx_eps': lcx_eps,
    }

wo = arms['wire_only']
ov = arms['overlay']

print('=' * 70)
print('STATISTICAL REPORT  wire_only vs overlay_normal  n=15 per arm')
print('=' * 70)

# ── 1. WRONG-BRANCH RATE: Fisher's exact ────────────────────────────────────
print('\n--- TEST 1: Wrong-branch rate (Fisher\'s exact) ---')
print(f'  wire_only : {wo["n_lcx"]}/15 wrong  ({wo["n_lcx"]/15*100:.1f}%)')
print(f'  overlay   : {ov["n_lcx"]}/15 wrong  ({ov["n_lcx"]/15*100:.1f}%)')

# 2x2: [[lad_wo, lcx_wo], [lad_ov, lcx_ov]]
table = np.array([[wo['n_lad'], wo['n_lcx']],
                  [ov['n_lad'], ov['n_lcx']]])
print(f'\n  Contingency table:')
print(f'            LAD   LCX')
print(f'  wire_only  {table[0,0]:2d}    {table[0,1]:2d}')
print(f'  overlay    {table[1,0]:2d}    {table[1,1]:2d}')

odds_ratio, p_fisher = fisher_exact(table, alternative='two-sided')
_, p_fisher_1t = fisher_exact(table, alternative='less')  # wire_only < overlay
print(f'\n  Fisher\'s exact (two-sided): p = {p_fisher:.4f}')
print(f'  Fisher\'s exact (one-sided, wo<ov): p = {p_fisher_1t:.4f}')
print(f'  Odds ratio: {odds_ratio:.3f}  (overlay vs wire_only for LCX)')

# 95% CI on rate difference via Wilson score intervals and propagation
from statsmodels.stats.proportion import proportion_confint, proportions_ztest
ci_wo = proportion_confint(wo['n_lcx'], 15, alpha=0.05, method='wilson')
ci_ov = proportion_confint(ov['n_lcx'], 15, alpha=0.05, method='wilson')
diff_obs = ov['n_lcx']/15 - wo['n_lcx']/15

# Bootstrap CI on rate difference
rng = np.random.default_rng(42)
n_boot = 100000
boot_wo = rng.binomial(15, wo['n_lcx']/15, n_boot) / 15
boot_ov = rng.binomial(15, ov['n_lcx']/15, n_boot) / 15
boot_diff = boot_ov - boot_wo
ci_diff = np.percentile(boot_diff, [2.5, 97.5])

print(f'\n  Observed rate difference: {diff_obs:+.3f} ({diff_obs*100:+.1f}pp)')
print(f'  95% CI on difference (bootstrap): [{ci_diff[0]:.3f}, {ci_diff[1]:.3f}]')
print(f'  Wilson CI wire_only rate: [{ci_wo[0]:.3f}, {ci_wo[1]:.3f}]')
print(f'  Wilson CI overlay rate:   [{ci_ov[0]:.3f}, {ci_ov[1]:.3f}]')
print(f'\n  VERDICT: {"SIGNIFICANT (p<0.05)" if p_fisher < 0.05 else "NOT SIGNIFICANT (p>=0.05)"} at two-sided alpha=0.05')

# ── 2. STEPS-TO-TARGET: Mann-Whitney U ──────────────────────────────────────
print('\n--- TEST 2: Steps-to-target among LAD episodes (Mann-Whitney U) ---')
wo_s = wo['steps_lad']
ov_s = ov['steps_lad']
print(f'  wire_only : n={len(wo_s)}  values={wo_s}')
print(f'             mean={np.mean(wo_s):.1f}  median={np.median(wo_s):.0f}  '
      f'sd={np.std(wo_s, ddof=1):.1f}')
print(f'  overlay   : n={len(ov_s)}  values={ov_s}')
print(f'             mean={np.mean(ov_s):.1f}  median={np.median(ov_s):.0f}  '
      f'sd={np.std(ov_s, ddof=1):.1f}')

U_stat, p_mwu = mannwhitneyu(wo_s, ov_s, alternative='two-sided')
_, p_mwu_1t  = mannwhitneyu(wo_s, ov_s, alternative='less')
n1, n2 = len(wo_s), len(ov_s)
r_effect = 1 - 2*U_stat / (n1*n2)  # r = 1 - 2U/(n1*n2), range [-1,1]
print(f'\n  Mann-Whitney U = {U_stat:.1f}')
print(f'  p (two-sided) = {p_mwu:.4f}')
print(f'  p (one-sided, wo<ov) = {p_mwu_1t:.6f}')
print(f'  Effect size r = {r_effect:.3f}  (|r|>0.5 = large)')
print(f'  Common language effect: P(wo_step < ov_step) = {U_stat/(n1*n2):.3f}')
print(f'\n  VERDICT: {"SIGNIFICANT (p<0.05)" if p_mwu < 0.05 else "NOT SIGNIFICANT (p>=0.05)"} at two-sided alpha=0.05')

# ── 3. LM rot/mm: Mann-Whitney U ────────────────────────────────────────────
print('\n--- TEST 3: LM rot/mm among LAD episodes (Mann-Whitney U) ---')
wo_r = sorted(wo['rots_lad'])
ov_r = sorted(ov['rots_lad'])
print(f'  wire_only : n={len(wo_r)}  mean={np.mean(wo_r):.4f}  '
      f'median={np.median(wo_r):.4f}  sd={np.std(wo_r, ddof=1):.4f}')
print(f'  overlay   : n={len(ov_r)}  mean={np.mean(ov_r):.4f}  '
      f'median={np.median(ov_r):.4f}  sd={np.std(ov_r, ddof=1):.4f}')

U_r, p_r = mannwhitneyu(wo_r, ov_r, alternative='two-sided')
_, p_r_1t = mannwhitneyu(wo_r, ov_r, alternative='less')
r_eff_r = 1 - 2*U_r / (len(wo_r)*len(ov_r))
print(f'\n  Mann-Whitney U = {U_r:.1f}')
print(f'  p (two-sided) = {p_r:.4f}')
print(f'  p (one-sided, wo<ov) = {p_r_1t:.6f}')
print(f'  Effect size r = {r_eff_r:.3f}')
print(f'  Common language effect: P(wo_rot < ov_rot) = {U_r/(len(wo_r)*len(ov_r)):.3f}')
print(f'\n  VERDICT: {"SIGNIFICANT (p<0.05)" if p_r < 0.05 else "NOT SIGNIFICANT (p>=0.05)"} at two-sided alpha=0.05')

# ── 4. POWER CALCULATION for wrong-branch rate ───────────────────────────────
print('\n--- POWER CALCULATION: wrong-branch rate 13% vs 33% ---')
print('  Observed: p1=2/15=0.133 (wire_only), p2=5/15=0.333 (overlay)')

from statsmodels.stats.power import GofChisquarePower
import statsmodels.stats.power as ssp

# Use two-proportion z-test power (normal approx) and exact Fisher's power
p1, p2 = 2/15, 5/15
alpha = 0.05

# Cohen's h effect size
h = 2 * (np.arcsin(np.sqrt(p2)) - np.arcsin(np.sqrt(p1)))
print(f'\n  Cohen h = {h:.4f}  (|h|>0.5 = medium/large)')

# Power at current n=15
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

h_effect = proportion_effectsize(p2, p1)
print(f'  proportion_effectsize (Cohen h) = {h_effect:.4f}')

power_tool = NormalIndPower()
power_15 = power_tool.power(effect_size=h_effect, nobs1=15, alpha=alpha, ratio=1.0,
                             alternative='two-sided')
print(f'  Power at n=15 per arm (two-sided, alpha=0.05): {power_15:.3f}')

# n required for 80% power
n_80 = power_tool.solve_power(effect_size=h_effect, power=0.80, alpha=alpha,
                               ratio=1.0, alternative='two-sided')
n_90 = power_tool.solve_power(effect_size=h_effect, power=0.90, alpha=alpha,
                               ratio=1.0, alternative='two-sided')
print(f'\n  n per arm for 80% power: {n_80:.1f}  → round up to {int(np.ceil(n_80))}')
print(f'  n per arm for 90% power: {n_90:.1f}  → round up to {int(np.ceil(n_90))}')

# Also check with one-sided (directional hypothesis: overlay > wire_only)
n_80_1t = power_tool.solve_power(effect_size=h_effect, power=0.80, alpha=alpha,
                                  ratio=1.0, alternative='larger')
print(f'  n per arm for 80% power (one-sided): {n_80_1t:.1f}  → {int(np.ceil(n_80_1t))}')

# Exact Fisher's power by simulation
rng2 = np.random.default_rng(99)
n_sims = 50000
def fisher_power_sim(n, p1, p2, alpha, n_sims, rng):
    sig = 0
    for _ in range(n_sims):
        x1 = rng.binomial(n, p1)
        x2 = rng.binomial(n, p2)
        tbl = np.array([[n-x1, x1], [n-x2, x2]])
        _, p = fisher_exact(tbl, alternative='two-sided')
        if p < alpha: sig += 1
    return sig / n_sims

print(f'\n  Simulated Fisher exact power (50k sims):')
for n_test in [15, 20, 30, 40, 50, 60, 75, 100]:
    pw = fisher_power_sim(n_test, p1, p2, alpha, n_sims, rng2)
    mark = ' <-- 80%' if abs(pw - 0.80) < 0.05 else ''
    print(f'    n={n_test:3d}: power={pw:.3f}{mark}')

print()
print('=' * 70)
print('SUMMARY FOR PAPER PHRASING')
print('=' * 70)
print(f"""
  Test 1 (wrong-branch, Fisher): p = {p_fisher:.4f}  → NOT SIGNIFICANT
    Phrase as: "associated with a 20pp increase (13%→33%, OR={odds_ratio:.1f})
    but underpowered at n=15 (power={power_15:.0%}, need n≈{int(np.ceil(n_80))} for 80%)"

  Test 2 (steps-to-target, MWU): p = {p_mwu:.4f}  → {"SIGNIFICANT" if p_mwu<0.05 else "NOT SIGNIFICANT"}
    Effect r = {r_effect:.3f}, P(wire<overlay) = {U_stat/(n1*n2):.2f}

  Test 3 (LM rot/mm, MWU): p = {p_r:.4f}  → {"SIGNIFICANT" if p_r<0.05 else "NOT SIGNIFICANT"}
    Effect r = {r_eff_r:.3f}, Finding 1 = the statistically solid claim
""")
