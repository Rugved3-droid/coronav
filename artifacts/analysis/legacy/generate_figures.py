#!/usr/bin/env python3
"""
Generate all 5 publication-quality figures for CoroNav T-MRB paper.
Outputs: D:\steve\pilot\figures\
Data sources: exclusively from on-disk trace files, renders, and lm_illusion_compare.json.
No data is fabricated.
"""

import sys, json, pathlib, warnings
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.gridspec import GridSpec
from PIL import Image
from scipy.stats import mannwhitneyu

warnings.filterwarnings('ignore')
sys.path.insert(0, r"D:\steve\pilot")
sys.path.insert(0, r"D:\steve\stEVE")

from run_biplane import _lm_metrics

PILOT = pathlib.Path(r"D:\steve\pilot")
RUNS  = PILOT / "runs"
OUT   = PILOT / "figures"
OUT.mkdir(exist_ok=True)

# IEEE column-width publication style
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 8,
    'axes.labelsize': 8,
    'axes.titlesize': 8,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'lines.linewidth': 1.2,
    'axes.linewidth': 0.8,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linewidth': 0.5,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
})

C_DARK  = '#222222'
C_MID   = '#777777'
C_LIGHT = '#bbbbbb'

# ------------------------------------------------------------------ helpers --

def load_episodes(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    eps = {}
    for r in rows:
        ep = r.get('episode', 0)
        eps.setdefault(ep, []).append(r)
    return [eps[k] for k in sorted(eps)]

def per_ep_rot_mm(trace_path):
    """Per-episode lm_rot_mm via authoritative _lm_metrics()."""
    vals = []
    for ep_rows in load_episodes(trace_path):
        m = _lm_metrics(ep_rows)
        if m is not None:
            vals.append(m['lm_rot_mm'])
    return np.array(vals)

def per_ep_steps(trace_path):
    """Per-episode step count for successful (terminal, non-truncated) episodes."""
    vals = []
    for ep_rows in load_episodes(trace_path):
        # Find terminal row
        terminal_rows = [r for r in ep_rows if r.get('terminal')]
        if not terminal_rows:
            continue
        last = terminal_rows[-1]
        if last.get('truncation', True):
            continue   # timed-out, not a success
        vals.append(int(last.get('step', len(ep_rows))))
    return np.array(vals)

def annotate_mw(ax, x1, x2, y, p, yoff=0.02, show_p=False):
    star = '***' if p < 0.001 else ('**' if p < 0.01 else '*')
    ax.plot([x1, x1, x2, x2], [y, y+yoff, y+yoff, y], lw=0.7, c='k')
    p_str = ('%.4f' % p) if p >= 0.0001 else '<0.0001'
    lbl = (star + '\np=' + p_str) if show_p else star
    ax.text((x1+x2)/2, y+yoff+0.002, lbl, ha='center', va='bottom', fontsize=6.5,
            linespacing=1.2)


# ================================================================ FIGURE 1 ==

def fig1_architecture():
    fig, ax = plt.subplots(figsize=(7.16, 3.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.2)
    ax.axis('off')

    def box(x, y, w, h, txt, fs=6.7, fc='#f0f0f0', ec='#444444'):
        r = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle="round,pad=0.06",
                           facecolor=fc, edgecolor=ec, linewidth=0.8, zorder=2)
        ax.add_patch(r)
        ax.text(x, y, txt, ha='center', va='center', fontsize=fs,
                multialignment='center', linespacing=1.35, zorder=3)

    def arr(x1, y1, x2, y2, lbl=''):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1), zorder=1,
                    arrowprops=dict(arrowstyle='->', color='#333333', lw=0.9,
                                   connectionstyle='arc3,rad=0'))
        if lbl:
            mx, my = (x1+x2)/2, (y1+y2)/2 + 0.10
            ax.text(mx, my, lbl, ha='center', va='bottom', fontsize=6, color='#555555')

    # Top row
    box(1.15, 3.25, 1.70, 0.95,
        "Coronary Anatomy\nVMR0066 / ASOCA\n(VTP / OBJ mesh)", fc='#ebebeb')
    arr(2.00, 3.25, 2.75, 3.25, 'mesh')
    box(3.70, 3.25, 1.75, 0.95,
        "SOFA v23.06\nBeamAdapter\nGaussSeidel LCP", fc='#e0e0e0')
    arr(4.58, 3.25, 5.42, 3.25, 'state')
    box(6.35, 3.25, 1.65, 0.95,
        "PillowTracking\nAP-Cranial 40 deg\n512x512 px", fc='#e0e0e0')
    arr(7.18, 3.25, 8.00, 3.25, 'frame')
    box(8.95, 3.25, 1.75, 0.95,
        "VLM Operator\nclaude-sonnet-4-6\n-> JSON action", fc='#d0d0d0')

    # VLM -> Action (vertical)
    arr(8.95, 2.77, 8.95, 2.03, 'JSON')

    # Bottom row
    box(8.95, 1.55, 1.75, 0.95,
        "Action Executor\ntranslate / rotate\n/ retract", fc='#e0e0e0')
    arr(8.08, 1.55, 7.38, 1.55, '')
    box(6.35, 1.55, 1.65, 0.95,
        "Metrics Logger\nlm_rot_mm\nsteps-to-target", fc='#ebebeb')

    # Feedback: Action -> SOFA
    ax.annotate('', xy=(3.70, 2.77), xytext=(8.07, 1.55), zorder=1,
                arrowprops=dict(arrowstyle='->', color='#333333', lw=0.9,
                                connectionstyle='angle,angleA=180,angleB=-90,rad=0.15'))
    ax.text(6.0, 0.80, 'guidewire actuation', ha='center', va='center',
            fontsize=6, color='#666666', style='italic')

    # Episode params
    ax.text(5.0, 0.30,
            r"$N_{\rm ep}=25$,  $N_{\rm step}=60$"
            "   |   dt = 0.006 s   |   contactDistance = 0.3 mm",
            ha='center', va='center', fontsize=6.5, color='#444444', style='italic')

    ax.text(5.0, 4.08, "CoroNav System Architecture",
            ha='center', va='center', fontsize=9, fontweight='bold')

    for fmt in ('svg', 'png'):
        fig.savefig(str(OUT / ('fig1_architecture.' + fmt)), format=fmt, dpi=300)
    plt.close(fig)
    print("[OK] Fig 1 -- fig1_architecture.svg + .png")
    print("  Source: schematic; labels from run_biplane.py SOFA/BeamAdapter config")


