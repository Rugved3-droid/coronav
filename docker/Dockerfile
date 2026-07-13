# CoroNav: SOFA v23.06.00 + BeamAdapter v23.06 + stEVE + CoroNav
#
# Two pre-built binaries are downloaded at build time (~338 MB total):
#   SOFA v23.06.00 Linux  — sofa-framework/sofa            (335 MB)
#   BeamAdapter v23.06    — sofa-framework/BeamAdapter      (  3 MB)
# stEVE is cloned from GitHub and installed via pip.
#
# Build (takes ~5 min on first run — downloads are cached in layers):
#   docker build -t coronav:latest -f docker/Dockerfile .
#
# Run quickstart (A1, 3 episodes):
#   docker run --rm -it \
#     -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
#     -v $PWD/runs:/coronav/runs \
#     coronav:latest \
#     python3 examples/quickstart.py
#
# Full benchmark:
#   docker run --rm -it \
#     -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
#     -v $PWD/runs:/coronav/runs \
#     coronav:latest \
#     python3 benchmarks/run_benchmark.py --operator claude --anatomy a1

# SOFA v23.06.00's prebuilt SofaPython3 bindings are compiled against Python 3.8
# specifically (see release notes) — python:3.8-slim-bullseye gives us that
# natively, so python3/pip3 already resolve to 3.8 with no PPA needed.
FROM python:3.8-slim-bullseye
LABEL maintainer="CoroNav"
LABEL sofa_version="23.06.00"
LABEL beamadapter_version="23.06"

ENV DEBIAN_FRONTEND=noninteractive

# ── runtime libs SOFA needs on Linux ──────────────────────────────────────────
# git: needed for `pip install git+https://...` (stEVE).
# build-essential: needed to build any wheels without cp38 manylinux binaries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget unzip ca-certificates git build-essential \
        libgl1-mesa-glx libglu1-mesa \
        libgomp1 libpng-dev libjpeg-dev \
        libxrender1 libxext6 libx11-6 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ── SOFA v23.06.00 pre-built Linux binary (335 MB) ────────────────────────────
ARG SOFA_URL=https://github.com/sofa-framework/sofa/releases/download/v23.06.00/SOFA_v23.06.00_Linux.zip
RUN wget -q --show-progress "${SOFA_URL}" -O /tmp/sofa.zip \
    && unzip -q /tmp/sofa.zip -d /opt/ \
    && rm /tmp/sofa.zip

ENV SOFA_ROOT=/opt/SOFA_v23.06.00_Linux

# ── BeamAdapter v23.06 pre-built Linux binary (3 MB) ─────────────────────────
# BeamAdapter is a SEPARATE download — NOT included in the main SOFA zip.
ARG BA_URL=https://github.com/sofa-framework/BeamAdapter/releases/download/release-v23.06/BeamAdapter_v23.06_for-SOFA-v23.06_Linux.zip
RUN wget -q "${BA_URL}" -O /tmp/ba.zip \
    && unzip -q /tmp/ba.zip -d /tmp/ba/ \
    && cp -r /tmp/ba/BeamAdapter_v23.06_for-SOFA-v23.06_Linux/. "${SOFA_ROOT}/" \
    && rm -rf /tmp/ba.zip /tmp/ba/

# ── Paths: SofaPython3 site-packages + shared libs ───────────────────────────
# Set directly (no ${VAR:-} fallback) — the base image has no pre-existing
# PYTHONPATH/LD_LIBRARY_PATH, and referencing an undefined var here trips
# BuildKit's UndefinedVar lint and can leave the value malformed.
ENV PYTHONPATH="${SOFA_ROOT}/plugins/SofaPython3/lib/python3/site-packages"
ENV LD_LIBRARY_PATH="${SOFA_ROOT}/lib:${SOFA_ROOT}/plugins/SofaPython3/lib"
ENV SOFA_PLUGIN_PATH="${SOFA_ROOT}/lib"

# Verify SOFA + SofaPython3 import at build time
RUN python3 -c "import Sofa; print('SOFA OK:', Sofa.__file__)"

# ── Python packages ──────────────────────────────────────────────────────────
RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir \
        numpy scipy Pillow anthropic \
        "git+https://github.com/lkarstensen/stEVE.git"

# Verify stEVE + BeamAdapter plugin import at build time
RUN python3 -c "import eve; print('stEVE OK:', eve.__file__)" \
    && python3 -c "import Sofa, SofaRuntime; root = Sofa.Core.Node('root'); SofaRuntime.importPlugin('BeamAdapter'); print('BeamAdapter plugin OK')"

# ── CoroNav ──────────────────────────────────────────────────────────────────
WORKDIR /coronav
COPY . /coronav/
RUN pip3 install --no-cache-dir -e . --no-deps

# Full smoke test at build time (no API key needed)
RUN python3 scripts/check_install.py

# ── Default command ───────────────────────────────────────────────────────────
# Pass ANTHROPIC_API_KEY via -e flag at docker run time.
CMD ["python3", "examples/quickstart.py"]
