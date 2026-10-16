# CoroNav

**A coronary guidewire-navigation environment for studying how vision-language-model
(VLM) operators use fluoroscopic images.**

CoroNav runs a physics-based coronary guidewire simulation (SOFA v23.06 +
BeamAdapter, via stEVE). At each step it renders a fluoroscopic projection and
a one-line state string. An image-based operator returns a JSON action, and the
environment executes it and logs the full state–action–outcome trace.

```
fluoroscopy image (512×512 px)   state text: "Distance to mid-LAD target: 42.3 mm. ..."
       │                                  │
       └──────────────┬───────────────────┘
                      ▼
             image-based operator (VLM, or your model)
                      │
          {"intended_direction": "advance",
           "action": {"translation": 30, "rotation": 0}}
                      │
                      ▼
          SOFA v23.06 coronary simulation (dt = 0.001 s)
```

**What it is, and what it is not.** As configured, the task is solvable
*without any visual information*: an open-loop policy that only advances
reaches the target in every episode on both retained anatomies. CoroNav is
therefore an **instrument (a controlled condition) for studying VLM visual
behaviour**, not a validated navigation-difficulty benchmark. A lower score
for an operator tells you how it uses the image, not how hard the task is.
You can still plug in and test your own operator (see
[Add your model](#add-your-model)).

## The study this repository supports

*Vessel overlay slows vision-language-model guidewire navigation in simulated
coronary anatomies* (manuscript in submission).

- **Question:** does rendering the vessel lumen into simulated fluoroscopy
  help a VLM operator?
- **Design:** one VLM (Claude Sonnet 4.6) navigated from the ostium to a
  mid-LAD target. Two conditions were compared: `wire_only` and `overlay`.
  Each arm had 25 seed-matched episodes, at a simulation timestep of 0.001 s.
  Step limits were 60 (A1) and 120 (A2), the same for both arms. An image-free
  open-loop control measured what the task needs without vision.
- **Anatomies:** two retained patient-derived left-coronary geometries, A1
  (VMR 0066) and A2 (ASOCA Normal_12). A third, A3 (ASOCA Normal_5), was
  **excluded** because its surface is a generated constant-radius tube, not
  patient lumen, and its contact physics did not resolve adequately.
- **Primary endpoint:** navigation efficiency (steps to target), analysed over
  all episodes without conditioning on success.
- **Secondary endpoint:** `f_rot_LM`, the left-main-phase rotation-movement
  fraction. It is dimensionless and in [0, 1]. Its code name is `lm_rot_mm`,
  which is *not* a length.

| | A1 (VMR 0066) | A2 (ASOCA Normal_12) |
|---|---|---|
| Open-loop control reached target | 75/75 | 75/75 |
| VLM reached target, wire_only vs overlay | 20/25 vs 13/25 (Fisher p = 0.0718, n.s.) | 25/25 vs 25/25 |
| Navigation (primary) | worst-rank p = 0.00206; win ratio 5.60 (95% CI 2.43–17.97); log-rank p = 0.000623 | median 41 vs 56 steps; Hodges–Lehmann +14.5 (95% CI +13.0 to +16.5); p = 1.25e-05 |
| `f_rot_LM` (secondary) | median 0.1452 vs 0.1749; paired p = 0.0147 (Holm 0.0147); unpaired p = 0.000384 | 0 vs 37 left-main rotate intents; paired p = 0.000482 (Holm 0.000965) |

Full results, limitations, the excluded A3 and the archived earlier analyses
are in **[`RESULTS.md`](RESULTS.md)**. The protocol is in
[`PROTOCOL.md`](PROTOCOL.md). The manuscript-to-repository audit is in
[`docs/MANUSCRIPT_CONCORDANCE.md`](docs/MANUSCRIPT_CONCORDANCE.md).

---

## Reproducibility status

Three separate questions, three separate answers:

| Question | Status |
|---|---|
| **Original-results traceability:** can the manuscript's statistics be regenerated from the original experimental records? | **No, not from this repository.** The original episode traces, analysis scripts, the number-to-artifact manifest and `CORRECTIONS.md` are not in this repository yet. The numbers above are transcribed from the manuscript. |
| **Environment reproducibility:** can another investigator install and run the simulation and operator? | **Yes for A1**, via Docker. Verified on 2026-10-14: the image builds and `scripts/check_install.py` passes. The open-loop control ran in the container (see `docs/MANUSCRIPT_CONCORDANCE.md`). **A2 is not yet reproducible from this repository**, because the conversion of the ASOCA case into the required mesh and centerline layout is not included. |
| **Independent result reproduction:** has this code reproduced the manuscript's quantitative results? | **Partly.** The A1 open-loop control was re-run in the container at 0.001 s: 75/75 reached target, 26 steps each, final distance 4.582–4.707 mm, matching the manuscript (75/75, 26, 4.58–4.71 mm). **The VLM arms and everything on A2 have not been reproduced.** No n = 25 operator run has been made with this repository. Details: `docs/MANUSCRIPT_CONCORDANCE.md` §5. |

Other points that affect reproduction:

- **The VLM's decoding is stochastic and unseeded.** Seeds fix the simulator
  reset only, so re-running an operator arm gives new trajectories and is a
  new sample, not a replay.
- An earlier partial container run (n = 9, A1, `wire_only`) used code that
  hard-coded the superseded 0.006 s timestep. It is archived in
  `RESULTS.md` §3.5 and is not evidence either way.

---

## Install

**SOFA v23.06 + BeamAdapter are compiled C++ binaries and cannot be
pip-installed.** Docker is the supported install path. The image downloads
two pre-built Linux binaries (~338 MB) and installs everything automatically.

### Prerequisites

- Docker (any version with `docker build`)
- An Anthropic API key (`ANTHROPIC_API_KEY`), only for the VLM operator. The
  open-loop control needs no key.

### Build the image (~5 min, downloaded layers are cached)

```bash
git clone https://github.com/Rugved3-droid/coronav.git
cd coronav
docker build -t coronav:latest -f docker/Dockerfile .
```

The build runs `python3 scripts/check_install.py` as its final layer. A
passing build means SOFA, BeamAdapter, stEVE and CoroNav all imported, the A1
centerlines parsed via `left_coronary_branches()`, and the protocol and code
timestep both equal 0.001 s. The image pins the Anthropic SDK to v0.72.0 (as
in the manuscript) and stEVE to a fixed commit.

### Run the image-free control (A1, no API key, no cost)

```bash
docker run --rm -v $PWD/runs:/coronav/runs coronav:latest \
  python3 benchmarks/run_benchmark.py --operator open_loop --anatomy a1
```

### Run the quickstart (A1, 3 VLM episodes, paid API calls)

> **Windows / Docker Desktop users:** the `-v $PWD/runs:/coronav/runs` mount
> below only works if the drive you're running from is enabled under
> Docker Desktop → Settings → Resources → File sharing. By default this is
> often just `C:`. If your clone lives on another drive (`D:`, etc.) and
> that drive isn't shared, the mount silently no-ops: the container starts
> fine, produces no error, and any output written to `runs/` simply never
> appears on the host. Enable your drive in File sharing (Apply & Restart)
> before relying on mounted output.

```bash
docker run --rm -it \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $PWD/runs:/coronav/runs \
  coronav:latest \
  python3 examples/quickstart.py
```

The quickstart prints per-step progress, then per-episode reached-target /
steps / `f_rot_LM`. Three episodes are a smoke test only and are not
comparable with the manuscript's n = 25 arms.

---

## Run the experiment design

```bash
# A1, both observation conditions (bundled anatomy, no registration; paid API calls)
docker run --rm -it \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $PWD/runs:/coronav/runs \
  coronav:latest \
  python3 benchmarks/run_benchmark.py --operator claude --anatomy a1 --mode wire_only overlay

# Descriptive summary
docker run --rm -v $PWD/runs:/coronav/runs coronav:latest \
  python3 benchmarks/report.py --run-dir runs/<timestamp>/
```

Each run writes `trace.jsonl` plus a `run_meta.json`. The metadata records
the timestep, step limit, seeds, operator, git commit, and a statement that
it is a new run rather than a reproduction. `report.py` gives descriptive
statistics and an unpaired sensitivity test only. The manuscript's
confirmatory analyses (worst-rank, win ratio, log-rank, Hodges–Lehmann,
paired Wilcoxon with Holm) are not in this repository.

The timestep is 0.001 s (133 SOFA sub-steps per operator step), so episodes
run about 6× slower than the superseded 0.006 s setting did.

### A2 (ASOCA Normal_12): requires registration and preparation

ASOCA data cannot be redistributed. To use A2:

1. Register at https://asoca.grand-challenge.org/ and download the ASOCA
   Normal cases under their terms.
2. Run the extractor, which also checks the result:
   ```bash
   docker run --rm \
     -v $PWD/data/anatomy:/coronav/data/anatomy \
     -v /path/to/ASOCA_Normal.zip:/tmp/ASOCA_Normal.zip \
     coronav:latest \
     python3 scripts/download_asoca.py --asoca-zip /tmp/ASOCA_Normal.zip
   ```
3. `build_env()` needs `clipped_left.obj`, `clipped_left.vtp` and ordered
   `paths/LAD*.pth` / `paths/LCX*.pth` centerlines in millimetres. **The
   pipeline that turned Normal_12 into that layout for the manuscript is not
   in this repository**, so step 2 will report "NOT READY" unless you supply
   those files. This is an open item (`docs/MANUSCRIPT_CONCORDANCE.md`).
4. Then:
   ```bash
   python3 benchmarks/run_benchmark.py --operator claude --anatomy a2 --mode wire_only overlay
   ```

A3 (ASOCA Normal_5) is excluded. The runner refuses it unless you pass
`--allow-excluded`, which exists for archival inspection only.

---

## Add your model

Copy `coronav/operator/template.py`, rename the class, and fill in `act()`.
You only need to implement one method. The runner handles everything else.

```python
from coronav.operator.base import VLMOperator
from coronav.prompts import DEFAULT_SYSTEM_PROMPT

class MyOperator(VLMOperator):
    def __init__(self):
        super().__init__(DEFAULT_SYSTEM_PROMPT)
        # load your model / client here

    def act(self, images, state_text):
        # images: list of (512,512) uint8 arrays
        # state_text: "Distance to mid-LAD target: 42.3 mm. Distance trend ..."
        # return: {"intended_direction": "advance", "action": {"translation": 30, "rotation": 0}}
        ...
```

See `examples/add_your_model.py` for a complete GPT-4o implementation. Then
run it from inside the container:

```bash
docker run --rm -it \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $PWD/runs:/coronav/runs \
  -v $PWD/coronav/operator:/coronav/coronav/operator \
  coronav:latest \
  python3 benchmarks/run_benchmark.py \
    --operator coronav.operator.my_model.MyOperator \
    --anatomy a1 --mode wire_only overlay
```

When you interpret results, remember that the open-loop control solves the
task. The informative quantity is how an operator's behaviour changes between
observation conditions, not its absolute score.

---

## Advanced: running without Docker

> **Warning:** Building SOFA v23.06 + BeamAdapter from source typically takes
> several hours and requires specific system libraries. Docker is strongly
> preferred. This path is for users with an existing SOFA v23.06 + BeamAdapter
> installation.

```bash
# Set SOFA paths
export SOFA_ROOT=/path/to/SOFA_v23.06.00_Linux
export PYTHONPATH="${SOFA_ROOT}/plugins/SofaPython3/lib/python3/site-packages:$PYTHONPATH"
export LD_LIBRARY_PATH="${SOFA_ROOT}/lib:$LD_LIBRARY_PATH"

# Python 3.8 (SOFA 23.06 prebuilt bindings) + stEVE + CoroNav
pip install numpy scipy Pillow "anthropic==0.72.0"
pip install "git+https://github.com/lkarstensen/stEVE.git@f909e7122d846a3c2fec91eedddaa0ba88b6391d"
pip install -e .

# Verify
python scripts/check_install.py

# Run
python benchmarks/run_benchmark.py --operator open_loop --anatomy a1
ANTHROPIC_API_KEY=... python examples/quickstart.py
```

### Unit tests (no SOFA, no API)

```bash
pip install numpy pillow pytest
python -m pytest tests
```

These test the metric definitions and protocol/code consistency on synthetic
fixtures. They are not evidence that any experimental result reproduces.

---

## Anatomy data

| Key | Name | Source | Status | Bundled | License |
|-----|------|--------|--------|---------|---------|
| A1 | VMR 0066 | Vascular Model Repository | retained | Yes | VMR terms, see `data/anatomy/a1_vmr0066/LICENSE_VMR0066` |
| A2 | ASOCA Normal_12 | ASOCA challenge | retained | No (registration) | ASOCA terms; do not redistribute |
| A3 | ASOCA Normal_5 (generated 2.5 mm tube) | ASOCA challenge | **excluded** | No | ASOCA terms |

**A1 citation:** Wilson NM, Ortiz AK, Johnson AB. J Med Device 2013;7(4):040923, doi:10.1115/1.4025983

**A2 citation:** Gharleghi R et al. Sci Data 2023;10:128, doi:10.1038/s41597-023-02016-2

---

## Repo structure

```
coronav/
├── coronav/                # Python package
│   ├── env.py              # build_env(), run_episode(); DT_SIMULATION = 0.001
│   ├── metrics.py          # lm_metrics() (f_rot_LM), episode_outcome(), run_summary()
│   ├── prompts.py          # DEFAULT_SYSTEM_PROMPT + harness constants
│   ├── operator/
│   │   ├── base.py         # VLMOperator ABC
│   │   ├── claude.py       # ClaudeOperator (claude-sonnet-4-6)
│   │   ├── open_loop.py    # OpenLoopOperator (image-free control)
│   │   └── template.py     # TemplateOperator stub
│   └── sim/
│       ├── coronary_sim.py # CoronaryBeamAdapter (SOFA Fix A + Fix B)
│       └── pth_centerlines.py
├── benchmarks/
│   ├── protocol.json       # seeds, step limits, timestep, endpoints (v2.0)
│   ├── run_benchmark.py    # CLI runner (--operator, --anatomy, --mode)
│   └── report.py           # descriptive summary of runs
├── data/anatomy/
│   └── a1_vmr0066/         # VMR 0066 (bundled)
├── docker/                 # Dockerfile, compose, README
├── docs/
│   └── MANUSCRIPT_CONCORDANCE.md   # manuscript ↔ repository audit
├── examples/               # quickstart.py, add_your_model.py
├── scripts/                # check_install.py, download_asoca.py
├── tests/                  # synthetic unit tests (no SOFA)
├── PROTOCOL.md
├── RESULTS.md
└── CITATION.cff
```

---

## Citation

```bibtex
@unpublished{Xcoronav,
  title   = {Vessel overlay slows vision-language-model guidewire navigation in simulated coronary anatomies},
  author  = {X,Y,Z},
  year    = {2026},
  note    = {Manuscript in submission}
}
```

If you use the A1 anatomy (VMR 0066):
```bibtex
@article{wilson2013vmr,
  title   = {The Vascular Model Repository: A Public Resource of Medical Imaging Data and Blood Flow Simulation Results},
  author  = {Wilson, Nathan M. and Ortiz, Ana K. and Johnson, Allison B.},
  journal = {Journal of Medical Devices},
  volume  = {7},
  number  = {4},
  pages   = {040923},
  year    = {2013},
  doi     = {10.1115/1.4025983}
}
```

If you use A2 (ASOCA):
```bibtex
@article{gharleghi2023asoca,
  title   = {Annotated computed tomography coronary angiogram images and associated data of normal and diseased arteries},
  author  = {Gharleghi, Ramtin and others},
  journal = {Scientific Data},
  volume  = {10},
  pages   = {128},
  year    = {2023},
  doi     = {10.1038/s41597-023-02016-2}
}
```

---

## License

Code: MIT (see `LICENSE`).
Data: see the individual `LICENSE_*` files in `data/anatomy/`.