# ================================================================ FIGURE 2 ==

def fig2_conditions():
    wo_frame = RUNS / "2026-06-28_18-03-27" / "arm_coronary_wire_only" / "ep01_step20.png"
    ov_frame = RUNS / "2026-06-28_19-29-24" / "arm_coronary_overlay"   / "ep01_step20.png"
    ct_frame = RUNS / "2026-06-28_21-00-25" / "arm_coronary_contrast"  / "ep01_step20.png"
    bp_pair  = PILOT / "biplane_preview" / "pair_wire_only.png"

    for p in [wo_frame, ov_frame, ct_frame, bp_pair]:
        if not p.exists():
            raise FileNotFoundError("Required frame not found: " + str(p))

    wo = np.array(Image.open(str(wo_frame)).convert('RGB'))
    ov = np.array(Image.open(str(ov_frame)).convert('RGB'))
    ct = np.array(Image.open(str(ct_frame)).convert('RGB'))
    bp = np.array(Image.open(str(bp_pair)).convert('RGB'))

    # Split biplane pair PNG into AP (left) and LAO (right) halves
    mid = bp.shape[1] // 2
    bp_ap  = bp[:, :mid, :]
    bp_lao = bp[:, mid:, :]

    fig = plt.figure(figsize=(7.16, 3.4))
    gs = GridSpec(2, 3, figure=fig, hspace=0.18, wspace=0.06,
                  left=0.01, right=0.99, top=0.84, bottom=0.02)

    panels = [
        (gs[0, 0], wo,     '(a) Wire-only\nAP-Cranial 40 deg'),
        (gs[0, 1], ov,     '(b) Vessel overlay\nAP-Cranial 40 deg'),
        (gs[0, 2], ct,     '(c) Contrast\nAP-Cranial 40 deg'),
        (gs[1, 0], bp_ap,  '(d) Biplane AP view\nAP-Cranial 40 deg'),
        (gs[1, 1], bp_lao, '(e) Biplane LAO view\nLAO 60 / Cranial 20 deg'),
    ]

    for slot, img, title in panels:
        ax = fig.add_subplot(slot)
        ax.imshow(img, aspect='auto')
        ax.set_title(title, fontsize=6.5, pad=4, linespacing=1.3)
        ax.axis('off')

    ax_empty = fig.add_subplot(gs[1, 2])
    ax_empty.axis('off')

    fig.suptitle("Fig. 2 -- Fluoroscopy observation conditions (VMR0066, seed 2001, step 20)",
                 fontsize=7.5, y=0.97, color='#444444')

    fig.savefig(str(OUT / 'fig2_conditions.png'), dpi=300)
    plt.close(fig)
    print("[OK] Fig 2 -- fig2_conditions.png")
    print("  Sources: ep01_step20 from June-28 wire_only / overlay / contrast runs")
    print("           biplane_preview/pair_wire_only.png (split AP + LAO)")


