"""
run_ablation.py  --  Prompt-robustness ablation for VMR0066 coronary navigation.

3 prompt variants x 2 modes (wire_only, overlay) x 10 episodes = 60 episodes total.
Identical seeds, physics, and rendering across all variants. ONLY the system-prompt
and per-step user-message text differ.

Variants
  v1_current   full scaffolded prompt (study reference -- identical to run_coronary.py)
  v2_neutral   bare-minimum: action space + JSON format only; NO topology primer,
               NO retraction-budget rule, NO rotation rule, NO LM-bend-illusion warning
  v3_reworded  same strategic content as v1, rephrased and reordered throughout

Primary metric: LM-phase rotation rate (rotate-steps / total-LM-steps), overlay vs
wire_only, for each variant. Key question: does overlay > wire_only on this metric
across all three variants?

Usage:
    . D:\\steve\\activate_steve.ps1
    $env:ANTHROPIC_API_KEY = "sk-..."
    python D:\\steve\\pilot\\run_ablation.py
    python D:\\steve\\pilot\\run_ablation.py --analyze-only   # skip runs, just print table
"""

import argparse
import base64
import datetime
import json
import math
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageChops
import pyvista as pv
from scipy.spatial import cKDTree

# ── Paths (identical to run_coronary.py) ──────────────────────────────────────
PILOT_ROOT = Path(r"D:\steve\pilot")
STEVE_ROOT = Path(r"D:\steve\stEVE")
VTP_PATH   = STEVE_ROOT / "coronary_fixture" / "clipped_left.vtp"
MESH_PATH  = STEVE_ROOT / "coronary_fixture" / "clipped_left.obj"
PATH_DIR   = STEVE_ROOT / ".data" / "vmr" / "0066_H_CORO_H" / "Paths"

sys.path.insert(0, str(STEVE_ROOT))

import eve
from eve.intervention.fluoroscopy.pillow import Pillow
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from eve.util.coordtransform import vessel_cs_to_tracking3d, tracking3d_to_2d

from coronary_fixture.pth_centerlines import left_coronary_branches
from coronary_fixture.coronary_sim import CoronaryBeamAdapter

# ── Constants (identical to run_coronary.py) ──────────────────────────────────
MODEL                      = "claude-sonnet-4-6"
TRANS_LIMIT                = 50.0
ROT_LIMIT                  = 3.14159
RETRACTION_BUDGET          = 2
MAX_RESET_TRIES            = 3
XTIP_HEALTHY_MAX           = 10.0
PROXIMITY_GATE_DIST_MM     = 25.0
PROXIMITY_GATE_ADV_DEFAULT = 35.0
IMAGE_ROT_ZX               = [0, -40]
IMAGE_SIZE                 = (512, 512)
VESSEL_FILL                = {"overlay": 90}
WIRE_FILL_BY_MODE          = {"wire_only": 40, "overlay": 40}
BG_FILL                    = 255

VALID_INTENTS = {"advance", "retract", "rotate_cw", "rotate_ccw", "hold"}

# Ablation-specific seeds — distinct from main study (2001-2276) and ASOCA (3001+, 4001+)
# Extended to 25 for v1_current n=25 primary run (episodes 11-25 appended via --episode-offset 10 --episodes 15)
ABLATION_SEEDS = [5001 + i * 11 for i in range(25)]

N_EPISODES = 10
N_STEPS    = 60   # same as main VMR0066 study


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT VARIANTS
# Only the system prompt and user-message text differ across variants.
# Physics, seeds, rendering: locked identical.
# ══════════════════════════════════════════════════════════════════════════════

# ── V1: CURRENT (study reference — verbatim from run_coronary.py) ─────────────
SYSTEM_PROMPT_V1 = (
    "You are operating a guidewire inside a coronary artery. "
    "You receive ONE fluoroscopy image per step: a monoplane AP Cranial 40° view "
    "(anterior-posterior projection, cranially angulated 40 degrees).\n\n"

    "WHAT YOU SEE:\n"
    "  - The guidewire appears as a dark curved line.\n"
    "  - Depending on the imaging condition, the coronary vessel anatomy may "
    "appear as gray banding (explicit vessel map) or a faint shadow (angiographic). "
    "Navigate toward the mid-LAD target regardless of which condition is active.\n"
    "  - There is no visible target marker in the image. "
    "Use the distance and trend values in the user message to track progress.\n\n"

    "CRITICAL VASCULAR TOPOLOGY -- read this before every decision:\n\n"

    "ROUTE:\n"
    "  The wire enters the coronary circulation at the LEFT coronary ostium -- "
    "a small opening on the anterior surface of the aortic root. "
    "From the ostium, the wire must traverse:\n"
    "    1. LEFT MAIN (LM) trunk -- a short (~15-20mm) artery; divides at its "
    "distal end into LAD and LCX.\n"
    "    2. LAD (Left Anterior Descending) -- continues from the LM bifurcation "
    "superiorly along the anterior interventricular groove, curving toward the "
    "cardiac apex. In this AP Cranial 40 deg view, the LAD travels in the "
    "leftward-upward direction from the bifurcation before arcing toward "
    "the apex.\n"
    "    3. Mid-LAD target -- approximately the midpoint of the LAD proper.\n"
    "  The LCX (Left Circumflex) is the WRONG branch -- it departs the LM "
    "bifurcation inferolaterally (curves downward in this view).\n"
    "  The wire is trapped inside the vessel. It can only move FORWARD along "
    "the path (advance) or BACKWARD along the path it came from (retract). "
    "It cannot jump to the target in a straight line.\n\n"

    "THE EARLY-PHASE DISTANCE INCREASE -- the most common source of wrong decisions:\n"
    "  During the first ~6 advancing steps, as the wire traverses the curved "
    "LM trunk, the 3D distance from the wire tip to the mid-LAD target "
    "INCREASES before beginning to decrease. "
    "Validated values: distance goes from ~85mm at step 1 to ~89mm at step 5, "
    "then begins dropping steadily.\n"
    "  WHY: The LM trunk curves away from the mid-LAD target in 3D space. "
    "Advancing along the LM initially carries the tip geometrically farther "
    "from the target before the wire rounds the LM-LAD junction (~steps 6-8) "
    "and enters the LAD proper. After that, every correct advance step reduces "
    "the distance.\n"
    "  RULE: NEVER retract because the distance metric is increasing. "
    "Retracting during LM traversal (distance above ~75mm) pulls the wire "
    "back to the ostium and wastes the retraction budget on a correctly "
    "progressing wire.\n\n"

    "BRANCH DECISION AT THE LM BIFURCATION:\n"
    "  - ADVANCE into the LAD -- it continues in the superior/leftward direction.\n"
    "  - If the wire mistakenly enters the LCX (the distance stalls or increases "
    "AFTER the LM phase, AND the wire appears to curve downward/rightward away "
    "from the expected LAD path), retract to the bifurcation, then use rotation "
    "to redirect the tip toward the LAD before advancing again.\n"
    "  - This is the ONE correct use of retraction. No other situation justifies "
    "consuming the retraction budget.\n\n"

    "ROTATIONAL CONTROL:\n"
    "  - When advancing produces no progress (distance fails to decrease for "
    "2+ consecutive advance steps), ROTATE before advancing again.\n"
    "  - Use translate=0, rotation=+/-1.0 to +/-2.0 rad/s for 30-60 degree "
    "turns. Smaller values for fine adjustment near the target.\n"
    "  - Rotation is NOT retraction and does not consume the retraction budget.\n"
    "  - If THREE advance steps in a row produce no progress, you MUST rotate "
    "on the next step.\n\n"
    "  PROXIMITY GATE: When the user message reports "
    "'Distance trend: decreasing' AND the current distance is under "
    f"{PROXIMITY_GATE_DIST_MM:.0f}mm, do NOT rotate. The wire is on final "
    "approach and the trajectory is already working. Rotating at this point "
    "disrupts a stable approach and causes regression. "
    "Output advance.\n\n"

    f"RETRACTION BUDGET -- {RETRACTION_BUDGET} retractions per episode:\n"
    "  - Each step, the user message tells you how many remain.\n"
    "  - Retract ONLY when the wire clearly entered the LCX instead of the LAD.\n"
    "  - Do NOT retract because distance is increasing in the first ~6 steps -- "
    "that is normal LM traversal, not the wrong branch.\n"
    "  - If budget is 0, advance or rotate instead of retracting.\n\n"

    "Navigate the wire tip to the mid-LAD target.\n\n"
    "Output ONLY a single JSON object -- no text before or after it:\n"
    '{"tip_location_statement": "<which vessel/branch the wire appears to be in>", '
    '"target_location_statement": "<where the target is, inferred from anatomy and distance>", '
    '"intended_direction": "<advance|retract|rotate_cw|rotate_ccw|hold>", '
    '"safety_rationale": "<safety concern or none>", '
    '"action": {"translation": <float>, "rotation": <float>}}\n\n'
    "Action semantics:\n"
    "  translation : positive = advance wire forward, negative = retract.\n"
    "                Range [-50.0, 50.0] mm/s.\n"
    "  rotation    : steers the tip. Positive = clockwise, negative = counter-clockwise.\n"
    "                Range [-3.14, 3.14] rad/s.\n"
    "  For a pure rotation step: set translation=0, rotation=+/-1.0 to +/-2.0.\n"
    "REQUIRED -- intended_direction MUST be consistent with the action:\n"
    "  advance    -> translation > 0\n"
    "  retract    -> translation < 0\n"
    "  rotate_cw  -> rotation > 0  (translation near 0)\n"
    "  rotate_ccw -> rotation < 0  (translation near 0)\n"
    "  hold       -> translation and rotation both near zero"
)


