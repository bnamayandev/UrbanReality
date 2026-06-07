"""
De-risk smoke test for Hunyuan3D-2mini SHAPE generation on an 8GB card.

Verifies: imports work (no compiled CUDA ops), the mini model loads, a mesh is
produced, and reports peak VRAM + wall time. Texture is NOT done here.

Usage: .venv-hunyuan/bin/python smoke_test.py [image_path] [octree_resolution]
"""
import sys
import time

import torch
from PIL import Image

from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.shapegen.pipelines import export_to_trimesh

IMG = sys.argv[1] if len(sys.argv) > 1 else "assets/demo.png"
OCTREE = int(sys.argv[2]) if len(sys.argv) > 2 else 256

print(f"torch {torch.__version__}  cuda_avail={torch.cuda.is_available()}", flush=True)

t0 = time.time()
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
    "tencent/Hunyuan3D-2mini",
    subfolder="hunyuan3d-dit-v2-mini",
    use_safetensors=True,
    device="cuda",
)
# Memory-efficient volume decode + skimage marching cubes (no custom CUDA build).
pipe.enable_flashvdm(mc_algo="mc")
print(f"model loaded in {time.time()-t0:.1f}s", flush=True)

image = Image.open(IMG).convert("RGB")
image = BackgroundRemover()(image)  # -> RGBA with alpha

torch.cuda.reset_peak_memory_stats()
t1 = time.time()
outputs = pipe(
    image=image,
    num_inference_steps=30,
    guidance_scale=5.0,
    octree_resolution=OCTREE,
    num_chunks=8000,
    output_type="mesh",
)
mesh = export_to_trimesh(outputs)[0]
gen_s = time.time() - t1
peak = torch.cuda.max_memory_allocated() / 1024 / 1024

out = f"/tmp/hunyuan_smoke_{OCTREE}.glb"
mesh.export(out)
print(f"OCTREE={OCTREE}  verts={len(mesh.vertices)}  faces={len(mesh.faces)}")
print(f"shape gen: {gen_s:.1f}s   PEAK VRAM: {peak:.0f} MB")
print(f"saved -> {out}")