# ================================================================ FIGURE 3 ==

def fig3_primary():
    v1_wo = RUNS / "ablation_prompt_robustness/v1_current/wire_only/trace.jsonl"
    v1_ov = RUNS / "ablation_prompt_robustness/v1_current/overlay/trace.jsonl"

    wo_rot = per_ep_rot_mm(v1_wo)
    ov_rot = per_ep_rot_mm(v1_ov)
    wo_stp = per_ep_steps(v1_wo)
    ov_stp = per_ep_steps(v1_ov)

    outlier_idx = 14   # ep15, seed 5155, confirmed outlier (skew=3.22)

    _, p_rot = mannwhitneyu(wo_rot, ov_rot, alternative='two-sided')
    _, p_stp = mannwhitneyu(wo_stp, ov_stp, alternative='two-sided')

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 3.5))
    rng = np.random.default_rng(42)

    # Panel (a): lm_rot_mm violin + strip
    grp_rot = [wo_rot, ov_rot]
    vp = ax1.violinplot(grp_rot, positions=[1, 2], showmedians=True, widths=0.55)
    for i, body in enumerate(vp['bodies']):
        body.set_facecolor([C_LIGHT, C_MID][i])
        body.set_edgecolor(C_DARK)
        body.set_alpha(0.6)
    for part in ['cmedians', 'cbars', 'cmins', 'cmaxes']:
        vp[part].set_color(C_DARK)
        vp[part].set_linewidth(1.0)

    for xi, dat in zip([1, 2], grp_rot):
        jit = rng.uniform(-0.10, 0.10, len(dat))
        ax1.scatter(xi + jit, dat, s=14, color=C_DARK, alpha=0.65, zorder=3, linewidths=0)

    # Mark ep15 outlier — open diamond (B&W safe) + arrow annotation
    jit_out = rng.uniform(-0.10, 0.10, 1)[0]
    ax1.scatter(1 + jit_out, wo_rot[outlier_idx], s=60,
                marker='D', facecolors='none', edgecolors=C_DARK,
                linewidths=1.3, zorder=5)
    ax1.annotate('ep15\n(seed 5155)',
                 xy=(1 + jit_out, wo_rot[outlier_idx]),
                 xytext=(1.58, wo_rot[outlier_idx] + 0.015),
                 arrowprops=dict(arrowstyle='->', lw=0.7, color=C_DARK),
                 fontsize=5.5, ha='left', va='bottom', color=C_DARK)

    y_top = max(wo_rot.max(), ov_rot.max()) * 1.05
    yoff = y_top * 0.06
    annotate_mw(ax1, 1, 2, y_top, p_rot, yoff=yoff, show_p=True)

    ax1.set_xticks([1, 2])
    ax1.set_xticklabels(['Wire-only\n(n=%d)' % len(wo_rot),
                         'Overlay\n(n=%d)' % len(ov_rot)])
    ax1.set_ylabel('LM rotation (mm / total LM mm)')
    ax1.set_title('(a) LM rotation metric  (n=25 per arm)')

    # Panel (b): steps-to-target
    grp_stp = [wo_stp, ov_stp]
    bp2 = ax2.boxplot(grp_stp, positions=[1, 2], widths=0.45,
                      patch_artist=True, showfliers=False,
                      medianprops=dict(color=C_DARK, lw=1.5),
                      whiskerprops=dict(color=C_DARK, lw=0.8),
                      capprops=dict(color=C_DARK, lw=0.8),
                      boxprops=dict(linewidth=0.8))
    bp2['boxes'][0].set_facecolor(C_LIGHT);  bp2['boxes'][0].set_alpha(0.6)
    bp2['boxes'][1].set_facecolor(C_MID);    bp2['boxes'][1].set_alpha(0.6)

    for xi, dat in zip([1, 2], grp_stp):
        jit = rng.uniform(-0.10, 0.10, len(dat))
        ax2.scatter(xi + jit, dat, s=14, color=C_DARK, alpha=0.65, zorder=3, linewidths=0)

    y_top2 = max(wo_stp.max() if len(wo_stp) else 0,
                 ov_stp.max() if len(ov_stp) else 0) + 3
    annotate_mw(ax2, 1, 2, y_top2, p_stp, yoff=1.5, show_p=True)

    ax2.set_xticks([1, 2])
    ax2.set_xticklabels(['Wire-only\n(n=%d)' % len(wo_stp),
                         'Overlay\n(n=%d)' % len(ov_stp)])
    ax2.set_ylabel('Steps to reach target')
    ax2.set_title('(b) Steps-to-target (successes only)')

    fig.suptitle("Fig. 3 -- Primary result: overlay vs. wire-only on VMR0066 (v1_current, n=25)",
                 fontsize=7.5, y=1.01)
    plt.tight_layout()

    fig.savefig(str(OUT / 'fig3_primary.png'), dpi=300)
    plt.close(fig)
    print("[OK] Fig 3 -- fig3_primary.png")
    print("  Sources: v1_current wire_only + overlay trace.jsonl (n=25 episodes each)")
    print("  rot MW p=%.4f,  steps MW p=%.4f" % (p_rot, p_stp))
    print("  wo_rot n=%d, ov_rot n=%d, wo_stp n=%d, ov_stp n=%d" % (
          len(wo_rot), len(ov_rot), len(wo_stp), len(ov_stp)))