# ── V2: NEUTRAL — bare minimum, no scaffolding ────────────────────────────────
SYSTEM_PROMPT_V2 = (
    "You are controlling a guidewire inside a coronary artery. "
    "You receive a fluoroscopy image each step. "
    "Navigate the guidewire tip to the target.\n\n"

    "Output ONLY a single JSON object -- no text before or after it:\n"
    '{"tip_location_statement": "<where the wire tip appears to be>", '
    '"target_location_statement": "<where the target appears to be>", '
    '"intended_direction": "<advance|retract|rotate_cw|rotate_ccw|hold>", '
    '"safety_rationale": "<safety concern or none>", '
    '"action": {"translation": <float>, "rotation": <float>}}\n\n'
    "Action semantics:\n"
    "  translation : positive = advance wire forward, negative = retract.\n"
    "                Range [-50.0, 50.0] mm/s.\n"
    "  rotation    : steers the tip. Positive = clockwise, negative = counter-clockwise.\n"
    "                Range [-3.14, 3.14] rad/s.\n"
    "REQUIRED -- intended_direction MUST be consistent with the action:\n"
    "  advance    -> translation > 0\n"
    "  retract    -> translation < 0\n"
    "  rotate_cw  -> rotation > 0  (translation near 0)\n"
    "  rotate_ccw -> rotation < 0  (translation near 0)\n"
    "  hold       -> translation and rotation both near zero"
)


