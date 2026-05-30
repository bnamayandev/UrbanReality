from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse
import torch, os
from PIL import Image
from trellis2.pipelines import Trellis2ImageTo3DPipeline
import o_voxel, io

app = FastAPI()
pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
pipeline.cuda()

@app.post("/generate")
async def generate(file: UploadFile):
    image = Image.open(io.BytesIO(await file.read()))
    mesh = pipeline.run(image)[0]
    mesh.simplify(16777216)
    glb = o_voxel.postprocess.to_glb(...)
    glb.export("/tmp/output.glb")
    return FileResponse("/tmp/output.glb")
