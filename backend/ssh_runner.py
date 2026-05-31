"""
Runs TRELLIS.2 locally via subprocess — backend and TRELLIS share the same machine.
"""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import base64
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter("%(asctime)s [ssh_runner] %(message)s"))
log = logging.getLogger("ssh_runner")
log.addHandler(_h)
log.setLevel(logging.DEBUG)

TRELLIS_DIR   = Path(os.getenv("TRELLIS_DIR",   "/home/asus/TRELLIS.2"))
CONDA_SH      = Path(os.getenv("CONDA_SH",      "/home/benjamin/miniconda3/etc/profile.d/conda.sh"))
CONDA_ENV     = os.getenv("CONDA_ENV",           "trellis2")
ASSETS_DIR    = TRELLIS_DIR / "assets" / "example_image"
EXAMPLE_PY    = TRELLIS_DIR / "example.py"
OUTPUT_GLB    = TRELLIS_DIR / "sample.glb"
TIMEOUT_SECS  = int(os.getenv("TRELLIS_TIMEOUT", str(30 * 60)))  # 30 min

GLB_STORE = Path(__file__).parent / "glb_store"
GLB_STORE.mkdir(exist_ok=True)


def run_trellis(image_b64: str, job_id: str) -> str:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Write input image
    raw = base64.b64decode(image_b64)
    input_img = ASSETS_DIR / f"input_{job_id}.png"
    input_img.write_bytes(raw)
    log.info("Wrote input image → %s", input_img)

    cmd = (
        f"source {CONDA_SH} && "
        f"cd {TRELLIS_DIR} && "
        f"HF_HUB_DISABLE_XET=1 "
        f"conda run -n {CONDA_ENV} --no-capture-output "
        f"python {EXAMPLE_PY} {input_img}"
    )
    log.info("Running TRELLIS (timeout=%ds): %s", TIMEOUT_SECS, cmd)

    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            timeout=TIMEOUT_SECS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"TRELLIS timed out after {TIMEOUT_SECS}s")
    finally:
        input_img.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"TRELLIS exited {result.returncode}")

    if not OUTPUT_GLB.exists():
        raise RuntimeError(f"sample.glb not found at {OUTPUT_GLB}")

    dest = GLB_STORE / f"{job_id}.glb"
    shutil.move(str(OUTPUT_GLB), str(dest))
    log.info("GLB saved → %s", dest)
    return str(dest)
