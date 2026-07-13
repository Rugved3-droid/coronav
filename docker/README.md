# CoroNav Docker

Containerised SOFA v23.06 + BeamAdapter + CoroNav for reproducible evaluation.

## What the build downloads

SOFA v23.06 + BeamAdapter are compiled C++ — they cannot be pip-installed.
The Dockerfile fetches two pre-built Linux binaries during `docker build`:

| Package | Source | Size |
|---------|--------|------|
| `SOFA_v23.06.00_Linux.zip` | sofa-framework/sofa releases | 335 MB |
| `BeamAdapter_v23.06_for-SOFA-v23.06_Linux.zip` | sofa-framework/BeamAdapter releases | 3 MB |

Both are official releases.  BeamAdapter is **separate** from the main SOFA
zip — the Dockerfile downloads and merges it into the SOFA directory.

## Quick start

> **Windows / Docker Desktop users:** every `-v $PWD/runs:/coronav/runs`
> mount below only works if the drive you're running from is enabled under
> Docker Desktop → Settings → Resources → File sharing (often just `C:` by
> default). If your clone lives on another drive and it isn't shared, the
> mount silently no-ops — no error, the container just never writes output
> back to the host. Enable your drive in File sharing first.

```bash
# 1. Build (~5 min — most time is the 338 MB download; layers are cached)
docker build -t coronav:latest -f docker/Dockerfile .
# The build runs check_install.py as the last layer.
# A passing build = SOFA, BeamAdapter, stEVE, CoroNav all working.

# 2. Quickstart (3 episodes on A1, no ASOCA registration needed)
docker run --rm -it \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $PWD/runs:/coronav/runs \
  coronav:latest \
  python3 examples/quickstart.py
```

## Full benchmark

```bash
docker run --rm -it \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $PWD/runs:/coronav/runs \
  coronav:latest \
  python3 benchmarks/run_benchmark.py --operator claude --anatomy a1
```

## docker-compose

```bash
cp .env.example .env && nano .env    # set ANTHROPIC_API_KEY

# Quickstart
docker-compose -f docker/docker-compose.yml run --rm quickstart

# Full A1 benchmark
docker-compose -f docker/docker-compose.yml run --rm coronav

# Smoke test (no API key needed)
docker-compose -f docker/docker-compose.yml run --rm check
```

## Mounting ASOCA data (A2/A3)

ASOCA data is not bundled (license-gated). After running `scripts/download_asoca.py`
on the host, mount the anatomy directory:

```bash
docker run --rm -it \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -v $PWD/runs:/coronav/runs \
  -v $PWD/data/anatomy:/coronav/data/anatomy \
  coronav:latest \
  python benchmarks/run_benchmark.py --operator claude --anatomy a1 a2 a3
```

## GPU

SOFA 23.06 does not require a GPU for the beamadapter simulations used in
CoroNav (CPU LCP solver). GPU acceleration is only relevant if you run your
own SOFA plugins that use CUDA.

To enable GPU access in Docker anyway:
1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/).
2. Uncomment the `deploy:` section in `docker/docker-compose.yml`.
3. Add `--gpus all` when using `docker run`.

## Troubleshooting

**SOFA import fails inside container**

Check that `PYTHONPATH` includes the SOFA Python bindings:
```bash
docker run --rm coronav:latest python -c "import Sofa; print(Sofa.__file__)"
```
If it fails, the SOFA release archive URL in `docker/Dockerfile` may have
changed. Update `SOFA_URL` to the current URL from
https://github.com/sofa-framework/sofa/releases/tag/v23.06.00

**OOM kill during benchmark**

SOFA BeamAdapter uses up to ~1.5 GB RAM per episode. Increase Docker memory
limit to at least 4 GB (Docker Desktop → Settings → Resources → Memory).

**Slow first run**

The first `build_env()` call compiles SOFA shaders. This is a one-time
per-container cost. Subsequent episodes in the same container are fast.
