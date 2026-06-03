"""
TRELLIS.2 image-to-3D converter.
Usage: python example.py <path_to_image>
Output: sample.glb next to this script
"""
import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import sys
from pathlib import Path

import torch
from PIL import Image


def _get_device():
    if torch.cuda.is_available():
        print(f"[TRELLIS.2] GPU: {torch.cuda.get_device_name(0)}")
        return "cuda"
    print("[TRELLIS.2] WARNING: no CUDA GPU found, falling back to CPU (will be slow)")
    return "cpu"


def main():
    if len(sys.argv) < 2:
        print("Usage: python example.py <image_path>", file=sys.stderr)
        sys.exit(1)

    device = _get_device()

    image_path = sys.argv[1]
    print(f"[TRELLIS.2] Loading image: {image_path}")
    image = Image.open(image_path).convert("RGB")

    print("[TRELLIS.2] Loading pipeline...")
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel

    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.cuda() if device == "cuda" else pipeline.cpu()

    print("[TRELLIS.2] Running inference...")
    mesh = pipeline.run(image)[0]
    mesh.simplify(16777216)  # nvdiffrast vertex limit

    print("[TRELLIS.2] Exporting GLB...")
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=1000000,
        texture_size=1024,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=False,
    )

    out_path = Path(__file__).parent / "sample.glb"
    glb.export(str(out_path), extension_webp=True)
    print(f"[TRELLIS.2] Saved: {out_path}")


if __name__ == "__main__":
    main()
