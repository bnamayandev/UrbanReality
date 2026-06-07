#!/usr/bin/env bash
# Compile the Hunyuan texgen CUDA/C++ extensions into .venv-hunyuan.
# Needed only for textured output (HUNYUAN_TEXTURE=1); shape works without it.
#
# Why the gcc-12 dance: the dev box ships CUDA toolkit 12.0, whose nvcc only
# supports gcc <= 12, but the system gcc is 13. We point nvcc at gcc-12 via
# -ccbin so custom_rasterizer's .cu compiles (this is the wall TRELLIS2 hit).
set -euo pipefail
cd "$(dirname "$0")"

VPY="$(pwd)/.venv-hunyuan/bin/python"
[ -x "$VPY" ] || { echo "create .venv-hunyuan first"; exit 1; }

export CUDA_HOME="${CUDA_HOME:-/usr/lib/nvidia-cuda-toolkit}"
export PATH="$CUDA_HOME/bin:$PATH"
export CC=/usr/bin/gcc-12 CXX=/usr/bin/g++-12
export NVCC_PREPEND_FLAGS='-ccbin /usr/bin/g++-12'
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.6}"  # RTX 3070 = Ampere sm_86

"$VPY" -m pip install -q setuptools wheel pybind11 ninja 2>/dev/null || \
  uv pip install --python "$VPY" setuptools wheel pybind11 ninja

echo ">> building custom_rasterizer (CUDA)"
( cd hy3dgen/texgen/custom_rasterizer && "$VPY" setup.py install )
echo ">> building differentiable_renderer (C++)"
( cd hy3dgen/texgen/differentiable_renderer && "$VPY" setup.py install )

echo ">> verifying"
"$VPY" -c "import torch; import custom_rasterizer_kernel, mesh_processor; print('texgen ext OK')"
