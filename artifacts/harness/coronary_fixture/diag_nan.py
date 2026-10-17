"""
Diagnostic: isolate NaN source in coronary sim.
- TEST A: contact disabled (alarmDistance=0) → isolates BTD/beam physics NaN
- TEST B: contact enabled → full pipeline

Run:  python coronary_fixture/diag_nan.py
"""
import os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from coronary_fixture.env_coronary_left import build_coronary_env

print("Building env ...")
env, vt, mid_lad = build_coronary_env(seed=42, max_it=2000)
sim = env.intervention.simulation


def run_test(label, xtip_advance, disable_contact=False, n_substeps=2):
    obs = env.reset()
    ic = sim._instruments_combined
    sofa = sim._sofa

    xtip_before = float(ic.m_ircontroller.xtip.value[0])
    pos0 = ic.DOFs.position.value[:, 0:3].copy()
    dist = np.linalg.norm(pos0[-1] - pos0[-2])
    print(f"\n[{label}]  xtip_before={xtip_before:.6f}mm  dist[-1,-2]={dist:.6f}mm  disable_contact={disable_contact}")

    lmd = sim.root.getObject("localmindistance")

    ok = True
    for s in range(n_substeps):
        x = ic.m_ircontroller.xtip.value.copy()
        x[0] += xtip_advance
        ic.m_ircontroller.xtip.value = x

        pos_pre = ic.DOFs.position.value[:, 0:3].copy()
        d_pre = np.linalg.norm(pos_pre[-1] - pos_pre[-2])
        print(f"  substep{s+1} PRE:  xtip={x[0]:.6f}  dist[-1,-2]={d_pre:.6f}")

        if disable_contact:
            lmd.alarmDistance.value = 0.0
            lmd.contactDistance.value = 0.0

        sofa.Simulation.animate(sim.root, sim.root.dt.value)

        if disable_contact:
            lmd.alarmDistance.value = 0.5
            lmd.contactDistance.value = 0.3

        pos = ic.DOFs.position.value[:, 0:3]
        n_nan = int(np.sum(np.isnan(pos)))

        if n_nan == 0:
            tip = pos[-1]
            d_start = float(np.linalg.norm(tip - pos0[0]))
            print(f"  substep{s+1} POST: nan=0  tip_dist_from_entrance={d_start:.4f}mm  OK")
        else:
            first_nan = np.where(np.any(np.isnan(pos), axis=1))[0][0]
            print(f"  substep{s+1} POST: nan={n_nan}/189  first_nan_row={first_nan}  <<< NaN!")
            ok = False
            break
    return ok


print("\n" + "="*60)
print("TEST 1: tiny advance, CONTACT DISABLED (BTD-only check)")
print("="*60)
r1 = run_test("tiny-no-contact", 0.0001, disable_contact=True, n_substeps=2)

print("\n" + "="*60)
print("TEST 2: tiny advance, CONTACT ENABLED (full pipeline)")
print("="*60)
r2 = run_test("tiny-contact", 0.0001, disable_contact=False, n_substeps=2)

print("\n" + "="*60)
print("TEST 3: large advance (0.21mm), CONTACT ENABLED")
print("="*60)
r3 = run_test("large-contact", 35.0 * 0.006, disable_contact=False, n_substeps=2)

print("\n" + "="*60)
summary = {
    "TEST1 (tiny, no contact)": r1,
    "TEST2 (tiny, contact)": r2,
    "TEST3 (large, contact)": r3,
}
for k, v in summary.items():
    print(f"  {k}: {'PASS' if v else 'FAIL'}")
print("="*60)
env.close()
