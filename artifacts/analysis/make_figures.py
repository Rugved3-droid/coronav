"""Submission figures for IJCARS. Plots committed result artifacts only; computes no new statistic.

Every number drawn here is read from a file in results/ that the manifest already cites. Where a
panel needs an interval, the interval is the one already in the artifact (Wilson, computed by the
Phase 7c/7d scripts). The operator's success rates are plotted as single draws with NO interval,
because no interval for them exists in the analysis and inventing one here would imply a
comparison the paper deliberately does not test.

IJCARS artwork requirements (fetched 2026-09-15): vector EPS preferred; halftone >= 300 dpi,
combination art >= 600 dpi; RGB; 174 mm wide for single-column figures. Each figure is written as
PDF and EPS (vector, fonts embedded) and as a 600 dpi RGB TIFF.

Figures 1 and 2 are produced by `analysis/make_figures_1_2.py`, which re-runs the original
composition at 600 dpi from the source renders; running this module runs that one too, so one
command produces all four figures.

    python analysis/make_figures.py
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
OUT = ROOT / "submission" / "figures"
PILOT_FIGS = Path(r"D:\steve\pilot\figures")

MM = 1 / 25.4
WIDTH = 174 * MM

# Okabe-Ito, colour-vision-deficiency safe.
C_WO, C_OV = "#0072B2", "#D55E00"      # wire-only, overlay
C_A1, C_A2 = "#009E73", "#CC79A7"      # anatomy A1, A2
C_BAND = "#DDDDDD"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42,
})


def read(name: str) -> list[dict]:
    with open(RES / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def manifest() -> dict[str, str]:
    """Statistical annotations drawn on figures come from the same manifest the manuscript is
    built from, so artwork cannot drift from the text.

    This matters because artwork is NOT linted: `build_manuscript.py` refuses a hand-typed
    number in prose, but a p-value typed into a figure caption or an axes annotation is invisible
    to it. Reading the value here closes that gap by construction.
    """
    with open(RES / "manifest.csv", newline="", encoding="utf-8") as fh:
        return {r["key"]: r["value"] for r in csv.DictReader(fh)}


def save(fig, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.eps", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.tif", dpi=600, bbox_inches="tight",
                pil_kwargs={"compression": "tiff_lzw"}, facecolor="white")
    # Matplotlib writes the TIFF with an alpha channel (RGBA). The journal asks for RGB, and
    # alpha in submitted TIFFs is a common cause of production rejections, so flatten it onto
    # white. facecolor="white" above means nothing is lost: the alpha channel is already opaque.
    with Image.open(OUT / f"{stem}.tif") as im:
        if im.mode != "RGB":
            flat = Image.new("RGB", im.size, "white")
            flat.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
            flat.save(OUT / f"{stem}.tif", format="TIFF", compression="tiff_lzw", dpi=(600, 600))
    plt.close(fig)
    print(f"wrote {OUT / stem}.{{pdf,eps,tif}}  (TIFF: 600 dpi, RGB)")


def cumulative(steps: list[int | None], n: int, horizon: int):
    xs = list(range(0, horizon + 1))
    ys = [100.0 * sum(1 for s in steps if s is not None and s <= t) / n for t in xs]
    return xs, ys


def fig3() -> None:
    ep = read("phase3_episodes_a1.csv")
    by_arm = defaultdict(list)
    for r in ep:
        by_arm[r["arm"]].append(int(r["steps"]) if r["success"] == "True" and r["steps"] else None)
    pairs = read("phase6h_pairs_a2.csv")
    a2_wo = [int(r["steps_wire_only"]) for r in pairs]
    a2_ov = [int(r["steps_overlay"]) for r in pairs]

    M = manifest()
    # Arms are distinguished by colour AND line style AND marker, so the panels survive
    # grayscale printing and colour-vision deficiency without relying on hue alone.
    STYLE = {
        "wire_only": dict(color=C_WO, ls="-", marker="o", label="Wire-only"),
        "overlay": dict(color=C_OV, ls="--", marker="s", label="Overlay"),
    }

    def draw(ax, steps, n, horizon, arm, markevery):
        s = STYLE[arm]
        xs, ys = cumulative(steps, n, horizon)
        ax.step(xs, ys, where="post", color=s["color"], ls=s["ls"], lw=1.6, label=s["label"])
        ax.plot(xs[::markevery], ys[::markevery], ls="none", marker=s["marker"], ms=3.4,
                mfc="white", mec=s["color"], mew=1.0)

    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 64 * MM), sharey=True)
    ax = axes[0]
    for arm in ("wire_only", "overlay"):
        draw(ax, by_arm[arm], len(by_arm[arm]), 60, arm, 8)
    ax.set_title("(a) A1, all episodes (failures censored at the step limit)", loc="left")
    ax.set_xlabel("Step")
    ax.set_ylabel("Cumulative proportion reaching target (%)")
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, loc="upper left")
    # Annotations sit in the empty upper-left block beneath the legend, on a translucent patch.
    # Placed lower-right they overlapped the overlay curve, which climbs steeply at the right.
    ax.text(0.04, 0.70,
            f"worst-rank p = {M['nav.worstrank_p']}\n"
            f"win ratio {M['nav.win_ratio']} ({M['nav.wr_lo']}–{M['nav.wr_hi']})",
            transform=ax.transAxes, ha="left", va="top", fontsize=6.5, color="#444444",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.5))

    ax = axes[1]
    for steps, arm in ((a2_wo, "wire_only"), (a2_ov, "overlay")):
        draw(ax, steps, len(steps), 62, arm, 8)
    ax.set_title("(b) A2, every episode reached target", loc="left")
    ax.set_xlabel("Step")
    ax.set_xlim(0, 62)
    ax.text(0.04, 0.97,
            f"Hodges–Lehmann {M['a2.steps_hl']} steps\np = {M['a2.steps_p']}",
            transform=ax.transAxes, ha="left", va="top", fontsize=6.5, color="#444444",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.5))
    fig.tight_layout()
    save(fig, "Fig3")


def fig4() -> None:
    sweep = read("phase7c_speed_sweep.csv")
    pooled = read("phase7c_pooled_default.csv")
    speed = read("phase7_operator_speed.csv")
    dist = read("phase7_operator_speed_distribution.csv")
    oracle = read("phase7d_oracle.csv")
    ep = read("phase3_episodes_a1.csv")
    pairs = read("phase6h_pairs_a2.csv")

    fig, axes = plt.subplots(1, 3, figsize=(WIDTH, 64 * MM),
                             gridspec_kw={"width_ratios": [1.1, 1.2, 1.1]})

    # (a) blind success by speed, operator single draws at the operator's median speed
    ax = axes[0]
    op_success = {
        "A1": 100.0 * sum(1 for r in ep if r["arm"] == "wire_only" and r["success"] == "True")
              / sum(1 for r in ep if r["arm"] == "wire_only"),
        "A2": 100.0 * sum(1 for r in pairs if int(r["steps_wire_only"]) <= 45) / len(pairs),
    }
    op_speed = {r["anatomy"]: float(r["median_advance_mm_s"]) for r in speed if r["arm"] == "wire_only"}
    for anat, colour, dx in (("A1", C_A1, -0.8), ("A2", C_A2, 0.8)):
        pts = []
        for r in sweep:
            if r["anatomy"].startswith(anat) and float(r["advance_mm_s"]) != 35.0:
                pts.append((float(r["advance_mm_s"]), float(r["rate"]), float(r["wilson_lo"]),
                            float(r["wilson_hi"])))
        for r in pooled:
            if r["anatomy"].startswith(anat):
                pts.append((35.0, float(r["pooled_rate"]), float(r["wilson_lo"]),
                            float(r["wilson_hi"])))
        pts.sort()
        xs = [p[0] + dx for p in pts]
        ys = [100 * p[1] for p in pts]
        lo = [100 * (p[1] - p[2]) for p in pts]
        hi = [100 * (p[3] - p[1]) for p in pts]
        ax.errorbar(xs, ys, yerr=[lo, hi], color=colour, marker="o", ms=3.5, lw=1.2, capsize=2,
                    label=f"{anat} blind policy")
        # The diamond is plotted at the OPERATOR'S MEDIAN ADVANCE SPEED, not at any speed the
        # operator was run at: the operator chose its own translation every step and was never
        # run as a fixed-speed policy. It is one draw, with no interval, because no interval for
        # it exists in the analysis and inventing one would imply a test the paper does not run.
        # Legend label kept short: the longer form overflowed the axes and was clipped mid-word.
        # The caption carries the full statement - that the diamond is one draw, plotted at the
        # operator's median advance speed rather than at any speed it was run at.
        ax.plot([op_speed[anat]], [op_success[anat]], marker="D", ms=5, mfc="white", mec=colour,
                mew=1.4, ls="none", label=f"{anat} operator (single draw)")
    ax.set_xlabel("Advance speed (mm/s)")
    ax.set_ylabel("Episodes reaching target (%)")
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 105)
    ax.set_title("(a) Blind success by speed", loc="left")
    ax.legend(frameon=True, framealpha=0.85, edgecolor="none", loc="lower left", fontsize=5.4)

    # (b) operator advance distribution per arm
    ax = axes[1]
    # Mutually exclusive AND exhaustive. The previous labels ("<=5", "<=10", "<=30") read as
    # nested rather than disjoint, and the previous definitions left the open interval (30, 35)
    # in no bin at all: an exactly-35 bin sat beside a ">10-30" bin with a gap between them. No
    # observed value fell in that gap, so no bar was wrong, but the shares were not guaranteed to
    # sum to 100%. They now are, and the assertion below enforces it.
    bins = [("0", lambda v: v == 0),
            (">0–5", lambda v: 0 < v <= 5),
            (">5–10", lambda v: 5 < v <= 10),
            (">10–30", lambda v: 10 < v <= 30),
            (">30–35", lambda v: 30 < v <= 35),
            (">35", lambda v: v > 35)]
    # Colour encodes ANATOMY (matching panels a and c); fill encodes ARM: solid = wire-only,
    # hatched on white = overlay. An earlier version coloured by arm and hatched by anatomy with the
    # hatch drawn in the fill colour, which made the hatching invisible and A1/A2 indistinguishable.
    arms = [("A1", "wire_only", C_A1, "A1 wire-only"), ("A1", "overlay", C_A1, "A1 overlay"),
            ("A2", "wire_only", C_A2, "A2 wire-only"), ("A2", "overlay", C_A2, "A2 overlay")]
    width = 0.2
    for k, (anat, arm, colour, label) in enumerate(arms):
        rows = [r for r in dist if r["anatomy"] == anat and r["arm"] == arm]
        shares = [sum(float(r["pct_of_steps"]) for r in rows if fn(float(r["translation_mm_s"])))
                  for _, fn in bins]
        if rows and abs(sum(shares) - 100.0) > 0.5:
            raise ValueError(f"{label}: advance-speed bins cover {sum(shares):.1f}% of steps, "
                             f"not 100% - the bin definitions have a gap or an overlap")
        xs = [i + (k - 1.5) * width for i in range(len(bins))]
        solid = arm == "wire_only"
        ax.bar(xs, shares, width=width, color=colour if solid else "white",
               hatch="" if solid else "//////", edgecolor=colour, lw=0.6, label=label)
    ax.set_xticks(range(len(bins)))
    # Rotated: six interval labels set horizontally collide with one another at this width.
    ax.set_xticklabels([b for b, _ in bins], rotation=45, ha="right", fontsize=6)
    ax.set_xlabel("Operator advance per step (mm/s)")
    ax.set_ylabel("Share of steps (%)")
    ax.set_title("(b) Operator advance speed", loc="left")
    ax.legend(frameon=False, fontsize=5.5, loc="upper left")

    # (c) constant-rotation probe against the pooled blind floor
    ax = axes[2]
    for anat, colour, dx in (("A1", C_A1, -0.04), ("A2", C_A2, 0.04)):
        fl = next(r for r in pooled if r["anatomy"].startswith(anat))
        rows = sorted((r for r in oracle if r["anatomy"].startswith(anat) and r["rotation"] != "UNION"),
                      key=lambda r: float(r["rotation"]))
        xs = [float(r["rotation"]) + dx for r in rows]
        ys = [100 * float(r["rate"]) for r in rows]
        lo = [100 * (float(r["rate"]) - float(r["wilson_lo"])) for r in rows]
        hi = [100 * (float(r["wilson_hi"]) - float(r["rate"])) for r in rows]
        ax.errorbar(xs, ys, yerr=[lo, hi], color=colour, marker="s", ms=3, lw=0, elinewidth=1,
                    capsize=1.5, label=f"{anat} constant rotation")
        ax.axhline(100 * float(fl["pooled_rate"]), color=colour, lw=1, ls="--",
                   label=f"{anat} blind floor, pooled")
    ax.set_xlabel("Constant rotation")
    ax.set_ylabel("Episodes reaching target (%)")
    ax.set_ylim(0, 105)
    ax.set_title("(c) Constant-rotation probe", loc="left")
    ax.legend(frameon=True, framealpha=0.85, edgecolor="none", fontsize=5.4, loc="lower left")

    fig.tight_layout()
    save(fig, "Fig4")


def main() -> int:
    fig3()
    # fig4() is NOT called. It was the calibration figure: blind success by advance speed (panel a),
    # the operator's advance distribution (b), and the constant-rotation probe (c). The speed sweep
    # and the probe were measured at dt=0.006 and are retired by C22, which leaves panel (b)
    # orphaned - an advance-speed histogram with nothing left to contextualise it. The function is
    # retained so the figure can be regenerated if those baselines are ever re-measured at the
    # arms' timestep.
    import make_figures_1_2  # noqa: E402  (same directory; keeps one entry point for all figures)

    return make_figures_1_2.main()


if __name__ == "__main__":
    raise SystemExit(main())
