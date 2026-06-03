"""
Runs TRELLIS.2 locally via subprocess using the local GPU.
"""
import logging
import os
import shutil
import subprocess
import sys
import base64
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter("%(asctime)s [trellis_runner] %(message)s"))
log = logging.getLogger("trellis_runner")
log.addHandler(_h)
log.setLevel(logging.DEBUG)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TRELLIS_DIR = _REPO_ROOT / "rendering-pipeline" / "trellis-server"
_DEFAULT_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"
_TRELLIS2_PKG_DIR    = _REPO_ROOT / "TRELLIS2"  # trellis2/ package lives here (no setup.py)

TRELLIS_DIR  = Path(os.getenv("TRELLIS_DIR",  str(_DEFAULT_TRELLIS_DIR)))
VENV_PYTHON  = Path(os.getenv("VENV_PYTHON",  str(_DEFAULT_VENV_PYTHON)))
ASSETS_DIR   = TRELLIS_DIR / "assets"
EXAMPLE_PY   = TRELLIS_DIR / "example.py"
OUTPUT_GLB   = TRELLIS_DIR / "sample.glb"
TIMEOUT_SECS = int(os.getenv("TRELLIS_TIMEOUT", str(30 * 60)))  # 30 min

GLB_STORE = Path(__file__).parent / "glb_store"
GLB_STORE.mkdir(exist_ok=True)


def run_trellis(image_b64: str, job_id: str) -> str:
    if not VENV_PYTHON.is_file():
        raise RuntimeError(
            f".venv Python not found at {VENV_PYTHON}. Create it first:\n"
            "  python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt\n"
            "Or set VENV_PYTHON in backend/.env to the correct path."
        )
    if not EXAMPLE_PY.is_file():
        raise RuntimeError(
            f"TRELLIS example.py not found at {EXAMPLE_PY}. "
            "Set TRELLIS_DIR in backend/.env."
        )
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    raw = base64.b64decode(image_b64)
    input_img = ASSETS_DIR / f"input_{job_id}.png"
    input_img.write_bytes(raw)
    log.info("Wrote input image → %s", input_img)

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "0"
    env["HF_HUB_DISABLE_XET"] = "1"
    # trellis2 has no setup.py — add the submodule root to PYTHONPATH
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_TRELLIS2_PKG_DIR}:{existing}" if existing else str(_TRELLIS2_PKG_DIR)

    log.info("Running TRELLIS (timeout=%ds): %s %s %s", TIMEOUT_SECS, VENV_PYTHON, EXAMPLE_PY, input_img)

    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(EXAMPLE_PY), str(input_img)],
            cwd=str(TRELLIS_DIR),
            env=env,
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