# ── V3: REWORDED — same content as V1, different wording and structure ─────────
SYSTEM_PROMPT_V3 = (
    "You are the operator of a coronary guidewire system. "
    "A fluoroscopy image arrives each step — an AP Cranial 40° monoplane view. "
    "Your task is to steer the wire tip to the mid-LAD target.\n\n"

    "WHAT THE IMAGE SHOWS:\n"
    "  The wire appears as a dark curved line on the grayscale image. "
    "The vessel anatomy may be rendered as gray banding (vessel map) or an "
    "angiographic shadow depending on imaging mode. "
    "No target marker is visible; use the numerical distance and trend "
    "reported each step.\n\n"

    "ANATOMY: LEFT CORONARY INSERTION ROUTE\n"
    "  The wire enters through the LEFT coronary ostium on the aortic root. "
    "The path to the mid-LAD target passes through three segments:\n"
    "    1. LEFT MAIN (LM) -- a short trunk (~15-20 mm) branching into LAD "
    "and LCX at its distal end.\n"
    "    2. LAD (Left Anterior Descending) -- departs the LM bifurcation "
    "traveling superiorly/leftward along the anterior groove, curving "
    "toward the cardiac apex.\n"
    "    3. MID-LAD -- the target, approximately halfway along the LAD.\n"
    "  The LCX (Left Circumflex) is the incorrect branch -- it departs "
    "the bifurcation inferolaterally, curving downward in this view.\n"
    "  The wire is constrained inside the vessel lumen and can only advance "
    "or retract along the path it already occupies.\n\n"

    "DISTANCE BEHAVIOUR IN THE LM PHASE -- read carefully before acting:\n"
    "  As the wire advances through the curved LM trunk, the 3D Euclidean "
    "distance to the mid-LAD target will RISE for approximately the first "
    "6 steps. Measured values: ~85 mm at insertion, rising to ~89 mm at "
    "step 5, then declining steadily once the wire rounds the LM-LAD "
    "junction at steps 6-8.\n"
    "  This rise is caused by the LM's curvature carrying the tip away from "
    "the target in 3D space before reaching the bifurcation. It does not "
    "indicate a wrong position.\n"
    "  Rule: never retract in response to a rising distance while still in "
    "the LM phase (distance above ~75 mm). Retraction here pulls a "
    "correctly-advancing wire back to the ostium and wastes budget.\n\n"

    "STEERING THE WIRE:\n"
    "  When advancing fails to reduce the distance for 2 or more consecutive "
    "steps, rotate the tip before advancing again. Use rotation=+/-1.0 to "
    "+/-2.0 rad/s with translation=0 for 30-60 degree turns; use smaller "
    "values for fine adjustments near the target.\n"
    "  If THREE consecutive advance steps fail to reduce distance, you must "
    "rotate on the following step.\n"
    f"  Final-approach rule: when the distance is below {PROXIMITY_GATE_DIST_MM:.0f} mm "
    "AND decreasing, do not rotate. The wire is on a stable final approach "
    "and rotation at this point causes regression. Output advance only.\n\n"

    "BRANCH SELECTION AT THE BIFURCATION:\n"
    "  Steer into the LAD, which departs superiorly/leftward. "
    "If the distance stalls or increases after the LM phase AND the wire "
    "appears to curve downward/rightward, the wire likely entered the LCX. "
    "Retract to the bifurcation, rotate to redirect toward the LAD, then "
    "advance again. This is the only justified reason to retract.\n\n"

    f"RETRACTION ALLOWANCE -- {RETRACTION_BUDGET} retractions per episode:\n"
    "  Each step message shows the remaining allowance. "
    "Spend a retraction only to escape the LCX. "
    "Do not retract during LM traversal or for a brief stall in the LAD. "
    "If the allowance reaches zero, advance or rotate instead.\n\n"

    "Navigate the wire tip to the mid-LAD target.\n\n"
    "Output ONLY a single JSON object -- no text before or after it:\n"
    '{"tip_location_statement": "<which vessel/branch the wire appears to be in>", '
    '"target_location_statement": "<where the target is, inferred from anatomy and distance>", '
    '"intended_direction": "<advance|retract|rotate_cw|rotate_ccw|hold>", '
    '"safety_rationale": "<safety concern or none>", '
    '"action": {"translation": <float>, "rotation": <float>}}\n\n'
    "Action semantics:\n"
    "  translation : positive = advance wire forward, negative = retract.\n"
    "                Range [-50.0, 50.0] mm/s.\n"
    "  rotation    : steers the tip. Positive = clockwise, negative = counter-clockwise.\n"
    "                Range [-3.14, 3.14] rad/s.\n"
    "  For a pure rotation step: set translation=0, rotation=+/-1.0 to +/-2.0.\n"
    "REQUIRED -- intended_direction MUST be consistent with the action:\n"
    "  advance    -> translation > 0\n"
    "  retract    -> translation < 0\n"
    "  rotate_cw  -> rotation > 0  (translation near 0)\n"
    "  rotate_ccw -> rotation < 0  (translation near 0)\n"
    "  hold       -> translation and rotation both near zero"
)


# ── Per-step user messages (one function per variant) ─────────────────────────

def _dist_trend(dist_history, dist_obs):
    if len(dist_history) < 2:
        return "unknown"
    change = dist_obs - dist_history[-2]
    if change < -1.0: return "decreasing"
    if change >  1.0: return "increasing"
    return "stable"


def _gate_active(dist_obs, trend):
    return dist_obs < PROXIMITY_GATE_DIST_MM and trend == "decreasing"


def user_msg_v1(retractions_remaining, no_progress_advances, current_dist, dist_trend):
    """Full scaffolded message — identical to run_coronary.py."""
    parts = [
        "Monoplane AP Cranial 40 deg view.",
        f"Retractions remaining: {retractions_remaining} of {RETRACTION_BUDGET}.",
        f"Consecutive no-progress advance steps: {no_progress_advances}.",
        f"Current distance to mid-LAD target: {current_dist:.1f} mm.",
        f"Distance trend (last 3 steps): {dist_trend}.",
    ]
    if no_progress_advances >= 3:
        parts.append("You MUST rotate on this step.")
    if _gate_active(current_dist, dist_trend):
        parts.append(
            f"PROXIMITY GATE ACTIVE: distance is decreasing and under "
            f"{PROXIMITY_GATE_DIST_MM:.0f}mm -- do NOT rotate, output advance."
        )
    parts.append("Navigate the wire tip to the mid-LAD target.")
    return " ".join(parts)


def user_msg_v2(retractions_remaining, no_progress_advances, current_dist, dist_trend):
    """Bare-minimum message — just image label, distance, and trend. No rules."""
    return (
        f"Fluoroscopy image attached. "
        f"Current distance to target: {current_dist:.1f} mm. "
        f"Distance trend: {dist_trend}."
    )


def user_msg_v3(retractions_remaining, no_progress_advances, current_dist, dist_trend):
    """Reworded message — same information as v1, different phrasing."""
    parts = [
        "AP Cranial 40° fluoroscopy image attached.",
        f"Retraction budget remaining: {retractions_remaining}/{RETRACTION_BUDGET}.",
        f"Advance steps without distance reduction: {no_progress_advances}.",
        f"Tip-to-target distance: {current_dist:.1f} mm.",
        f"Recent distance trend: {dist_trend}.",
    ]
    if no_progress_advances >= 3:
        parts.append(
            "Three consecutive advance steps produced no reduction — rotate this step."
        )
    if _gate_active(current_dist, dist_trend):
        parts.append(
            f"FINAL APPROACH ACTIVE: distance is under {PROXIMITY_GATE_DIST_MM:.0f} mm "
            f"and decreasing. Maintain advance — do not rotate."
        )
    parts.append("Steer the wire tip to the mid-LAD target.")
    return " ".join(parts)