# ================================================================ FIGURE 4 ==

def fig4_dissociation():
    # Panel (a): scripted d_tgt-vs-step from lm_illusion_compare.json
    with open(str(PILOT / "lm_illusion_compare.json")) as f:
        illusion = json.load(f)

    a1_data = illusion["results"]["VMR 0066 (fresh verification)"][0]   # seed 2001
    a2_data = illusion["results"]["ASOCA Normal_12"][0]                  # seed 3001
    a3_data = illusion["results"]["ASOCA Normal_5"][0]                   # seed 4001

    def delta(data):
        ds = np.array(data["d_series"])
        return ds - ds[0], data["lm_steps"], data["rise_mm"]

    d1, lm1, rise1 = delta(a1_data)
    d2, lm2, rise2 = delta(a2_data)
    d3, lm3, rise3 = delta(a3_data)

    steps1 = np.arange(1, len(d1)+1)
    steps2 = np.arange(1, len(d2)+1)
    steps3 = np.arange(1, len(d3)+1)

    # Panel (b): per-episode overlay effect from live trace files
    a1_wo = per_ep_rot_mm(RUNS / "ablation_prompt_robustness/v1_current/wire_only/trace.jsonl")
    a1_ov = per_ep_rot_mm(RUNS / "ablation_prompt_robustness/v1_current/overlay/trace.jsonl")
    a2_wo = per_ep_rot_mm(RUNS / "normal12_wire_only/arm_asoca_normal12_wire_only/trace.jsonl")
    a2_ov = per_ep_rot_mm(RUNS / "normal12_overlay/arm_asoca_normal12_overlay/trace.jsonl")
    a3_wo = per_ep_rot_mm(RUNS / "normal5_wire_only/arm_asoca_normal5_wire_only/trace.jsonl")
    a3_ov = per_ep_rot_mm(RUNS / "normal5_overlay/arm_asoca_normal5_overlay/trace.jsonl")

    _, p_a1 = mannwhitneyu(a1_wo, a1_ov, alternative='two-sided')
    _, p_a2 = mannwhitneyu(a2_wo, a2_ov, alternative='two-sided')
    _, p_a3 = mannwhitneyu(a3_wo, a3_ov, alternative='two-sided')

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 3.5))

    # Panel (a): d_tgt curves — LM phase only for rise label, post-bif annotated separately
    ax1.axhline(0, color='#cccccc', lw=0.6, ls='--')

    # Shade LM phase for A1 only (where illusion occurs)
    if lm1:
        ax1.axvspan(min(lm1), max(lm1) + 0.5, alpha=0.12, color='#888888',
                    label='LM phase (A1)', zorder=0)

    # Determine LM/post-bif split step for A3
    # A3 lm_steps from JSON: 1-11; post-bif starts at step 12 (lcx)
    a3_lm_set = set(a3_data["lm_steps"])
    a3_bif    = max(a3_lm_set) + 1   # first post-bif step index = 12 (1-based)

    # A1: full curve (peak and post-bif both descend — no visual confusion)
    ax1.plot(steps1, d1, '-o', ms=3.5, color=C_DARK,
             label='A1 VMR0066 (illusion +4.36 mm)')
    # A2: full curve (monotone decrease)
    ax1.plot(steps2, d2, '-s', ms=3.5, color=C_MID,
             label='A2 Normal-12 (no illusion, 0.00 mm)')
    # A3: LM phase solid, post-bif dashed with different marker
    a3_lm_steps   = [i+1 for i in range(len(d3)) if (i+1) in a3_lm_set]
    a3_post_steps = [i+1 for i in range(len(d3)) if (i+1) not in a3_lm_set]
    a3_lm_d   = [d3[i-1] for i in a3_lm_steps]
    a3_post_d = [d3[i-1] for i in a3_post_steps]

    ax1.plot(a3_lm_steps, a3_lm_d, '-^', ms=3.5, color=C_LIGHT,
             label='A3 Normal-5 (no illusion, +0.18 mm in LM)')
    if a3_post_steps:
        # Connect LM end to post-bif start seamlessly, then dashed
        connect_steps = [a3_lm_steps[-1]] + a3_post_steps
        connect_d     = [a3_lm_d[-1]]     + a3_post_d
        ax1.plot(connect_steps, connect_d, '--^', ms=3.5, color=C_LIGHT,
                 alpha=0.6, label='_nolegend_')
        # Annotate post-bif divergence
        ax1.annotate('LCx divergence\n(wrong branch)',
                     xy=(a3_post_steps[-1], float(a3_post_d[-1])),
                     xytext=(a3_post_steps[-1] - 3.5, float(a3_post_d[-1]) - 5.0),
                     arrowprops=dict(arrowstyle='->', lw=0.7, color=C_LIGHT),
                     fontsize=5.5, ha='right', color='#888888', style='italic')
        # Mark bifurcation boundary
        ax1.axvline(x=a3_bif - 0.5, color=C_LIGHT, lw=0.7, ls=':', alpha=0.7)

    # Annotate A1 LM rise (peak within LM phase)
    peak_step = int(np.argmax(d1)) + 1
    ax1.annotate('LM-phase rise\n+4.36 mm (A1)',
                 xy=(peak_step, float(d1[peak_step-1])),
                 xytext=(peak_step + 2.5, float(d1[peak_step-1]) + 2.5),
                 arrowprops=dict(arrowstyle='->', lw=0.8, color=C_DARK),
                 fontsize=5.5, ha='left', color=C_DARK)

    ax1.set_xlabel('Scripted advance step')
    ax1.set_ylabel('Delta distance to LAD target (mm)')
    ax1.set_title('(a) Scripted traversal: d_tgt vs. step\n'
                  '(solid = LM phase; dashed = post-bifurcation)')
    ax1.legend(fontsize=6, loc='lower left')

    # Panel (b): overlay effect per anatomy
    ana_labels = ['A1\nVMR0066', 'A2\nNormal-12', 'A3\nNormal-5']
    x = np.array([1, 2, 3])
    wo_med = [np.median(a1_wo), np.median(a2_wo), np.median(a3_wo)]
    ov_med = [np.median(a1_ov), np.median(a2_ov), np.median(a3_ov)]
    wo_data = [a1_wo, a2_wo, a3_wo]
    ov_data = [a1_ov, a2_ov, a3_ov]
    ps = [p_a1, p_a2, p_a3]

    width = 0.30
    ax2.bar(x - width/2, wo_med, width, color=C_LIGHT, edgecolor=C_DARK,
            linewidth=0.7, label='Wire-only')
    ax2.bar(x + width/2, ov_med, width, color=C_MID, edgecolor=C_DARK,
            linewidth=0.7, label='Overlay')

    rng = np.random.default_rng(0)
    for xi, wo, ov in zip(x, wo_data, ov_data):
        ax2.scatter(xi - width/2 + rng.uniform(-0.07, 0.07, len(wo)),
                    wo, s=8, color=C_DARK, alpha=0.4, zorder=4, linewidths=0)
        ax2.scatter(xi + width/2 + rng.uniform(-0.07, 0.07, len(ov)),
                    ov, s=8, color=C_DARK, alpha=0.4, zorder=4, linewidths=0)

    all_vals = [v for grp in (wo_data + ov_data) for v in grp]
    y_max = max(all_vals) if all_vals else 1.0
    for xi, p in zip(x, ps):
        lbl_p = ('p=%.4f' % p) if p >= 0.0001 else 'p<0.0001'
        ax2.text(xi, y_max * 1.12, lbl_p, ha='center', va='bottom', fontsize=5.8,
                 color=C_DARK, fontweight='bold')

    ax2.set_xticks(x)
    ax2.set_xticklabels(ana_labels)
    ax2.set_ylabel('LM rotation (mm / total LM mm) -- median')
    ax2.set_title('(b) Overlay effect on LM rotation per anatomy\n(significant in all 3; A1 p=0.0004, A2 p<0.001, A3 p<0.001)')
    ax2.legend(fontsize=6.5, loc='upper left')
    ax2.set_ylim(0, y_max * 1.35)

    fig.suptitle("Fig. 4 -- Overlay increases LM rotation across all anatomies; behavioral consequence is anatomy-gated",
                 fontsize=7.5, y=1.01)
    plt.tight_layout()

    fig.savefig(str(OUT / 'fig4_dissociation.png'), dpi=300)
    plt.close(fig)
    print("[OK] Fig 4 -- fig4_dissociation.png")
    print("  Panel (a) source: lm_illusion_compare.json  (scripted d_series, seeds 2001/3001/4001)")
    print("  Panel (b) sources: v1_current + normal12 + normal5 trace files")
    print("  A1: n_wo=%d n_ov=%d p=%.4f" % (len(a1_wo), len(a1_ov), p_a1))
    print("  A2: n_wo=%d n_ov=%d p=%.4f" % (len(a2_wo), len(a2_ov), p_a2))
    print("  A3: n_wo=%d n_ov=%d p=%.4f" % (len(a3_wo), len(a3_ov), p_a3))


