"""
Runs Stable Fast 3D locally via subprocess using the local GPU.

Lightweight image-to-3D (~1B params, ~7GB VRAM) that fits an 8GB GPU.
run_sf3d takes a base64 PNG and returns the path to a generated GLB.

SF3D pins old deps (numpy 1.26, transformers 4.42) that conflict with the
backend, so it lives in its OWN venv and is invoked as a subprocess. Override
the interpreter / model dir via SF3D_VENV_PYTHON / SF3D_DIR in backend/.env.
"""
import base64
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_h = logging.StreamHandler(sys.stderr)
_h.setFormatter(logging.Formatter("%(asctime)s [sf3d_runner] %(message)s"))
log = logging.getLogger("sf3d_runner")
log.addHandler(_h)
log.setLevel(logging.DEBUG)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SF3D_DIR     = _REPO_ROOT / "rendering-pipeline" / "stable-fast-3d"
_DEFAULT_VENV_PYTHON  = _DEFAULT_SF3D_DIR / ".venv-sf3d" / "bin" / "python"

SF3D_DIR     = Path(os.getenv("SF3D_DIR",          str(_DEFAULT_SF3D_DIR)))
VENV_PYTHON  = Path(os.getenv("SF3D_VENV_PYTHON",  str(_DEFAULT_VENV_PYTHON)))
RUN_PY       = SF3D_DIR / "run.py"
PRETRAINED   = os.getenv("SF3D_MODEL", "stabilityai/stable-fast-3d")
# Low-poly knobs (the whole point of using SF3D on an 8GB card).
TEX_RES      = os.getenv("SF3D_TEXTURE_RES", "1536")     # texture atlas res; main visual lever
REMESH       = os.getenv("SF3D_REMESH", "none")          # none | triangle | quad
VERTEX_COUNT = os.getenv("SF3D_VERTEX_COUNT", "-1")      # -1 = model default
FG_RATIO     = os.getenv("SF3D_FOREGROUND_RATIO", "0.85")  # how much of the frame the subject fills
TIMEOUT_SECS = int(os.getenv("SF3D_TIMEOUT", str(10 * 60)))

GLB_STORE = Path(__file__).parent / "glb_store"
GLB_STORE.mkdir(exist_ok=True)


def run_sf3d(image_b64: str, job_id: str) -> str:
    if not VENV_PYTHON.is_file():
        raise RuntimeError(
            f"SF3D venv Python not found at {VENV_PYTHON}. Create it first "
            "(see rendering-pipeline/stable-fast-3d) or set SF3D_VENV_PYTHON in backend/.env."
        )
    if not RUN_PY.is_file():
        raise RuntimeError(f"SF3D run.py not found at {RUN_PY}. Set SF3D_DIR in backend/.env.")

    with tempfile.TemporaryDirectory(prefix=f"sf3d_{job_id}_") as tmp:
        tmp_path = Path(tmp)
        input_img = tmp_path / "input.png"
        input_img.write_bytes(base64.b64decode(image_b64))
        out_dir = tmp_path / "out"

        cmd = [
            str(VENV_PYTHON), str(RUN_PY), str(input_img),
            "--output-dir", str(out_dir),
            "--pretrained-model", PRETRAINED,
            "--device", "cuda",
            "--texture-resolution", TEX_RES,
            "--foreground-ratio", FG_RATIO,
            "--remesh_option", REMESH,
        ]
        if VERTEX_COUNT and VERTEX_COUNT != "-1":
            cmd += ["--target_vertex_count", VERTEX_COUNT]

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0"
        # expandable_segments reclaims the ~400MB PyTorch otherwise strands to
        # fragmentation during texture baking — required for TEX_RES >= 1536 to
        # fit the 8GB card (1024 fits without it). Respect an explicit override.
        env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        hf = os.getenv("HF_TOKEN", "")
        if hf and not hf.startswith("your_"):
            env["HF_TOKEN"] = hf
            env["HUGGING_FACE_HUB_TOKEN"] = hf

        log.info("Running SF3D (timeout=%ds): %s", TIMEOUT_SECS, " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, cwd=str(SF3D_DIR), env=env, timeout=TIMEOUT_SECS,
                check=False, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"SF3D timed out after {TIMEOUT_SECS}s")

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "")[-600:]
            log.error("SF3D failed (rc=%s): %s", result.returncode, tail)
            raise RuntimeError(f"SF3D exited {result.returncode}: {tail or '(no output)'}")

        # run.py writes {output_dir}/0/mesh.glb for a single input image
        produced = out_dir / "0" / "mesh.glb"
        if not produced.exists():
            raise RuntimeError(f"SF3D output GLB not found at {produced}")

        dest = GLB_STORE / f"{job_id}.glb"
        shutil.move(str(produced), str(dest))
        log.info("GLB saved → %s", dest)
        return str(dest)