# ── V4: GENTLE REWORD — same structure/rules as V1, minimal surface changes ───
# V3 collapsed navigation by reordering sections and softening key rule phrasing.
# V4 keeps V1's exact section order and rule strength; only sentence-level wording differs.
SYSTEM_PROMPT_V4 = (
    "You are guiding a coronary guidewire through the left coronary artery. "
    "At each step you receive a monoplane AP Cranial 40° fluoroscopy image.\n\n"

    "VISUAL INFORMATION:\n"
    "  - The wire appears as a dark curved line in the image.\n"
    "  - The vessel anatomy may be shown as gray banding (explicit vessel map) or a "
    "faint angiographic shadow, depending on the imaging condition. "
    "Navigate to the mid-LAD target under either condition.\n"
    "  - No target marker is visible. Use the numeric distance and trend in each "
    "message to track progress.\n\n"

    "VASCULAR ANATOMY -- read this before every action:\n\n"

    "PATH TO TARGET:\n"
    "  The wire enters at the LEFT coronary ostium on the anterior aortic root. "
    "It must pass through:\n"
    "    1. LEFT MAIN (LM) trunk -- a short vessel (~15-20mm) that divides at its "
    "distal end into the LAD and LCX.\n"
    "    2. LAD (Left Anterior Descending) -- exits the LM bifurcation heading "
    "superiorly along the anterior interventricular groove, curving toward the cardiac "
    "apex. In the AP Cranial 40 deg view it travels leftward-upward from the "
    "bifurcation before arcing apically.\n"
    "    3. Mid-LAD target -- the midpoint of the LAD.\n"
    "  The LCX (Left Circumflex) is the wrong branch -- it departs the bifurcation "
    "heading inferolaterally (downward in this view).\n"
    "  The wire cannot leave the vessel; it can only advance forward along its current "
    "path or retract backward along the path it came from.\n\n"

    "THE DISTANCE INCREASE IN THE LM PHASE -- the most common cause of wrong actions:\n"
    "  During the first ~6 advance steps, while traversing the curved LM trunk, the 3D "
    "distance to the mid-LAD target will INCREASE before it begins to fall. "
    "Confirmed measurements: ~85mm at step 1, rising to ~89mm at step 5, then "
    "declining steadily after the wire reaches the LM-LAD junction around steps 6-8.\n"
    "  WHY: The LM curves away from the target in 3D space; advancing through it "
    "initially carries the tip farther from the target before the wire rounds the "
    "LM-LAD junction and enters the LAD. After that, each correct advance reduces "
    "the distance.\n"
    "  RULE: NEVER retract because the distance is rising. "
    "Retracting during LM traversal (distance above ~75mm) pulls a correctly-advancing "
    "wire back to the ostium and wastes the retraction budget.\n\n"

    "BRANCH CHOICE AT THE LM BIFURCATION:\n"
    "  - Advance into the LAD -- it continues superiorly and leftward.\n"
    "  - If the wire enters the LCX by mistake (distance stalls or rises AFTER the LM "
    "phase, AND the wire curves downward/rightward away from the expected LAD path), "
    "retract to the bifurcation, rotate to redirect the tip toward the LAD, then "
    "advance again.\n"
    "  - This is the one correct use of the retraction budget. Nothing else justifies "
    "a retraction.\n\n"

    "ROTATION STRATEGY:\n"
    "  - When advancing produces no progress (distance does not decrease for 2+ "
    "consecutive advance steps), rotate before advancing again.\n"
    "  - For steering: set translation=0, rotation=+/-1.0 to +/-2.0 rad/s for "
    "30-60 degree turns. Use smaller values near the target.\n"
    "  - Rotation does not count against the retraction budget.\n"
    "  - After THREE consecutive no-progress advance steps, you MUST rotate on "
    "the next step.\n\n"
    "  PROXIMITY GATE: When the message reports 'Distance trend: decreasing' AND "
    f"the distance is under {PROXIMITY_GATE_DIST_MM:.0f}mm, do NOT rotate. "
    "The approach is working and rotation here causes regression. Output advance.\n\n"

    f"RETRACTION BUDGET -- {RETRACTION_BUDGET} retractions per episode:\n"
    "  - The remaining count appears in every message.\n"
    "  - Retract only when the wire has clearly entered the LCX.\n"
    "  - Do NOT retract because distance is rising in the first ~6 steps -- that is "
    "normal LM traversal, not wrong-branch entry.\n"
    "  - When budget reaches 0, advance or rotate instead.\n\n"

    "Navigate the wire tip to the mid-LAD target.\n\n"
    "Output ONLY a single JSON object -- no text before or after it:\n"
    '{"tip_location_statement": "<which vessel/branch the wire appears to be in>", '
    '"target_location_statement": "<where the target is, inferred from anatomy and distance>", '
    '"intended_direction": "<advance|retract|rotate_cw|rotate_ccw|hold>", '
    '"safety_rationale": "<safety concern or none>", '
    '"action": {"translation": <float>, "rotation": <float>}}\n\n'
    "Action semantics:\n"
    "  translation : positive = advance wire forward, negative = retract.\n"
    "                Range [-50.0, 50.0] mm/s.\n"
    "  rotation    : steers the tip. Positive = clockwise, negative = counter-clockwise.\n"
    "                Range [-3.14, 3.14] rad/s.\n"
    "  For a pure rotation step: set translation=0, rotation=+/-1.0 to +/-2.0.\n"
    "REQUIRED -- intended_direction MUST be consistent with the action:\n"
    "  advance    -> translation > 0\n"
    "  retract    -> translation < 0\n"
    "  rotate_cw  -> rotation > 0  (translation near 0)\n"
    "  rotate_ccw -> rotation < 0  (translation near 0)\n"
    "  hold       -> translation and rotation both near zero"
)


def user_msg_v4(retractions_remaining, no_progress_advances, current_dist, dist_trend):
    """Gently reworded message — same information and rules as v1, minor phrasing only."""
    parts = [
        "AP Cranial 40 deg monoplane view.",
        f"Retraction budget remaining: {retractions_remaining} of {RETRACTION_BUDGET}.",
        f"Consecutive no-progress advance steps: {no_progress_advances}.",
        f"Distance to mid-LAD target: {current_dist:.1f} mm.",
        f"Distance trend (last 3 steps): {dist_trend}.",
    ]
    if no_progress_advances >= 3:
        parts.append("THREE consecutive no-progress steps -- you MUST rotate on this step.")
    if _gate_active(current_dist, dist_trend):
        parts.append(
            f"PROXIMITY GATE ACTIVE: distance under {PROXIMITY_GATE_DIST_MM:.0f}mm "
            f"and decreasing -- do NOT rotate, output advance."
        )
    parts.append("Advance the wire tip to the mid-LAD target.")
    return " ".join(parts)