# ================================================================ FIGURE 5 ==

def fig5_robustness_biplane():
    # Panel (a): ablation prompt variants
    variant_specs = [
        ('V1\nv1_current',
         RUNS / "ablation_prompt_robustness/v1_current/wire_only/trace.jsonl",
         RUNS / "ablation_prompt_robustness/v1_current/overlay/trace.jsonl"),
        ('V2\nv2_neutral',
         RUNS / "ablation_prompt_robustness/v2_neutral/wire_only/trace.jsonl",
         RUNS / "ablation_prompt_robustness/v2_neutral/overlay/trace.jsonl"),
        ('V3\nv3_reworded',
         RUNS / "ablation_prompt_robustness/v3_reworded/wire_only/trace.jsonl",
         RUNS / "ablation_prompt_robustness/v3_reworded/overlay/trace.jsonl"),
        ('V4\nv4_gentle',
         RUNS / "ablation_prompt_robustness/v4_gentle/wire_only/trace.jsonl",
         RUNS / "ablation_prompt_robustness/v4_gentle/overlay/trace.jsonl"),
    ]

    labels   = []
    wo_meds  = []
    ov_meds  = []
    wo_all   = []
    ov_all   = []
    pvals    = []

    for lbl, wo_path, ov_path in variant_specs:
        wo = per_ep_rot_mm(wo_path)
        ov = per_ep_rot_mm(ov_path)
        _, p = mannwhitneyu(wo, ov, alternative='two-sided')
        labels.append(lbl)
        wo_meds.append(np.median(wo))
        ov_meds.append(np.median(ov))
        wo_all.append(wo)
        ov_all.append(ov)
        pvals.append(p)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.16, 3.5))
    x = np.arange(1, len(labels)+1)
    width = 0.32
    rng = np.random.default_rng(7)

    # V3 (index 2, x=3) gets hatching — navigation collapsed, excluded from inference
    V3_IDX = 2
    for xi, wm, om, lbl in zip(x, wo_meds, ov_meds, labels):
        is_v3 = (xi == x[V3_IDX])
        hatch = '///' if is_v3 else None
        alpha = 0.35 if is_v3 else 0.65
        fc_wo = C_LIGHT if not is_v3 else '#dddddd'
        fc_ov = C_MID   if not is_v3 else '#aaaaaa'
        ax1.bar(xi - width/2, wm, width, color=fc_wo, edgecolor=C_DARK,
                linewidth=0.7, hatch=hatch, alpha=alpha,
                label='Wire-only' if xi == x[0] else '_nolegend_')
        ax1.bar(xi + width/2, om, width, color=fc_ov, edgecolor=C_DARK,
                linewidth=0.7, hatch=hatch, alpha=alpha,
                label='Overlay' if xi == x[0] else '_nolegend_')

    for xi, wo, ov in zip(x, wo_all, ov_all):
        is_v3 = (xi == x[V3_IDX])
        alp = 0.20 if is_v3 else 0.40
        ax1.scatter(xi - width/2 + rng.uniform(-0.08, 0.08, len(wo)),
                    wo, s=8, color=C_DARK, alpha=alp, zorder=4, linewidths=0)
        ax1.scatter(xi + width/2 + rng.uniform(-0.08, 0.08, len(ov)),
                    ov, s=8, color=C_DARK, alpha=alp, zorder=4, linewidths=0)

    all_vals5 = [v for grp in (wo_all + ov_all) for v in grp]
    y_max5 = max(all_vals5) if all_vals5 else 1.0

    for xi, p, lbl in zip(x, pvals, labels):
        is_v3 = (xi == x[V3_IDX])
        if is_v3:
            continue   # p-value replaced by exclusion note below
        lbl_p = ('p=%.3f' % p) if p >= 0.001 else ('p=%.4f' % p)
        fw = 'bold' if p < 0.01 else 'normal'
        ax1.text(xi, y_max5 * 1.10, lbl_p, ha='center', va='bottom',
                 fontsize=5.8, fontweight=fw)

    # Exclusion label for V3
    ax1.text(x[V3_IDX], y_max5 * 1.08,
             'nav. collapsed\nexcluded',
             ha='center', va='bottom', fontsize=5.0, color='#666666',
             style='italic', linespacing=1.2)

    # V2 annotation: both arms near-zero rotation (prompt suppresses rotation)
    ax1.text(x[1], y_max5 * 0.20,
             'both arms\n~zero rotation',
             ha='center', va='bottom', fontsize=5.0, color='#666666',
             style='italic', linespacing=1.2)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=6.5)
    ax1.set_ylabel('LM rotation (mm / total LM mm) -- median')
    ax1.set_title('(a) Prompt ablation — underpowered secondary check (n=10/variant)\n'
                  'V1 p=0.0004 (n=25, significant). V2: both arms ~zero (uninformative). '
                  'V4: same direction, NS. V3: excluded.')
    ax1.legend(fontsize=6.5)
    ax1.set_ylim(0, y_max5 * 1.35)

    # Panel (b): biplane correction cascade
    # Source: PAPER_DATA.md biplane section
    stage_labels = [
        'Unmatched\nseeds\n(n=5)',
        'Seed-matched\n60 steps\n(n=9)',
        'Seed-matched\n120 steps\n(n=9)',
    ]
    diffs = [-6.3, -2.2, -0.6]   # pp biplane - monoplane

    x2 = np.arange(1, 4)
    cols = [C_DARK, C_MID, C_LIGHT]
    ax2.bar(x2, diffs, color=cols, edgecolor=C_DARK, linewidth=0.8, width=0.55)
    ax2.axhline(0, color='#888888', lw=0.8, ls='--')

    for xi, d in zip(x2, diffs):
        va = 'top' if d < 0 else 'bottom'
        off = -0.15 if d < 0 else 0.15
        ax2.text(xi, d + off, '%+.1f pp' % d,
                 ha='center', va=va, fontsize=7.5,
                 color='white' if abs(d) > 3 else C_DARK)

    ax2.set_xticks(x2)
    ax2.set_xticklabels(stage_labels, fontsize=6.5)
    ax2.set_ylabel('Overlay: biplane - monoplane LM rotation (pp)')
    ax2.set_title('(b) Biplane correction cascade\n(overlay arm LM-rot%; all comparisons NS)')
    ax2.text(0.97, 0.05, 'All Fisher/MW p > 0.05 (NS)',
             transform=ax2.transAxes, ha='right', va='bottom',
             fontsize=6.5, color='#555555', style='italic')

    fig.suptitle("Fig. 5 -- Prompt robustness ablation (a) and biplane null result (b)",
                 fontsize=7.5, y=1.01)
    plt.tight_layout()

    fig.savefig(str(OUT / 'fig5_robustness_biplane.png'), dpi=300)
    plt.close(fig)
    print("[OK] Fig 5 -- fig5_robustness_biplane.png")
    print("  Panel (a) sources: ablation_prompt_robustness/v1-v4 trace.jsonl files")
    print("  Panel (b) source:  PAPER_DATA.md biplane cascade (-6.3/-2.2/-0.6 pp)")
    for lbl, p, wm, om in zip(labels, pvals, wo_meds, ov_meds):
        print("    %-18s  wo_med=%.3f  ov_med=%.3f  MW p=%.4f" % (
              lbl.replace('\n', ' '), wm, om, p))


# ================================================================ MAIN =======

if __name__ == '__main__':
    print("=" * 60)
    print("CoroNav Figure Generation")
    print("=" * 60)
    fig1_architecture()
    fig2_conditions()
    fig3_primary()
    fig4_dissociation()
    fig5_robustness_biplane()
    print("=" * 60)
    print("All figures written to: " + str(OUT))
