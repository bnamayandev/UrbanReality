"""
TRELLIS.2 image-to-3D converter.
Usage: python example.py <path_to_image>
Output: sample.glb in the current directory (~/TRELLIS.2/)
"""
import sys
import os
from pathlib import Path

from PIL import Image


def main():
    if len(sys.argv) < 2:
        print("Usage: python example.py <image_path>", file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]
    print(f"[TRELLIS.2] Loading image: {image_path}")
    image = Image.open(image_path).convert("RGB")

    print("[TRELLIS.2] Loading pipeline...")
    from trellis.pipelines import TrellisImageTo3DPipeline  # noqa: E402

    pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large-500M")
    pipeline.cuda()

    print("[TRELLIS.2] Running inference...")
    outputs = pipeline.run(image, seed=42)

    print("[TRELLIS.2] Exporting GLB...")
    from trellis.utils import postprocessing_utils  # noqa: E402

    glb = postprocessing_utils.to_glb(
        outputs["gaussian"][0],
        outputs["mesh"][0],
        simplify=0.95,
        texture_size=1024,
    )

    out_path = Path(__file__).parent / "sample.glb"
    glb.export(str(out_path))
    print(f"[TRELLIS.2] Saved: {out_path}")


if __name__ == "__main__":
    main()
