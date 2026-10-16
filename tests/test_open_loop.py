import numpy as np

from coronav.operator.open_loop import OpenLoopOperator


def test_open_loop_always_advances_and_ignores_observation():
    op = OpenLoopOperator()
    blank = np.zeros((512, 512), dtype=np.uint8)
    noisy = np.random.default_rng(0).integers(0, 255, (512, 512), dtype=np.uint8)
    a = op.act([blank], "Distance to mid-LAD target: 80.0 mm.")
    b = op.act([noisy], "You MUST rotate on this step.")
    assert a == b == {"intended_direction": "advance",
                      "action": {"translation": 35.0, "rotation": 0.0}}
