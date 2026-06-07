"""
Thin CLI entry for Hunyuan3D-2mini SHAPE generation + optional texture.

image -> high-detail GLB. Mirrors SF3D's run.py so backend/hunyuan_runner.py can
drive it as a subprocess in this repo's own venv (.venv-hunyuan).

Shape path is pure-PyTorch + skimage marching cubes (mc_algo='mc'), so it needs
no compiled CUDA ops — it runs on the dev box's CUDA toolkit 12.0.

Texturing uses front-projection by default: projects the input image orthographically
onto the mesh via X/Y vertex coordinates. This preserves the building's exact colors
and is instant (no extra model). Pass --texture-mode paint to use Hunyuan's multiview
diffusion paint instead (needs compiled CUDA ext, produces grey on buildings).
"""
import argparse
import gc
import time

import numpy as np
import torch
import trimesh
from PIL import Image

from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import (
    DegenerateFaceRemover,
    FaceReducer,
    FloaterRemover,
    Hunyuan3DDiTFlowMatchingPipeline,
)
from hy3dgen.shapegen.pipelines import export_to_trimesh


def _apply_projection_texture(mesh, image):
    """
    Triplanar projection: splits the mesh so every face has its own UV
    coordinates, then picks the projection axis (X/Y/Z) based on each
    face's dominant normal. Front/back faces get the full building image;
    side faces get the left/right edge strip; top/bottom faces get the
    top edge strip. Every face is covered — no grey missing-texture areas.
    """
    if image.mode == "RGBA":
        bg = Image.new("RGB", image.size, (180, 180, 180))
        bg.paste(image, mask=image.split()[3])
        img_rgb = bg
    else:
        img_rgb = image.convert("RGB")

    verts = np.array(mesh.vertices, dtype=np.float64)
    faces = np.array(mesh.faces)

    # Normalize vertex positions to [0, 1] on each axis
    bmin = verts.min(axis=0)
    bmax = verts.max(axis=0)
    brange = np.maximum(bmax - bmin, 1e-8)
    vn = (verts - bmin) / brange  # (V, 3)

    # Per-face normalized positions: (F, 3, 3) = [face, vert, xyz]
    fv = vn[faces]

    # Face normals (un-normalized — only sign/dominant axis matters)
    e1 = verts[faces[:, 1]] - verts[faces[:, 0]]
    e2 = verts[faces[:, 2]] - verts[faces[:, 0]]
    normals = np.cross(e1, e2)           # (F, 3)
    dom = np.argmax(np.abs(normals), axis=1)  # 0=X, 1=Y, 2=Z per face

    # Split the mesh: each face gets its own 3 vertices so UV seams are clean
    n_faces = len(faces)
    new_verts = verts[faces.reshape(-1)]          # (F*3, 3)
    new_faces = np.arange(n_faces * 3).reshape(n_faces, 3)
    fv_flat = fv.reshape(n_faces * 3, 3)          # (F*3, xyz)

    uvs = np.zeros((n_faces * 3, 2), dtype=np.float32)

    # X-dominant (left/right sides): project along Z and Y
    mask = np.repeat(dom == 0, 3)
    uvs[mask, 0] = fv_flat[mask, 2]   # z → u
    uvs[mask, 1] = fv_flat[mask, 1]   # y → v

    # Y-dominant (top/bottom): project along X and Z
    mask = np.repeat(dom == 1, 3)
    uvs[mask, 0] = fv_flat[mask, 0]   # x → u
    uvs[mask, 1] = fv_flat[mask, 2]   # z → v

    # Z-dominant (front/back): project along X and Y — the main facade view
    mask = np.repeat(dom == 2, 3)
    uvs[mask, 0] = fv_flat[mask, 0]   # x → u
    uvs[mask, 1] = fv_flat[mask, 1]   # y → v

    uvs = np.clip(uvs, 0.0, 1.0)

    result = trimesh.Trimesh(vertices=new_verts, faces=new_faces, process=False)
    material = trimesh.visual.material.PBRMaterial(
        baseColorTexture=img_rgb,
        metallicFactor=0.0,
        roughnessFactor=0.8,
    )
    result.visual = trimesh.visual.TextureVisuals(uv=uvs, material=material)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("image", type=str)
    p.add_argument("--output", required=True, help="output .glb path")
    p.add_argument("--model-path", default="tencent/Hunyuan3D-2mini")
    p.add_argument("--subfolder", default="hunyuan3d-dit-v2-mini")
    p.add_argument("--device", default="cuda")
    p.add_argument("--octree-resolution", type=int, default=256,
                   help="geometry detail; higher = finer + more VRAM/time (16-512)")
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--guidance-scale", type=float, default=5.0)
    p.add_argument("--num-chunks", type=int, default=8000,
                   help="lower = less peak VRAM during volume decode")
    p.add_argument("--max-faces", type=int, default=80000,
                   help="decimate to this face budget for web delivery; -1 = keep raw")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--texture", action="store_true",
                   help="apply texture to the output mesh (default mode: front-projection)")
    p.add_argument("--texture-mode", default="project", choices=["project", "paint"],
                   help="project=fast orthographic projection of input image (default); "
                        "paint=Hunyuan multiview diffusion (needs compiled CUDA ext)")
    p.add_argument("--texgen-model-path", default="tencent/Hunyuan3D-2",
                   help="repo holding the delight + multiview paint weights (paint mode only)")
    p.add_argument("--texgen-subfolder", default="hunyuan3d-paint-v2-0-turbo")
    args = p.parse_args()

    print(f"torch {torch.__version__} cuda={torch.cuda.is_available()}", flush=True)

    t0 = time.time()
    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        args.model_path, subfolder=args.subfolder,
        use_safetensors=True, device=args.device,
    )
    # Memory-efficient volume decode + skimage marching cubes (no custom CUDA build).
    pipe.enable_flashvdm(mc_algo="mc")
    print(f"model loaded in {time.time()-t0:.1f}s", flush=True)

    image = BackgroundRemover()(Image.open(args.image).convert("RGB"))

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    t1 = time.time()
    generator = torch.Generator().manual_seed(args.seed)
    outputs = pipe(
        image=image,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance_scale,
        generator=generator,
        octree_resolution=args.octree_resolution,
        num_chunks=args.num_chunks,
        output_type="mesh",
    )
    mesh = export_to_trimesh(outputs)[0]
    print(f"raw mesh: {len(mesh.vertices)} verts / {len(mesh.faces)} faces "
          f"in {time.time()-t1:.1f}s", flush=True)

    # Clean + decimate for web. Floater/degenerate removal first, then reduce.
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    if args.max_faces and args.max_faces > 0:
        mesh = FaceReducer()(mesh, max_facenum=args.max_faces)

    if args.texture:
        t2 = time.time()
        if args.texture_mode == "paint":
            # Hunyuan multiview diffusion paint. Needs compiled custom_rasterizer ext.
            # Produces generic grey on building images — use 'project' for buildings.
            del pipe
            gc.collect()
            torch.cuda.empty_cache()
            from hy3dgen.texgen import Hunyuan3DPaintPipeline
            paint = Hunyuan3DPaintPipeline.from_pretrained(
                args.texgen_model_path, subfolder=args.texgen_subfolder,
            )
            paint.enable_model_cpu_offload()
            print(f"paint model loaded in {time.time()-t2:.1f}s", flush=True)
            t3 = time.time()
            mesh = paint(mesh, image=image)
            print(f"texture (paint): {time.time()-t3:.1f}s", flush=True)
        else:
            # Front-projection: project the input image directly onto the mesh.
            # Instant, no extra model, preserves building facade colors exactly.
            mesh = _apply_projection_texture(mesh, image)
            print(f"texture (projection): {time.time()-t2:.3f}s", flush=True)

    if torch.cuda.is_available():
        peak = torch.cuda.max_memory_allocated() / 1024 / 1024
        print(f"PEAK VRAM: {peak:.0f} MB", flush=True)

    mesh.export(args.output)
    print(f"final mesh: {len(mesh.vertices)} verts / {len(mesh.faces)} faces", flush=True)
    print(f"saved -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
