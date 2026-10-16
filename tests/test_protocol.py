"""Consistency checks between benchmarks/protocol.json, the code defaults, and
the final manuscript design. No SOFA or API access needed."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = json.loads((ROOT / "benchmarks" / "protocol.json").read_text(encoding="utf-8"))


def _module_constant(path, name):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def _default_arg(path, cls, func, arg):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for c in ast.walk(tree):
        if isinstance(c, ast.ClassDef) and c.name == cls:
            for f in c.body:
                if isinstance(f, ast.FunctionDef) and f.name == func:
                    names = [a.arg for a in f.args.args]
                    defaults = dict(zip(names[-len(f.args.defaults):], f.args.defaults))
                    return ast.literal_eval(defaults[arg])
    raise KeyError(arg)


def test_timestep_is_manuscript_value_everywhere():
    assert PROTOCOL["simulation"]["dt_simulation_s"] == 0.001
    assert _module_constant(ROOT / "coronav" / "env.py", "DT_SIMULATION") == 0.001
    assert _default_arg(ROOT / "coronav" / "sim" / "coronary_sim.py",
                        "CoronaryBeamAdapter", "__init__", "dt_simulation") == 0.001


def test_retained_anatomies_and_step_limits():
    a = PROTOCOL["anatomies"]
    assert {k for k, v in a.items() if v["status"] == "retained"} == {"a1", "a2"}
    assert a["a1"]["step_budget"] == 60
    assert a["a2"]["step_budget"] == 120
    for k in ("a1", "a2"):
        assert a[k]["n_episodes"] == 25 == len(a[k]["seeds"]) == len(set(a[k]["seeds"]))


def test_a3_is_excluded_with_reason():
    a3 = PROTOCOL["anatomies"]["a3"]
    assert a3["status"] == "excluded"
    assert "patient" in a3["exclusion_reason"]


def test_both_observation_conditions_available():
    assert {"wire_only", "overlay"} <= set(PROTOCOL["imaging"]["modes"])


def test_harness_constants_match_protocol():
    prompts = ROOT / "coronav" / "prompts.py"
    op = PROTOCOL["operator"]
    assert _module_constant(prompts, "_PROXIMITY_GATE_MM") == op["proximity_gate_mm"]
    assert _module_constant(prompts, "_PROXIMITY_GATE_ADV_DEFAULT") == op["proximity_gate_advance_mm_s"]
    assert _module_constant(prompts, "_RETRACTION_BUDGET") == op["retraction_budget"]
    open_loop = ROOT / "coronav" / "operator" / "open_loop.py"
    assert _module_constant(open_loop, "OPEN_LOOP_ADVANCE_MM_S") == PROTOCOL["open_loop_control"]["advance_mm_s"]
