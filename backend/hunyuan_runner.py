"""
Runs Hunyuan3D-2mini SHAPE + texture generation locally via subprocess on the local GPU.

High-detail image-to-3D (0.6B shape DiT). On the dev box's 8GB RTX 3070 it peaks
~4GB (shape only) or ~6.8GB (textured) at octree 256 and produces ~17x the geometry
of SF3D. Texturing uses front-projection by default: the input image is projected
directly onto the mesh via orthographic X/Y UV, so building facade colors are exact.
run_hunyuan takes a base64 PNG and returns the path to a GLB.

Like SF3D, Hunyuan pins deps that conflict with the backend, so it lives in its
OWN venv and is invoked as a subprocess. Override interpreter / repo dir via
HUNYUAN_VENV_PYTHON / HUNYUAN_DIR in backend/.env.
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
_h.setFormatter(logging.Formatter("%(asctime)s [hunyuan_runner] %(message)s"))
log = logging.getLogger("hunyuan_runner")
log.addHandler(_h)
log.setLevel(logging.DEBUG)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DIR    = _REPO_ROOT / "rendering-pipeline" / "hunyuan3d-2"
_DEFAULT_PYTHON = _DEFAULT_DIR / ".venv-hunyuan" / "bin" / "python"

HUNYUAN_DIR    = Path(os.getenv("HUNYUAN_DIR",          str(_DEFAULT_DIR)))
VENV_PYTHON    = Path(os.getenv("HUNYUAN_VENV_PYTHON",  str(_DEFAULT_PYTHON)))
RUN_PY         = HUNYUAN_DIR / "run_shape.py"
MODEL_PATH     = os.getenv("HUNYUAN_MODEL",     "tencent/Hunyuan3D-2mini")
SUBFOLDER      = os.getenv("HUNYUAN_SUBFOLDER", "hunyuan3d-dit-v2-mini")
# Quality / VRAM knobs. octree is the geometry-detail lever (16-512); ~4GB peak
# at 256 leaves headroom on the 8GB card to push higher within the time budget.
OCTREE         = os.getenv("HUNYUAN_OCTREE",     "256")
STEPS          = os.getenv("HUNYUAN_STEPS",      "30")
GUIDANCE       = os.getenv("HUNYUAN_GUIDANCE",   "5.0")
NUM_CHUNKS     = os.getenv("HUNYUAN_NUM_CHUNKS", "8000")
MAX_FACES      = os.getenv("HUNYUAN_MAX_FACES",  "80000")
# Texture (multiview paint). On by default; needs the compiled texgen ext.
TEXTURE        = os.getenv("HUNYUAN_TEXTURE", "1").strip().lower() not in ("0", "false", "no", "")
# Generous default: a cold run downloads ~2-4GB of paint/delight weights (~10min
# on a slow link). Warm runs are ~75s. Bump down once weights are cached if you like.
TIMEOUT_SECS   = int(os.getenv("HUNYUAN_TIMEOUT", str(20 * 60)))

GLB_STORE = Path(__file__).parent / "glb_store"
GLB_STORE.mkdir(exist_ok=True)


def run_hunyuan(image_b64: str, job_id: str) -> str:
    if not VENV_PYTHON.is_file():
        raise RuntimeError(
            f"Hunyuan venv Python not found at {VENV_PYTHON}. Create it first "
            "(see rendering-pipeline/hunyuan3d-2) or set HUNYUAN_VENV_PYTHON in backend/.env."
        )
    if not RUN_PY.is_file():
        raise RuntimeError(f"Hunyuan run_shape.py not found at {RUN_PY}. Set HUNYUAN_DIR in backend/.env.")

    with tempfile.TemporaryDirectory(prefix=f"hunyuan_{job_id}_") as tmp:
        tmp_path = Path(tmp)
        input_img = tmp_path / "input.png"
        input_img.write_bytes(base64.b64decode(image_b64))
        out_glb = tmp_path / "mesh.glb"

        cmd = [
            str(VENV_PYTHON), str(RUN_PY), str(input_img),
            "--output", str(out_glb),
            "--model-path", MODEL_PATH,
            "--subfolder", SUBFOLDER,
            "--device", "cuda",
            "--octree-resolution", OCTREE,
            "--steps", STEPS,
            "--guidance-scale", GUIDANCE,
            "--num-chunks", NUM_CHUNKS,
            "--max-faces", MAX_FACES,
        ]
        if TEXTURE:
            cmd.append("--texture")

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0"
        # Reclaim fragmented VRAM, mirroring the SF3D runner. Respect an override.
        env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        hf = os.getenv("HF_TOKEN", "")
        if hf and not hf.startswith("your_"):
            env["HF_TOKEN"] = hf
            env["HUGGING_FACE_HUB_TOKEN"] = hf

        log.info("Running Hunyuan (timeout=%ds): %s", TIMEOUT_SECS, " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, cwd=str(HUNYUAN_DIR), env=env, timeout=TIMEOUT_SECS,
                check=False, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Hunyuan timed out after {TIMEOUT_SECS}s")

        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "")[-600:]
            log.error("Hunyuan failed (rc=%s): %s", result.returncode, tail)
            raise RuntimeError(f"Hunyuan exited {result.returncode}: {tail or '(no output)'}")

        if not out_glb.exists():
            raise RuntimeError(f"Hunyuan output GLB not found at {out_glb}")

        dest = GLB_STORE / f"{job_id}.glb"
        shutil.move(str(out_glb), str(dest))
        log.info("GLB saved → %s", dest)
        return str(dest)
