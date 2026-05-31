"""
Handles SCP upload + SSH execution of TRELLIS.2 on the GX10,
then SCP downloads the resulting sample.glb.
"""
import base64
import os
import tempfile
from pathlib import Path

import paramiko
from dotenv import load_dotenv

load_dotenv()

GX10_HOST = os.getenv("GX10_HOST", "100.93.45.108")
GX10_USER = os.getenv("GX10_USER", "benjamin")
GX10_PORT = int(os.getenv("GX10_PORT", "22"))
REMOTE_ASSETS_DIR = "/home/benjamin/TRELLIS.2/assets/example_image"
REMOTE_TRELLIS_DIR = "/home/benjamin/TRELLIS.2"
REMOTE_OUTPUT_GLB  = "/home/benjamin/TRELLIS.2/sample.glb"
REMOTE_EXAMPLE_PY  = "/home/benjamin/TRELLIS.2/example.py"

GLB_STORE = Path(__file__).parent / "glb_store"
GLB_STORE.mkdir(exist_ok=True)


def _make_client() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        GX10_HOST,
        port=GX10_PORT,
        username=GX10_USER,
        timeout=30,
    )
    client.get_transport().set_keepalive(30)
    return client


def run_trellis(image_b64: str, job_id: str) -> str:
    """
    1. Decode base64 image → temp PNG
    2. SCP to GX10 assets dir
    3. SSH: conda run -n trellis2 python example.py <remote_path>
    4. SCP sample.glb back
    5. Return local GLB path
    """
    hf_token = os.getenv("HF_TOKEN", "")

    # Decode image to a local temp file
    raw = base64.b64decode(image_b64)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(raw)
        local_img = f.name

    remote_img = f"{REMOTE_ASSETS_DIR}/input_{job_id}.png"
    local_glb  = str(GLB_STORE / f"{job_id}.glb")

    client = _make_client()
    try:
        sftp = client.open_sftp()

        # Ensure remote assets dir exists
        try:
            sftp.stat(REMOTE_ASSETS_DIR)
        except FileNotFoundError:
            sftp.mkdir(REMOTE_ASSETS_DIR)

        # Upload image
        sftp.put(local_img, remote_img)
        sftp.close()

        # Run TRELLIS
        cmd = (
            f"cd {REMOTE_TRELLIS_DIR} && "
            f"HF_TOKEN={hf_token} "
            f"HF_HUB_DISABLE_XET=1 "
            f"conda run -n trellis2 --no-capture-output "
            f"python {REMOTE_EXAMPLE_PY} {remote_img}"
        )
        _, stdout, stderr = client.exec_command(cmd)
        # Block until done (TRELLIS can take several minutes)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err = stderr.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"TRELLIS exited {exit_status}: {err[:600]}")

        # Download GLB
        sftp = client.open_sftp()
        sftp.get(REMOTE_OUTPUT_GLB, local_glb)
        sftp.close()

    finally:
        client.close()
        Path(local_img).unlink(missing_ok=True)

    return local_glb
