# NAI FaceDetailer (v0.2.0)

A professional desktop GUI application for [NovelAI](https://novelai.net) image generation, specializing in high-fidelity Text-to-Image (T2I) workflows and advanced automated face/eye correction.
Built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — supports macOS, Windows, and Linux.

## v0.2.0 Highlights

- **Dual-Stage Detection:** Internal use of both YOLOv8n (face) and a custom eye detector (`full_eyes_detect_v1.pt`) for superior results in character focus.
- **Refined TIPO (KGen-style):** High-impact tag expansion with aggressive pruning and a strict 50-tag limit for cleaner, more effective prompts.
- **Persistent Settings:** Automatic session saving and loading for Model, Resolution, CFG, and all key parameters.
- **Unified UI:** Slimmed down, focused interface with a fixed-size, reliable sidebar. (I2I and Inpaint tabs have been removed to optimize the v0.2.0 workflow).

---

## Screenshots

*(Screenshots will be added here)*

---

## Requirements

- Python 3.10 or higher
- A valid [NovelAI](https://novelai.net) account and API access token
- Internet connection (for initial package installation and image generation)

---

## Quick Start

1. **Get your NAI token** — Log in to [novelai.net](https://novelai.net), go to Account → API Keys
2. **Run setup** — creates `.venv` and installs all dependencies
3. **Launch the app** — open Settings and paste your token
4. **Generate**

### macOS / Linux

```bash
bash setup.sh   # First time only
bash run.sh     # Launch
```

### Windows

```bat
setup.bat       :: First time only
run.bat         :: Launch
```

---

## Configuration

On first launch, open **Settings** (bottom of the sidebar) and configure:

| Setting | Description |
|---------|-------------|
| **NAI Token** | Your NovelAI API access token |
| **Output Directory** | Folder where generated images are saved |
| **TIPO Model Path** | Path to a `.gguf` prompt-expansion model (optional) |
| **TIPO GPU Layers** | GPU offload layers for TIPO (`-1` = full GPU) |
| **Wildcard Directory** | Folder containing `*.txt` wildcard files (optional) |

---

## Features

### T2I — Text to Image

Generate high-quality images from text prompts with integrated enhancement tools.

| Feature | Description |
|---------|-------------|
| **KGen-style TIPO** | Expand short prompts into detailed tag lists using a local GGUF LLM with aggressive pruning. |
| **Ban Tags** | Remove specific tags from TIPO output (exact match, comma-separated) |
| **Golden Recipe** | Apply curated quality prefix/suffix and negative prompt boosts |
| **Art Style Presets** | Save and apply named tag sets (Prepend or Append) |
| **Wildcards** | Use `{filename}` syntax to randomly substitute tags from `.txt` files |
| **Auto Face Detailer** | Automatically chain into Face Detailer after T2I finishes for a seamless workflow. |
| **Model Swapping** | Use different NAI models for each stage (e.g., v4.5 for T2I, v3 for Face Detailer). |
| **Auto Generation** | Loop generation infinitely (∞) or N times with a configurable interval |

**Auto Generation:** Enable the `자동 생성` switch, choose ∞ or N회, set the interval in seconds, then click **Generate** to start. Click again to stop.

> **Tip:** Combine Wildcards + Auto Generation (∞) to batch-explore concepts overnight.

---

### Face Detailer

Fix distorted or low-quality faces and eyes in generated images automatically:

1. **Dual-Stage Detection:** YOLOv8 detects faces, followed by a custom detector (`full_eyes_detect_v1.pt`) for precise eye refinement.
2. **SAM** (Segment Anything Model) generates a precise pixel mask.
3. **NAI Inpaint** regenerates the masked region at high quality.

Models are **auto-downloaded on first use** to `~/.nai_studio/models/` — no manual action needed.

> **Tip:** Enable **Auto Face Detailer Workflow** in T2I settings for a one-click automated correction pipeline.

---

### Shared Settings

Available across all modules:

- **Model:** `nai-diffusion-4-5-curated` · `nai-diffusion-4-5-full` · `nai-diffusion-4-full` · `nai-diffusion-4-curated-preview` · `nai-diffusion-3` · `nai-diffusion-furry-3` · `nai-diffusion-2`
- **Resolution, Steps, CFG, Seed, CFG Rescale, Sampler, Noise Schedule**

---

## Model Downloads

### Detection Models (auto-downloaded)

| Model | Source | Description |
|-------|--------|-------------|
| `face_yolov8n.pt` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer/resolve/main/face_yolov8n.pt) | YOLOv8n Face Detection |
| `full_eyes_detect_v1.pt` | [Full Eyes Detection (Civitai)](https://civitai.com/models/330727/full-eyes-detection-adetailer) | Advanced Eye Detector (YOLOv8) |
| `sam_b.pt` | [Ultralytics](https://github.com/ultralytics/assets/releases/download/v8.3.0/sam_b.pt) | Segment Anything Model |

Downloaded automatically to: `~/.nai_studio/models/`

### TIPO Prompt Expansion (manual)

TIPO uses any GGUF-format model via [llama.cpp](https://github.com/ggml-org/llama.cpp).
Place the `.gguf` file anywhere and set its path in Settings → **TIPO Model Path**.

Example: `gemma4-tipo-ko-Q4_K_M.gguf` (place in `models/` directory)

---

## GPU Support

`setup.sh` / `setup.bat` auto-detects your hardware:

| Hardware | Backend | Detection |
|----------|---------|-----------|
| Apple Silicon | Metal (MPS) | macOS + arm64 |
| NVIDIA | CUDA 12.1 | `nvidia-smi` |
| AMD | ROCm 6.0 | `rocminfo` |
| Intel Arc | SYCL (IPEX) | `sycl-ls` |
| Other / CPU | CPU fallback | — |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Token not accepted | Regenerate at novelai.net → Account → API Keys |
| Face Detailer hangs on first run | Downloading models (~200 MB) — check console for progress |
| TIPO does nothing | Verify TIPO Model Path in Settings and that the `.gguf` file exists |
| `429 Too Many Requests` | NAI rate limit — app auto-retries after 60 seconds |

---

## References & Credits

| Project | Use | License |
|---------|-----|---------|
| [NovelAI](https://novelai.net) | Image generation API | — |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | GUI framework | MIT |
| [Ultralytics](https://github.com/ultralytics/ultralytics) | YOLOv8 face detection + SAM segmentation | AGPL-3.0 |
| [KGen / z-tipo-extension](https://github.com/KohakuBlueleaf/KGen) | TIPO tag expansion logic (Refined) | Apache 2.0 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | GGUF inference engine for TIPO | MIT |
| [Pillow](https://github.com/python-pillow/Pillow) | Image processing | HPND |
| [PyTorch](https://github.com/pytorch/pytorch) | Deep learning backend | BSD-3-Clause |
| [Hugging Face Hub](https://github.com/huggingface/huggingface_hub) | Model download | Apache 2.0 |
| [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) | Pretrained face detection model | — |
| [Full Eyes Detection (Civitai)](https://civitai.com/models/330727/full-eyes-detection-adetailer) | Eye detection model (YOLOv8) | — |
| [guon/hand-eyes (Hugging Face)](https://huggingface.co/guon/hand-eyes) | Model hosting | — |

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
details.
