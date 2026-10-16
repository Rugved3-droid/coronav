"""Figures 1 and 2 for IJCARS, re-exported at the journal's artwork resolution.

WHAT THIS IS. Figures 1 (environment schematic) and 2 (observation conditions) were composed for
the original T-MRB submission by `D:\\steve\\pilot\\generate_figures.py`, a copy of which is
committed unchanged at `analysis/legacy/generate_figures.py` as provenance. That script writes 300
dpi PNG, which does not meet the journal's 600 dpi combination-art requirement, and its Figures 3-5
are built on analyses this revision superseded. This module re-runs ONLY its Figure 1 and Figure 2
composition, at an overridden resolution, and writes vector PDF/EPS where the source is vector.

The drawing code below is the original composition, carried over. Three deliberate changes, each
reported in results/LOG.md:

  1. The burned-in figure titles are removed. IJCARS carries figure titles in the caption, and a
     title inside the artwork duplicates it.
  2. Figure 1's parameter line no longer asserts a single step budget. The original read
     "N_ep = 25, N_step = 60". 60 is A1's budget; A2's arms did not share one (CORRECTIONS.md,
     C13), so as a global statement it was false. The line now names the episode count and the
     solver constants only, and points to Methods for budgets.
  3. Figure 2's panels are labelled by condition only. The original burned in
     "seed 2001, step 20", which reads as though one wire position is shown in all panels; the
     three monoplane frames are step 20 of three SEPARATE runs, so the wire is in three different
     places. What the figure shows is the rendering conditions, not a matched instant.
  4. Figure 2's frames are drawn at aspect="equal". The original drew them at aspect="auto", which
     stretched each 512x512 render to fill a wide axes and so distorted the projected anatomy.
  5. Figure 2's biplane panels are cropped to the render itself, dropping the preview's burned-in
     annotation bars (including "step=19 dist_to_target=2.4mm seed=2001"). A number printed into
     artwork cannot be checked against the manifest, and the projections it labelled are already
     in the panel titles.

RESOLUTION. The TIFF is rendered so that its pixel width is exactly 174 mm at 600 dpi: the figure
is saved once to measure the tight bounding box, then re-saved at the dpi that lands on that pixel
count. So the raster is a true 600 dpi rendering at the journal's single-column width, not an
upscaled 300 dpi image. PDF and EPS are vector and carry no resolution; they are saved at the
composition's native size for the typesetter to scale.

INPUTS. Figure 2 reads four rendered frames from the pilot tree, outside this repository:

    runs/2026-06-28_18-03-27/arm_coronary_wire_only/ep01_step20.png
    runs/2026-06-28_19-29-24/arm_coronary_overlay/ep01_step20.png
    runs/2026-06-28_21-00-25/arm_coronary_contrast/ep01_step20.png
    biplane_preview/pair_wire_only.png

All four were verified present on 2026-09-16. The script fails loudly if any is missing rather than
substituting anything.

Runs in the base Python environment: matplotlib, numpy and Pillow only. Unlike the legacy script it
does not import `run_biplane`, so it needs neither pyvista nor the SOFA environment.

    python analysis/make_figures_1_2.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "submission" / "figures"
PILOT = pathlib.Path(r"D:\steve\pilot")
RUNS = PILOT / "runs"

MM = 1 / 25.4
TARGET_MM = 174.0          # IJCARS single-column width
TARGET_DPI = 600           # combination art
C_DARK = "#222222"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8,
    "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "lines.linewidth": 1.2, "axes.linewidth": 0.8,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
    "pdf.fonttype": 42, "ps.fonttype": 42,   # embed fonts as TrueType, not Type 3
})


def save_raster_600(fig, stem: str) -> None:
    """Write <stem>.tif as RGB at exactly TARGET_MM wide and TARGET_DPI.

    Saved twice on purpose: once to measure the tight bounding box in pixels (it cannot be known
    before rendering), then at the dpi that makes the pixel width land on 174 mm at 600 dpi.
    """
    target_px = int(round(TARGET_MM * MM * TARGET_DPI))
    with tempfile.TemporaryDirectory() as tmp:
        probe = pathlib.Path(tmp) / "probe.png"
        fig.savefig(probe, dpi=TARGET_DPI)
        with Image.open(probe) as im:
            probe_px = im.width
        dpi = TARGET_DPI * target_px / probe_px
        final = pathlib.Path(tmp) / "final.png"
        fig.savefig(final, dpi=dpi, facecolor="white")
        with Image.open(final) as im:
            flat = Image.new("RGB", im.size, "white")
            flat.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
            flat.save(OUT / f"{stem}.tif", format="TIFF", compression="tiff_lzw",
                      dpi=(TARGET_DPI, TARGET_DPI))
            w_mm = flat.width / TARGET_DPI * 25.4
    print(f"wrote {stem}.tif  {flat.width}x{flat.height} px  RGB  {TARGET_DPI} dpi  "
          f"{w_mm:.1f} mm wide  (rendered at {dpi:.0f} dpi)")


def fig1() -> None:
    fig, ax = plt.subplots(figsize=(7.16, 3.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0.1, 3.9)
    ax.axis("off")

    def box(x, y, w, h, txt, fs=6.7, fc="#f0f0f0", ec="#444444"):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.06",
                                    facecolor=fc, edgecolor=ec, linewidth=0.8, zorder=2))
        ax.text(x, y, txt, ha="center", va="center", fontsize=fs, multialignment="center",
                linespacing=1.35, zorder=3)

    def arr(x1, y1, x2, y2, lbl=""):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), zorder=1,
                    arrowprops=dict(arrowstyle="->", color="#333333", lw=0.9,
                                    connectionstyle="arc3,rad=0"))
        if lbl:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.10, lbl, ha="center", va="bottom",
                    fontsize=6, color="#555555")

    box(1.15, 3.25, 1.70, 0.95, "Coronary anatomy\nVMR 0066 / ASOCA\n(VTP / OBJ mesh)", fc="#ebebeb")
    arr(2.00, 3.25, 2.75, 3.25, "mesh")
    box(3.70, 3.25, 1.75, 0.95, "SOFA v23.06\nBeamAdapter\nGauss-Seidel LCP", fc="#e0e0e0")
    arr(4.58, 3.25, 5.42, 3.25, "state")
    box(6.35, 3.25, 1.65, 0.95, "Fluoroscopy render\nAP-cranial 40 deg\n512 x 512 px", fc="#e0e0e0")
    arr(7.18, 3.25, 8.00, 3.25, "frame")
    box(8.95, 3.25, 1.75, 0.95, "VLM operator\nstateless call\n-> JSON action", fc="#d0d0d0")

    arr(8.95, 2.77, 8.95, 2.03, "JSON")

    box(8.95, 1.55, 1.75, 0.95, "Action executor\ntranslate / rotate\n/ retract", fc="#e0e0e0")

    # The logger is a RECORDING SINK. It takes one arrow IN from the executor and sends nothing
    # onward, so it cannot read as part of the control path.
    arr(8.08, 1.55, 7.28, 1.55, "")
    ax.text(7.68, 1.68, "record", ha="center", va="bottom", fontsize=5.8, color="#888888")
    box(6.35, 1.55, 1.75, 0.95, "Metrics logger\n(records only)\nstate, action, outcome",
        fs=6.2, fc="#f6f6f6")

    # Control loop closes BELOW everything: executor -> down -> across -> up into SOFA. Drawn as
    # two plain segments plus one arrow so the path cannot be confused with the executor-to-logger
    # link. An earlier version routed it through the logger, which made the logger look like the
    # component driving the guidewire.
    ax.plot([8.95, 8.95], [1.08, 0.72], color="#333333", lw=0.9, zorder=1)
    ax.plot([8.95, 3.70], [0.72, 0.72], color="#333333", lw=0.9, zorder=1)
    ax.annotate("", xy=(3.70, 2.77), xytext=(3.70, 0.72), zorder=1,
                arrowprops=dict(arrowstyle="->", color="#333333", lw=0.9))
    ax.text(6.32, 0.80, "guidewire actuation", ha="center", va="bottom", fontsize=6,
            color="#666666", style="italic")

    # Solver constants only. The step budget is NOT stated here: it differs between arms in A2
    # (CORRECTIONS.md, C13), so a single number would be false. See Methods.
    ax.text(5.0, 0.24,
            r"$N_{\rm ep}=25$ per arm   |   dt = 0.001 s   |   contact distance = 0.3 mm"
            "   |   step limit: see Methods",
            ha="center", va="center", fontsize=6.5, color="#444444", style="italic")

    for fmt in ("pdf", "eps"):
        fig.savefig(OUT / f"Fig1.{fmt}")
        print(f"wrote Fig1.{fmt}  (vector, fonts embedded)")
    save_raster_600(fig, "Fig1")
    plt.close(fig)


def fig2() -> None:
    frames = {
        "wire_only": RUNS / "2026-06-28_18-03-27" / "arm_coronary_wire_only" / "ep01_step20.png",
        "overlay": RUNS / "2026-06-28_19-29-24" / "arm_coronary_overlay" / "ep01_step20.png",
        "contrast": RUNS / "2026-06-28_21-00-25" / "arm_coronary_contrast" / "ep01_step20.png",
        "biplane": PILOT / "biplane_preview" / "pair_wire_only.png",
    }
    missing = [str(p) for p in frames.values() if not p.exists()]
    if missing:
        raise FileNotFoundError("Required source frame(s) not found:\n  " + "\n  ".join(missing))

    img = {k: np.array(Image.open(p).convert("RGB")) for k, p in frames.items()}

    # The biplane preview is a 1034x556 composite of two 512x512 renders, each wrapped in black
    # bars that the preview burned in: the projection above, and below it
    # "step=19 dist_to_target=2.4mm seed=2001". Both bars are cropped away. The panel titles
    # already give the projections, and a distance printed into artwork is a number that no
    # longer traces to the manifest, which is exactly what the build exists to prevent.
    bp = img["biplane"]
    bp_ap, bp_lao = bp[24:536, 0:512, :], bp[24:536, 522:1034, :]
    for name, arr_ in (("biplane first view", bp_ap), ("biplane second view", arr_lao := bp_lao)):
        if arr_.shape[:2] != (512, 512):
            raise ValueError(f"{name} crop is {arr_.shape[:2]}, expected (512, 512)")

    def panel_grid(stem: str, panels: list, ncols: int, figsize) -> None:
        fig = plt.figure(figsize=figsize)
        gs = GridSpec(1, ncols, figure=fig, wspace=0.06,
                      left=0.01, right=0.99, top=0.88, bottom=0.02)
        for i, (arr_, title) in enumerate(panels):
            ax = fig.add_subplot(gs[0, i])
            # aspect="equal", not "auto". Every frame is a 512x512 render; the original
            # composition stretched them to fill non-square axes, distorting the anatomy.
            ax.imshow(arr_, aspect="equal", interpolation="nearest")
            ax.set_title(title, fontsize=6.5, pad=4, linespacing=1.3, color=C_DARK)
            ax.axis("off")
        fig.savefig(OUT / f"{stem}.pdf")
        print(f"wrote {stem}.pdf  (vector container; panel images are raster by nature)")
        save_raster_600(fig, stem)
        plt.close(fig)

    # MAIN-TEXT FIGURE 2: the two conditions this study actually compares, and nothing else.
    # The contrast and biplane renderings are exploratory conditions reported only in the
    # supplement, so putting them beside the comparison invited them to be read as part of it.
    panel_grid("Fig2", [
        (img["wire_only"], "(a) Wire-only\nAP-cranial 40 deg"),
        (img["overlay"], "(b) Vessel overlay\nAP-cranial 40 deg"),
    ], ncols=2, figsize=(6.85, 3.9))

    # SUPPLEMENTARY FIGURE S1: the exploratory conditions, moved out of the main text. No pixel
    # of any render is altered; only which panels sit in which figure has changed.
    panel_grid("FigS1", [
        (img["contrast"], "(a) Contrast\nAP-cranial 40 deg"),
        (bp_ap, "(b) Biplane, first view\nAP-cranial 40 deg"),
        (arr_lao, "(c) Biplane, second view\nLAO 60 deg / cranial 20 deg"),
    ], ncols=3, figsize=(6.85, 2.9))


def retire_superseded() -> None:
    """Remove the 300 dpi files these outputs replace, so only compliant artwork is submitted."""
    for name in ("Fig1.png", "Fig1.svg", "Fig2.png"):
        p = OUT / name
        if p.exists():
            p.unlink()
            print(f"removed superseded {name} (300 dpi; replaced by 600 dpi TIFF + vector)")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fig1()
    fig2()
    retire_superseded()
    return 0


if __name__ == "__main__":
    sys.exit(main())
