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

def _find_conda_sh() -> Path:
    """Try common miniconda/anaconda install locations and current user's HOME."""
    candidates = [
        os.getenv("CONDA_SH"),
        f"{os.path.expanduser('~')}/miniconda3/etc/profile.d/conda.sh",
        f"{os.path.expanduser('~')}/anaconda3/etc/profile.d/conda.sh",
        "/home/asus/miniconda3/etc/profile.d/conda.sh",
        "/home/asus/anaconda3/etc/profile.d/conda.sh",
        "/home/benjamin/miniconda3/etc/profile.d/conda.sh",
        "/opt/miniconda3/etc/profile.d/conda.sh",
        "/opt/conda/etc/profile.d/conda.sh",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return Path(candidates[1])  # best guess — will fail clearly at runtime


TRELLIS_DIR   = Path(os.getenv("TRELLIS_DIR",   "/home/asus/TRELLIS.2"))
CONDA_SH      = _find_conda_sh()
CONDA_ENV     = os.getenv("CONDA_ENV",           "trellis2")
ASSETS_DIR    = TRELLIS_DIR / "assets" / "example_image"
EXAMPLE_PY    = TRELLIS_DIR / "example.py"
OUTPUT_GLB    = TRELLIS_DIR / "sample.glb"
TIMEOUT_SECS  = int(os.getenv("TRELLIS_TIMEOUT", str(30 * 60)))  # 30 min

GLB_STORE = Path(__file__).parent / "glb_store"
GLB_STORE.mkdir(exist_ok=True)


def run_trellis(image_b64: str, job_id: str) -> str:
    if not CONDA_SH.is_file():
        raise RuntimeError(
            f"conda.sh not found at {CONDA_SH}. Set CONDA_SH in backend/.env "
            "to the correct path (e.g. /home/asus/miniconda3/etc/profile.d/conda.sh)"
        )
    if not EXAMPLE_PY.is_file():
        raise RuntimeError(
            f"TRELLIS example.py not found at {EXAMPLE_PY}. Set TRELLIS_DIR in backend/.env."
        )
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Write input image
    raw = base64.b64decode(image_b64)
    input_img = ASSETS_DIR / f"input_{job_id}.png"
    input_img.write_bytes(raw)
    log.info("Wrote input image → %s", input_img)

    # Force the env's python to also see the calling user's site-packages
    # (cv2 etc. installed via `pip install --user` when env site-packages
    # is owned by another user)
    user_site = Path.home() / ".local/lib/python3.10/site-packages"
    cmd = (
        f"source {CONDA_SH} && "
        f"cd {TRELLIS_DIR} && "
        f"HF_HUB_DISABLE_XET=1 "
        f"PYTHONPATH={user_site}:${{PYTHONPATH:-}} "
        f"conda run -n {CONDA_ENV} --no-capture-output "
        f"env PYTHONPATH={user_site}:${{PYTHONPATH:-}} "
        f"python {EXAMPLE_PY} {input_img}"
    )
    log.info("Running TRELLIS (timeout=%ds): %s", TIMEOUT_SECS, cmd)

    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            timeout=TIMEOUT_SECS,
            check=False,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"TRELLIS timed out after {TIMEOUT_SECS}s")
    finally:
        input_img.unlink(missing_ok=True)

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-600:]
        log.error("TRELLIS failed (rc=%s): %s", result.returncode, tail)
        raise RuntimeError(f"TRELLIS exited {result.returncode}: {tail or '(no output)'}")

    if not OUTPUT_GLB.exists():
        raise RuntimeError(f"sample.glb not found at {OUTPUT_GLB}")

    dest = GLB_STORE / f"{job_id}.glb"
    shutil.move(str(OUTPUT_GLB), str(dest))
    log.info("GLB saved → %s", dest)
    return str(dest)
