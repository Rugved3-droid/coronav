"""
Download 0066_H_CORO_H from the VMR (new ZIP-based URL, post-2024 website).
Saves to .data/vmr/0066_H_CORO_H/ alongside the existing aortic models.

Run from the stEVE repo root:
    python coronary_fixture/download_coronary.py
"""
import io
import os
import shutil
import zipfile
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODEL_ID = "0066_H_CORO_H"
BASE_URL = "https://www.vascularmodel.com/svprojects"

def get_data_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    return os.path.join(repo_root, ".data", "vmr")

def download(model_id: str, data_dir: str) -> str:
    model_dir = os.path.join(data_dir, model_id)
    if os.path.isdir(model_dir) and os.listdir(model_dir):
        log.info("Already downloaded: %s", model_dir)
        return model_dir

    os.makedirs(data_dir, exist_ok=True)
    zip_url = f"{BASE_URL}/{model_id}.zip"
    log.info("Downloading %s ...", zip_url)

    r = requests.get(zip_url, timeout=120, stream=True)
    r.raise_for_status()

    buf = io.BytesIO()
    total = 0
    for chunk in r.iter_content(chunk_size=131072):
        buf.write(chunk)
        total += len(chunk)
    log.info("Downloaded %.1f MB", total / 1e6)

    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(data_dir)
    log.info("Extracted to %s", model_dir)
    return model_dir


if __name__ == "__main__":
    data_dir = get_data_dir()
    model_dir = download(MODEL_ID, data_dir)
    log.info("Model dir: %s", model_dir)
    for root, dirs, files in os.walk(model_dir):
        for f in files:
            log.info("  %s", os.path.join(root, f).replace(model_dir, ""))
