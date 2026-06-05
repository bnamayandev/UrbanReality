# UrbanForge — Session Context
> Resume from any device. Read this before asking Claude anything.
> Last updated: 2026-05-30

---

## What this project is

**UrbanForge** — NVIDIA Hackathon 2026 (Toronto, Urban Operations track). 6-person team, 36-hour build.

AI-powered urban development intelligence: place a proposed building anywhere on a Toronto 3D map, get instant AI impact analysis (environmental, traffic, economic, infrastructure, housing). Current local stack: **qwen3:8b** (Ollama) for analysis, **gemini-3.1-flash-image** for the 2D preview, and **Stable Fast 3D** for the 3D model — all on a single 8 GB GPU (LLM and SF3D run sequentially).

Full spec: open `project-blueprint.html` in a browser.

---

## Team

| Person | Role |
|--------|------|
| Omar | Data Engineer — `omar/data` branch |
| Ben | 3D Rendering / Maps  |
| Rehan | 2D Image Rendering  |
| Ahmed | AI / ML Engineer |
| Yusuf | Integration Lead + AI / ML |
| Wali | FrontEnd and Backend Engineer |

---

## Hardware — DGX Spark

- **SSH:** `ssh asus@100.93.45.108` (user: `asus`, not `ahmed`)
- **GPU:** NVIDIA GB10 Grace Blackwell Superchip, CUDA 13.0
- **Repo on GPU:** `~/UrbanForge/`
- **Venv:** `~/venv/` — always `source ~/venv/bin/activate` first

### Models already downloaded (via Ollama)
| Model | Size | Use |
|-------|------|-----|
| `nemotron-3-super:latest` | 86 GB | Primary — best quality, slow (~45s/response) |
| `nemotron3:33b` | 27 GB | Faster alternative for demo |
| `qwen3.6:35b` | 23 GB | Backup — already tested working |
| `gemma4:26b` | 17 GB | Backup |

**Qwen** also runs via llama.cpp (port 8000): `./run_qwen3.6.sh` (chmod +x first)

> **Local dev (single 8 GB GPU):** the app now runs `qwen3:8b` (Ollama) + Stable Fast 3D locally; the DGX/Nemotron models below are legacy from the original deploy target.

### Services
- **Ollama** (qwen3:8b): `ollama serve` → port 11434
- **FastAPI backend**: `uvicorn main:app --host 0.0.0.0 --port 8001 --reload`
- Run both in tmux: `tmux new -s <name>`, detach with Ctrl+B then D

---

