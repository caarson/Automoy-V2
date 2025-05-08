![Automoy Platform Logo](https://cloud.innovatingsustainabletechnology.com/apps/files_sharing/publicpreview/SL7ayF37TPessQT?file=/\&fileId=317\&x=3840\&y=2160\&a=true\&etag=4a4d71d889fe7f610d7c18700daf40f5)

# Automoy V2

**Automoy** is a modular, GPU-accelerated autonomous agent framework that blends LLM reasoning, visual parsing, and real-world OS-level control.

Originally based on [Self-Operating Computer by OthersideAI](https://github.com/OthersideAI/self-operating-computer), Automoy has evolved into a full-stack, pluggable system capable of UI automation, screen parsing, and soon, robotics.

> **Automoy turns screenshots and objectives into action.**

---

## ✨ What's New in V2?

* Full **GPU acceleration** for OCR and computer vision tasks
* **OmniParser**-based UI analysis
* Modular support for **LLMs** like Deepseek, Ollama, GPT-4, Mistral
* **Web UI (God Mode)** for real-time monitoring, task queue, and execution feedback
* Structured **plugin and script support**
* **Installer for one-click setup** on Windows

---

## 🧠 Project Overview

```
automoy-v2/
├── config/               # Config loader and runtime config.txt/py
│   ├── config.py
│   └── config.txt
│
├── core/
│   ├── main.py           # Entrypoint
│   ├── operate.py        # Main Automoy execution logic
│   ├── prompts.py        # Prompt crafting
│   ├── lm_interface.py   # Core LLM interface (used in legacy and current modules)
│   ├── exceptions.py     # Custom exception handling
│   ├── lm_interfaces/
│   │   ├── main_interface.py
│   │   └── handlers/     # LLM input/output formatters
│   ├── utils/
│   │   ├── omniparser/   # OmniParser interface and sample output
│   │   ├── operating_system/
│   │   │   └── os_interface.py
│   │   ├── region/       # Region mapping and coordinate translation
│   │   │   ├── mapper.py
│   │   │   └── area_selector.py
│   │   ├── vmware/       # VMWare controller interface
│   │   └── web_scraping/ # Scraping and HTML UI parsing
│
├── dependencies/
│   └── OmniParser-master/ # OmniParser engine directory
│
├── evaluations/          # Benchmarking + test scripts
│
├── gui/
│   ├── gui.py            # FastAPI frontend + control panel
│   ├── static/           # Web assets (JS, CSS)
│   └── templates/        # HTML templates
│
├── installer/
│   ├── setup.py          # Launch installer
│   ├── conda_setup.py
│   ├── cuda_setup.py
│   ├── omniparser_setup.py
│   ├── vmware_setup.py
│   ├── requirements.txt
│   ├── downloads/
│   └── aria2c.exe        # Download utility
│
├── scripts/              # Custom automation routines
├── README.md
```

---

## 🤖 How Automoy Works

1. **Screenshot Taken** (manually or on loop)
2. **OmniParser parses UI elements** from image
3. **LLM interprets context and decides next step**
4. **Automoy acts** (mouse clicks, keyboard input, etc.)

> Automoy "sees" the desktop, "thinks" about what to do, and then "acts" on the system directly.

---

## 📅 System Requirements

### Minimum:

* 2GB VRAM GPU
* 8GB RAM
* CUDA 11.8+

### Recommended:

* 16GB RAM
* RTX-class GPU (3060+)

> Automoy requires **CUDA** to accelerate visual tasks. If CUDA is misconfigured, Automoy will not launch.

### OS Support:

* **Windows 10+ (official)**
* **Linux**: community support coming soon
* **macOS**: Not supported

---

## 🛠️ AMD GPU Support (Experimental)

CUDA is NVIDIA-exclusive, but the following projects offer possible AMD compatibility:

* [SCALE Toolkit](https://wccftech.com/nvidia-cuda-directly-run-on-amd-gpus-using-scale-toolkit/) – CUDA-on-AMD translation layer
* [ZLUDA](https://www.xda-developers.com/nvidia-cuda-amd-zluda/) – Converts CUDA binaries to Intel/AMD-compatible code

These are **not officially supported**, but adventurous users may test and report results.

---

## 🚀 Roadmap

* [IN-P] Web-based control panel (God Mode)
* [IN-P] Script/plugin loader with hot-reload capability
* [x] CUDA installer w/ PyTorch verification for GPU acceleration
* [ ] Multi-screen support for wider operational contexts
* [ ] OCR fallback pipeline to support CPU-only environments
* [ ] Real-time frame analysis loop (stream-based parsing for dynamic UI)
* [ ] OpenCL + integrated graphics support (non-CUDA fallback and broader hardware support)
* [ ] Portable Automoy OS under `os/` (USB-bootable image for appliance deployment)
* [ ] MOE (Mixture of Experts) agent logic and critical reasoning support
* [ ] Advanced geometric reasoning and spatial awareness via vision model extensions
* [ ] NVIDIA Isaac Sim integration (robotics interfaces modularized under `utils/`)
* [ ] Circuit simulator integration for electrical prototyping (e.g. Falstad, ngspice)
* [ ] Support for additional simulation tools (physics, CAD, electronics, or virtual environments)
* [ ] Adaptive manufacturing mode: Automoy as an orchestrator of physical/digital manufacturing workflows (via robotic arm + sensors)

---

## 🔧 Installation

1. Clone the repo
2. Navigate to `/installer`
3. Run `setup.py` or use `aria2c.exe` to fetch dependencies
4. Launch `main.py` from `core/`

---

## ✨ Bonus: Touchscreen + RGB Support (Optional)

Automoy can be deployed in custom hardware:

* Touchscreens (5"–7" HDMI + USB)
* RGB lighting (WS2812 via ESP32 or Arduino)
* 3D-printed cases for standalone or rack-mounted setups

This makes Automoy a physical, interactive AI agent appliance.

---

## 📚 License & Acknowledgments

* Based on original ideas from OthersideAI
* OmniParser integration by Microsoft
* Inspired by the vision of local-first, agentic computing

**Built by Technologies-AI**