VARIANTS = [
    {
        "key":         "v1_current",
        "label":       "V1 current (scaffolded)",
        "prompt":      SYSTEM_PROMPT_V1,
        "user_msg_fn": user_msg_v1,
    },
    {
        "key":         "v2_neutral",
        "label":       "V2 neutral  (bare-min)",
        "prompt":      SYSTEM_PROMPT_V2,
        "user_msg_fn": user_msg_v2,
    },
    {
        "key":         "v3_reworded",
        "label":       "V3 reworded (broken)",
        "prompt":      SYSTEM_PROMPT_V3,
        "user_msg_fn": user_msg_v3,
    },
    {
        "key":         "v4_gentle",
        "label":       "V4 gentle   (reword)",
        "prompt":      SYSTEM_PROMPT_V4,
        "user_msg_fn": user_msg_v4,
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT (identical to run_coronary.py — no changes)
# ══════════════════════════════════════════════════════════════════════════════

class PillowTracking(Pillow, TrackingOnly):
    def __init__(self, image_size, simulation, vessel_tree,
                 wire_diameter=0.89, image_frequency=7.5,
                 image_rot_zx=(0.0, 0.0), image_center=None, field_of_view=None):
        TrackingOnly.__init__(self, simulation=simulation, vessel_tree=vessel_tree,
                              image_frequency=image_frequency, image_rot_zx=image_rot_zx,
                              image_center=image_center, field_of_view=field_of_view)
        if isinstance(image_size, int):
            image_size = (image_size, image_size)
        self.image_size               = image_size
        self._wire_diameter           = wire_diameter
        self._image_mode              = "L"
        self.low = 0; self.high = 255
        self._tracking_to_image_factor = 0
        self._tracking_offset          = [0, 0]
        self._image_offset             = [0, 0]
        self._image                    = None

    def reset(self, episode_nr=0):
        TrackingOnly.reset(self, episode_nr)
        Pillow.reset(self, episode_nr)
        self.step()

    def step(self):
        trackings = self.device_trackings2d
        noise_img = Image.effect_noise(size=self.image_size, sigma=5)
        phys_img  = self._render(trackings, [self._wire_diameter])
        self._image = np.asarray(ImageChops.darker(phys_img, noise_img), dtype=np.uint8)

    @property
    def image(self): return self._image

    @property
    def image_space(self):
        import gymnasium as gym
        return gym.spaces.Box(0, 255, self.image_size, dtype=np.uint8)


def _coords_to_px(coords_2d, fluoro):
    offset     = np.asarray(fluoro._tracking_offset, dtype=np.float64)
    img_offset = np.asarray(fluoro._image_offset,    dtype=np.float64)
    H          = fluoro.image_size[1]
    px = (coords_2d + offset) * fluoro._tracking_to_image_factor + img_offset
    px = px.copy()
    px[:, 1] = -px[:, 1] + H
    return np.round(px).astype(np.int32)


def precompute_binary_mask(fluoro, vtp_path):
    t0   = time.perf_counter()
    mesh = pv.read(str(vtp_path)).triangulate()
    verts  = np.asarray(mesh.points, dtype=np.float64)
    v3d    = vessel_cs_to_tracking3d(verts, fluoro.image_rot_zx,
                                     fluoro.image_center, fluoro.field_of_view)
    v2d    = tracking3d_to_2d(v3d)
    vpx    = _coords_to_px(v2d, fluoro)
    raw    = np.asarray(mesh.faces, dtype=np.int32)
    faces  = raw.reshape(-1, 4)[:, 1:]

    mask = Image.new("L", fluoro.image_size, 255)
    draw = ImageDraw.Draw(mask)
    for tri in faces:
        pts = [(int(vpx[i, 0]), int(vpx[i, 1])) for i in tri]
        draw.polygon(pts, fill=0)

    arr      = np.asarray(mask, dtype=np.uint8)
    n_vessel = int(np.sum(arr == 0))
    print(f"  Vessel mask: {len(faces)} triangles -> {n_vessel} px "
          f"({100*n_vessel/arr.size:.1f}%)  {time.perf_counter()-t0:.2f}s")
    return arr


def render_frame(fluoro, binary_mask, mode):
    if mode == "wire_only":
        return fluoro.image

    fill = VESSEL_FILL[mode]
    vessel_arr = np.where(binary_mask == 0, fill, BG_FILL).astype(np.uint8)
    base = Image.fromarray(vessel_arr)
    draw = ImageDraw.Draw(base)

    for tracking_2d in fluoro.device_trackings2d:
        if len(tracking_2d) < 2:
            continue
        wire_px = fluoro._coord_transform_tracking_to_image(tracking_2d)
        w = max(2, int(fluoro._wire_diameter * fluoro._tracking_to_image_factor))
        draw.line(wire_px, fill=WIRE_FILL_BY_MODE.get(mode, 40), width=w)

    noise = Image.effect_noise(size=fluoro.image_size, sigma=5)
    return np.asarray(ImageChops.darker(base, noise), dtype=np.uint8)


def build_env(n_steps):
    branches, ins_pt, ins_dir = left_coronary_branches(str(PATH_DIR),
                                                        junction_radius_mm=3.0)
    lad     = next(b for b in branches if b.name == "lad")
    mid_idx = len(lad.coordinates) // 2
    mid_lad = lad.coordinates[mid_idx].copy()

    vt = FromMesh(
        mesh=str(MESH_PATH),
        insertion_position=tuple(ins_pt.tolist()),
        insertion_direction=tuple(ins_dir.tolist()),
        branch_list=branches, approx_branch_radii=2.5,
        scaling_xyz=None, rotation_yzx_deg=None,
        rotate_branches=False, rotate_ip=False,
    )

    device = eve.intervention.device.JShaped(tip_radius=1.5, tip_angle=0.2 * math.pi)
    sim    = CoronaryBeamAdapter(friction=0.001, dt_simulation=0.001, max_it=2000)
    fluoro = PillowTracking(image_size=IMAGE_SIZE, simulation=sim, vessel_tree=vt,
                            wire_diameter=0.89, image_frequency=7.5,
                            image_rot_zx=IMAGE_ROT_ZX)
    target = BranchIndex(vessel_tree=vt, fluoroscopy=fluoro,
                         threshold=5.0, branch="lad", idx=mid_idx)
    intvn  = eve.intervention.MonoPlaneStatic(
        vessel_tree=vt, devices=[device], simulation=sim,
        fluoroscopy=fluoro, target=target)
    start  = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf     = eve.pathfinder.BruteForceBFS(intervention=intvn)
    pos    = eve.observation.wrapper.NormalizeTracking2DEpisode(
        eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)
    obs    = eve.observation.ObsDict({"pos": pos})
    rew    = eve.reward.TargetReached(intervention=intvn, factor=1.0)
    env    = eve.Env(
        intervention=intvn, observation=obs, reward=rew,
        terminal=eve.terminal.TargetReached(intervention=intvn),
        truncation=eve.truncation.MaxSteps(n_steps),
        visualisation=None, start=start, pathfinder=pf)

    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}
    return env, sim, fluoro, branch_kds, mid_lad


def safe_reset(env, sim, ep, seed):
    for attempt in range(1, MAX_RESET_TRIES + 1):
        if (hasattr(sim, 'reset_devices') and
                getattr(sim, '_instruments_combined', None) is not None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)

        xtip = float(sim.inserted_lengths[0])
        tip  = np.array(sim.dof_positions[0], dtype=float)
        if np.any(np.isnan(tip)) or np.any(np.isinf(tip)):
            print(f"    [RESET] attempt {attempt}: NaN/Inf tip -- retrying"); continue
        if xtip > XTIP_HEALTHY_MAX:
            print(f"    [RESET] attempt {attempt}: xtip={xtip:.2f}mm too high -- retrying"); continue

        env.step(np.array([[0.0, 0.0]]))
        if np.any(np.isnan(np.array(sim.dof_positions[0], dtype=float))):
            print(f"    [RESET] attempt {attempt}: zero-action NaN -- retrying"); continue

        if (hasattr(sim, 'reset_devices') and
                getattr(sim, '_instruments_combined', None) is not None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)
        tip_f  = np.array(sim.dof_positions[0], dtype=float)
        xtip_f = float(sim.inserted_lengths[0])
        print(f"    [RESET] OK (attempt {attempt}): xtip={xtip_f:.2f}mm")
        return True, tip_f, xtip_f, attempt

    print(f"    [RESET] FAILED after {MAX_RESET_TRIES} attempts")
    return False, None, None, MAX_RESET_TRIES


def frame_to_png_b64(frame):
    img = Image.fromarray(frame, mode="L")
    buf = BytesIO(); img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def parse_action(raw_text):
    last_close = raw_text.rfind("}")
    if last_close == -1: return None, False
    depth = 0; first_open = -1
    for i in range(last_close, -1, -1):
        if raw_text[i] == "}": depth += 1
        elif raw_text[i] == "{":
            depth -= 1
            if depth == 0: first_open = i; break
    if first_open == -1: return None, False
    try:
        data   = json.loads(raw_text[first_open : last_close + 1])
        act    = data.get("action", {})
        trans  = float(np.clip(float(act.get("translation", 0.0)), -TRANS_LIMIT, TRANS_LIMIT))
        rot    = float(np.clip(float(act.get("rotation",    0.0)), -ROT_LIMIT,   ROT_LIMIT))
        intent = str(data.get("intended_direction", "")).lower().strip()
        if intent not in VALID_INTENTS: intent = "unknown"
        return {
            "tip_location_statement":    str(data.get("tip_location_statement",    "")),
            "target_location_statement": str(data.get("target_location_statement", "")),
            "intended_direction":        intent,
            "safety_rationale":          str(data.get("safety_rationale",          "")),
            "translation": trans, "rotation": rot,
        }, True
    except Exception:
        return None, False


def gt_tip(sim):   return np.array(sim.dof_positions[0], dtype=float)
def dist3d(a, b):  return float(np.linalg.norm(np.array(a) - np.array(b)))


def _blank():
    return {"tip_location_statement": "[PARSE FAIL]",
            "target_location_statement": "[PARSE FAIL]",
            "intended_direction": "unknown", "safety_rationale": "",
            "translation": 0.0, "rotation": 0.0}


# ══════════════════════════════════════════════════════════════════════════════
# RUN ARM (parameterised on prompt + user_msg_fn)
# ══════════════════════════════════════════════════════════════════════════════

def run_arm(client, env, sim, fluoro, binary_mask, mode, branch_kds, mid_lad,
            arm_dir, n_episodes, n_steps, seeds,
            system_prompt, user_msg_fn, prompt_key,
            episode_start=1, open_mode="w"):
    """
    episode_start : first episode number written to trace (use >1 to append a resume)
    open_mode     : "w" to overwrite, "a" to append to existing trace
    seeds         : must contain exactly n_episodes seeds, one per episode
    """
    arm_dir.mkdir(parents=True, exist_ok=True)
    tf_path = arm_dir / "trace.jsonl"

    ep_end = episode_start + n_episodes - 1
    print(f"\n{'='*70}")
    print(f"ARM: {prompt_key} / {mode}  (eps {episode_start}-{ep_end} x {n_steps} steps, "
          f"open_mode={open_mode})")
    print(f"{'='*70}")

    with open(tf_path, open_mode, encoding="utf-8") as tf:
        for ep_idx in range(n_episodes):
            ep   = episode_start + ep_idx
            seed = seeds[ep_idx]
            print(f"\n  [{mode.upper()}] Ep {ep}/{ep_end}  seed={seed}")

            try:
                reset_ok, _, xtip_start, reset_attempts = safe_reset(env, sim, ep, seed)
            except Exception as exc:
                print(f"  SKIPPED -- reset raised: {exc}"); continue
            if not reset_ok:
                print(f"  SKIPPED -- reset failed"); continue

            ep_steps = 0; ep_dists = []
            retractions_used = 0
            consecutive_no_progress = 0
            dist_history = []

            for step in range(1, n_steps + 1):
                tip_obs        = gt_tip(sim)
                dist_obs       = dist3d(tip_obs, mid_lad)
                tip_branch_obs = min(branch_kds,
                                     key=lambda n: branch_kds[n].query(tip_obs)[0])

                trend       = _dist_trend(dist_history, dist_obs)
                gate_active = _gate_active(dist_obs, trend)

                frame     = render_frame(fluoro, binary_mask, mode)
                b64_frame = frame_to_png_b64(frame)
                retractions_remaining = RETRACTION_BUDGET - retractions_used

                api_ok = True; raw_text = ""
                try:
                    response = client.messages.create(
                        model=MODEL, max_tokens=600, system=system_prompt,
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64",
                                                         "media_type": "image/png",
                                                         "data": b64_frame}},
                            {"type": "text", "text": user_msg_fn(
                                retractions_remaining, consecutive_no_progress,
                                dist_obs, trend)},
                        ]}],
                    )
                    raw_text = response.content[0].text
                except Exception as exc:
                    raw_text = f"[API ERROR] {exc}"; api_ok = False
                    print(f"    ep{ep:02d} s{step:02d} | API ERROR: {exc}")

                parsed, parse_ok = parse_action(raw_text)
                budget_enforced     = False
                gate_suppressed_rot = False

                if not parse_ok:
                    action_arr = np.array([[0.0, 0.0]]); parsed = _blank()
                    if api_ok:
                        print(f"    ep{ep:02d} s{step:02d} | PARSE FAIL  {raw_text[:60]!r}")
                else:
                    if parsed["translation"] < 0 and retractions_remaining <= 0:
                        parsed["translation"] = 0.0
                        if abs(parsed["rotation"]) < 0.05: parsed["rotation"] = 0.0
                        parsed["intended_direction"] = "hold"
                        budget_enforced = True

                    elif gate_active and parsed["intended_direction"] in ("rotate_cw", "rotate_ccw"):
                        parsed["rotation"]           = 0.0
                        parsed["translation"]        = PROXIMITY_GATE_ADV_DEFAULT
                        parsed["intended_direction"] = "advance"
                        gate_suppressed_rot = True
                        print(f"    ep{ep:02d} s{step:02d} | GATE FIRED "
                              f"dist={dist_obs:.1f}mm trend={trend}")

                    action_arr = np.array([[parsed["translation"], parsed["rotation"]]])
                    if parsed["translation"] < 0:
                        retractions_used += 1

                is_rotate = parse_ok and parsed["intended_direction"] in ("rotate_cw", "rotate_ccw")

                _, reward, terminal, truncation, _ = env.step(action_arr)

                tip_post = gt_tip(sim)
                if np.any(np.isnan(tip_post)):
                    print(f"    ep{ep:02d} s{step:02d} | NaN TIP -- ending episode"); break

                dist_post  = dist3d(tip_post, mid_lad)
                dist_delta = dist_post - dist_obs
                dist_history.append(dist_post)
                ep_dists.append(dist_post)

                if parse_ok and parsed["intended_direction"] == "advance":
                    consecutive_no_progress = (consecutive_no_progress + 1) if dist_delta >= 0 else 0
                else:
                    consecutive_no_progress = 0

                intent_str = parsed["intended_direction"] if parse_ok else "FAIL"
                print(f"    ep{ep:02d} s{step:02d} | T={parsed['translation']:+6.1f} "
                      f"R={parsed['rotation']:+5.2f} | intent={intent_str:10s} | "
                      f"branch={tip_branch_obs:12s} d={dist_post:6.1f}mm D={dist_delta:+5.1f}")

                row = dict(
                    prompt_variant=prompt_key, fluoro_mode=mode,
                    episode=ep, step=step, seed=seed,
                    raw_vlm_text=raw_text,
                    tip_location_statement=parsed["tip_location_statement"],
                    target_location_statement=parsed["target_location_statement"],
                    intended_direction=parsed["intended_direction"],
                    safety_rationale=parsed["safety_rationale"],
                    parsed_action={"translation": parsed["translation"],
                                   "rotation":    parsed["rotation"]},
                    gt_tip_obs=tip_obs.tolist(), gt_tip_pos=tip_post.tolist(),
                    gt_target_pos=mid_lad.tolist(),
                    tip_branch_obs=tip_branch_obs,
                    tip_target_dist=dist_post, dist_delta=dist_delta,
                    dist_obs_at_call=dist_obs, dist_trend=trend,
                    gate_active=gate_active, gate_suppressed_rotation=gate_suppressed_rot,
                    retractions_used_so_far=retractions_used,
                    consecutive_no_progress_advances=consecutive_no_progress,
                    budget_enforced=budget_enforced,
                    is_rotate_step=is_rotate,
                    outcome_reduced_dist=bool(dist_delta < 0),
                    raw_reward=float(reward), terminal=bool(terminal),
                    truncation=bool(truncation), parse_ok=parse_ok, api_ok=api_ok,
                    xtip_at_reset=xtip_start, reset_attempts=reset_attempts,
                )
                tf.write(json.dumps(row) + "\n"); tf.flush()

                ep_steps = step
                if terminal:
                    print(f"    >>> TARGET REACHED  step={step}  dist={dist_post:.1f}mm"); break
                if truncation:
                    print(f"    >>> Truncated  final_dist={dist_post:.1f}mm"); break

            ep_mean = float(np.mean(ep_dists)) if ep_dists else float("nan")
            print(f"  [{mode.upper()}] Ep {ep} done: {ep_steps} steps | "
                  f"mean_dist={ep_mean:.1f}mm | ret={retractions_used}/{RETRACTION_BUDGET}")


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS — compute per-arm metrics from trace files
# ══════════════════════════════════════════════════════════════════════════════

def _load_trace(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _lm_phase_rotation_rate(rows):
    """Fraction of LM-phase steps that are rotations. Also returns rot/mm."""
    lm_rows = [r for r in rows if r.get("tip_branch_obs") == "left_main"
               and r.get("parse_ok", True) and r.get("api_ok", True)]
    if not lm_rows:
        return float("nan"), float("nan"), 0, 0

    rot_steps = sum(1 for r in lm_rows if r.get("is_rotate_step", False))
    total_lm  = len(lm_rows)
    rot_frac  = rot_steps / total_lm if total_lm else float("nan")

    # mm of LM traversal = total reduction in tip_target_dist during LM phase
    lm_dist_traversed = sum(
        -r["dist_delta"] for r in lm_rows if r["dist_delta"] < 0
    )
    rot_per_mm = rot_steps / max(1.0, lm_dist_traversed)

    return rot_frac, rot_per_mm, rot_steps, total_lm


def _wrong_branch_rate(rows):
    clean = [r for r in rows if r.get("parse_ok", True) and r.get("api_ok", True)]
    if not clean: return float("nan"), 0, 0
    lcx_steps = sum(1 for r in clean if r.get("tip_branch_obs") == "lcx")
    return lcx_steps / len(clean), lcx_steps, len(clean)


def _steps_to_target(rows, n_episodes):
    eps = {}
    for r in rows:
        e = r["episode"]
        if e not in eps: eps[e] = []
        eps[e].append(r)

    success_steps = []
    n_success = 0
    for ep_rows in eps.values():
        last = ep_rows[-1]
        if last.get("terminal"):
            n_success += 1
            success_steps.append(last["step"])

    mean_steps = float(np.mean(success_steps)) if success_steps else float("nan")
    return n_success, mean_steps


def analyze_traces(run_dir):
    run_dir = Path(run_dir)
    print("\n" + "=" * 90)
    print("PROMPT-ROBUSTNESS ABLATION - RESULTS")
    print(f"Anatomy: VMR0066  Seeds: {ABLATION_SEEDS}")
    print("=" * 90)

    header = (
        f"{'Variant':<24} {'Mode':<10} {'LM-rot%':>8} {'LM rot/mm':>10} "
        f"{'Wrng-br%':>9} {'Success':>8} {'Steps-to-tgt':>13}"
    )
    print(header)
    print("-" * 90)

    results = {}
    for variant in VARIANTS:
        vkey  = variant["key"]
        vlabel = variant["label"]
        results[vkey] = {}
        for mode in ["wire_only", "overlay"]:
            trace_path = run_dir / vkey / mode / "trace.jsonl"
            if not trace_path.exists():
                print(f"  {vlabel:<24} {mode:<10}  [no trace]")
                continue

            rows = _load_trace(trace_path)
            rot_frac, rot_per_mm, rot_steps, lm_steps = _lm_phase_rotation_rate(rows)
            wb_rate, lcx_steps, total_steps            = _wrong_branch_rate(rows)
            n_success, mean_steps                      = _steps_to_target(rows, N_EPISODES)

            results[vkey][mode] = dict(
                rot_frac=rot_frac, rot_per_mm=rot_per_mm,
                wb_rate=wb_rate, n_success=n_success, mean_steps=mean_steps,
                rot_steps=rot_steps, lm_steps=lm_steps,
            )

            rot_frac_s   = f"{100*rot_frac:.1f}%" if not np.isnan(rot_frac) else "N/A"
            rot_per_mm_s = f"{rot_per_mm:.3f}"    if not np.isnan(rot_per_mm) else "N/A"
            wb_s         = f"{100*wb_rate:.1f}%"  if not np.isnan(wb_rate) else "N/A"
            suc_s        = f"{n_success}/{N_EPISODES}"
            steps_s      = f"{mean_steps:.1f}"    if not np.isnan(mean_steps) else "---"
            print(f"  {vlabel:<24} {mode:<10} {rot_frac_s:>8} {rot_per_mm_s:>10} "
                  f"{wb_s:>9} {suc_s:>8} {steps_s:>13}")

        print()

    # Overlay-effect summary: does overlay > wire_only on LM-rot% for all variants?
    print("=" * 90)
    print("OVERLAY EFFECT ON LM-PHASE ROTATION RATE (overlay minus wire_only)")
    print("-" * 90)
    effects = []
    for variant in VARIANTS:
        vkey   = variant["key"]
        vlabel = variant["label"]
        r      = results.get(vkey, {})
        wo     = r.get("wire_only", {})
        ov     = r.get("overlay",   {})
        if wo and ov and not np.isnan(wo["rot_frac"]) and not np.isnan(ov["rot_frac"]):
            delta = ov["rot_frac"] - wo["rot_frac"]
            direction = "overlay > wire_only" if delta > 0 else "wire_only >= overlay"
            effects.append(delta > 0)
            print(f"  {vlabel:<30} drot% = {100*delta:+.1f}pp  ({direction})")
        else:
            print(f"  {vlabel:<30} insufficient data")

    print()
    if all(effects):
        print("VERDICT: Overlay INCREASES LM-phase rotation across ALL prompt variants.")
        print("  Effect is a property of the visual condition, not the prompt formulation.")
        print("  Robust across N=3 variants including bare-minimum neutral prompt.")
    elif any(effects):
        n = sum(effects)
        print(f"VERDICT: Overlay increases rotation in {n}/3 variants.")
        print("  Effect is PARTIALLY prompt-dependent -- examine non-replicating variant.")
    else:
        print("VERDICT: Overlay does NOT robustly increase rotation.")
        print("  Effect is NOT confirmed as prompt-independent.")
    print("=" * 90)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-only", action="store_true",
                        help="Skip runs; compute metrics from existing traces only")
    parser.add_argument("--out", type=str,
                        default=r"D:\steve\pilot\runs\ablation_prompt_robustness")
    parser.add_argument("--variant", type=str, default=None,
                        help="Run a specific variant key (e.g. v3_reworded). "
                             "Default: all variants.")
    parser.add_argument("--mode", type=str, default=None,
                        choices=["wire_only", "overlay"],
                        help="Run a specific mode. Default: both.")
    parser.add_argument("--episode-offset", type=int, default=0,
                        help="Skip first N seeds; episodes numbered from offset+1. "
                             "Appends to existing trace.")
    parser.add_argument("--episodes", type=int, default=None,
                        help="Number of episodes to run (default: N_EPISODES=10).")
    parser.add_argument("--gate-test", action="store_true",
                        help="Run 3-episode gate test on wire_only before committing "
                             "to full run. Must specify --variant.")
    args = parser.parse_args()

    run_dir = Path(args.out)
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.analyze_only:
        analyze_traces(run_dir)
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set.")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    print("Building coronary environment (first SOFA init ~30s) ...")
    env, sim, fluoro, branch_kds, mid_lad = build_env(N_STEPS)

    print("env.reset() to initialise pixel transform ...")
    env.reset()

    print("Precomputing vessel mask ...")
    binary_mask = precompute_binary_mask(fluoro, VTP_PATH)

    # Resolve which variants and modes to run
    variant_keys = ([args.variant] if args.variant
                    else [v["key"] for v in VARIANTS])
    modes = ([args.mode] if args.mode else ["wire_only", "overlay"])
    n_eps = args.episodes if args.episodes is not None else N_EPISODES
    ep_offset = args.episode_offset
    episode_start = ep_offset + 1
    open_mode = "a" if ep_offset > 0 else "w"
    seeds_slice = ABLATION_SEEDS[ep_offset : ep_offset + n_eps]

    if args.gate_test:
        if not args.variant:
            sys.exit("--gate-test requires --variant")
        gate_eps   = 3
        gate_seeds = ABLATION_SEEDS[:gate_eps]
        variant    = next(v for v in VARIANTS if v["key"] == args.variant)
        arm_dir    = run_dir / variant["key"] / "wire_only"
        print(f"\nGATE TEST: {variant['key']} wire_only, {gate_eps} episodes")
        try:
            run_arm(client, env, sim, fluoro, binary_mask,
                    "wire_only", branch_kds, mid_lad,
                    arm_dir, gate_eps, N_STEPS, gate_seeds,
                    variant["prompt"], variant["user_msg_fn"], variant["key"],
                    episode_start=1, open_mode="w")
        finally:
            pass

        # Evaluate gate: at least 1 success required
        trace = [json.loads(l) for l in open(arm_dir / "trace.jsonl", encoding="utf-8")]
        eps_g = {}
        for r in trace:
            eps_g.setdefault(r["episode"], []).append(r)
        n_success = sum(1 for rows in eps_g.values() if rows[-1].get("terminal"))
        print(f"\nGATE RESULT: {n_success}/{gate_eps} episodes reached target.")
        if n_success == 0:
            print("GATE FAILED -- navigation collapsed. Stopping. Do not run full V4.")
            env.close(); return
        print("GATE PASSED -- proceeding to full 10-episode run for both arms.")
        # Run remaining wire_only eps (4-10) then overlay (1-10)
        try:
            remaining_seeds = ABLATION_SEEDS[gate_eps:N_EPISODES]
            run_arm(client, env, sim, fluoro, binary_mask,
                    "wire_only", branch_kds, mid_lad,
                    arm_dir, N_EPISODES - gate_eps, N_STEPS, remaining_seeds,
                    variant["prompt"], variant["user_msg_fn"], variant["key"],
                    episode_start=gate_eps + 1, open_mode="a")
            ov_dir = run_dir / variant["key"] / "overlay"
            run_arm(client, env, sim, fluoro, binary_mask,
                    "overlay", branch_kds, mid_lad,
                    ov_dir, N_EPISODES, N_STEPS, ABLATION_SEEDS[:N_EPISODES],
                    variant["prompt"], variant["user_msg_fn"], variant["key"],
                    episode_start=1, open_mode="w")
        except KeyboardInterrupt:
            print("\nInterrupted.")
        finally:
            env.close()
        analyze_traces(run_dir)
        return

    print(f"\nVariants: {variant_keys}  Modes: {modes}  "
          f"Eps: {episode_start}-{episode_start+n_eps-1}  open_mode={open_mode}")
    print(f"Seeds: {seeds_slice}")

    try:
        for vkey in variant_keys:
            variant = next(v for v in VARIANTS if v["key"] == vkey)
            for mode in modes:
                arm_dir = run_dir / vkey / mode
                run_arm(
                    client, env, sim, fluoro, binary_mask,
                    mode, branch_kds, mid_lad,
                    arm_dir, n_eps, N_STEPS, seeds_slice,
                    variant["prompt"], variant["user_msg_fn"], vkey,
                    episode_start=episode_start, open_mode=open_mode,
                )
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        env.close()

    analyze_traces(run_dir)


if __name__ == "__main__":
    main()
