![Automation Platform Logo](https://cloud.innovatingsustainabletechnology.com/apps/files_sharing/publicpreview/SL7ayF37TPessQT?file=/&fileId=317&x=3840&y=2160&a=true&etag=4a4d71d889fe7f610d7c18700daf40f5)

# What is Automoy-V2?
The project is originally derived from [Self-Operating Computer by OthersideAI](https://github.com/OthersideAI/self-operating-computer). Automoy extends on this API and makes deploying an autonomous agent easy.

This version utilizes **GPU acceleration** for OCR and object recognition tasks.

Automoy is built for **Deepseek, Ollama, and GPT**. Currently, **Claude and Gemini are not supported**, though this may change as the project evolves.

Version two integrates **Microsoft's OmniParser** for enhanced UI analysis and automation.

---

## Project Structure
```
automoy-v2/
│
│── lmstudio/                # 🧠 LLM reasoning module using LM Studio (interprets UI data and makes automation decisions)
│
core/
│
├── main.py               # Primary entry point or CLI for "core" logic
├── operate.py            # High-level logic or “operation” routines
├── prompts.py            # Prompt definitions, templates, or generation logic
│
├── interfaces/           # (formerly lm_interfaces)
│   ├── __init__.py
│   ├── base_interface.py # If you have a base class or abstract class
│   ├── openai_interface.py
│   ├── huggingface_interface.py
│   └── ...               # Additional LLM-specific interfaces
│
├── utils/
│   ├── __init__.py
│   ├── helper_functions.py  # Utility functions, e.g. for logging, I/O
│   ├── config_loader.py     # If you have config load/parse logic
│   └── ...
│
│── evaluations/             # 🛠️ Testing and benchmarking (verifies system performance and accuracy)
│
│── robotics/                # 🤖 (Future) Robotics programming integration (enables hardware interaction and validation)
│
│── gui/                     # 🖥️ Web UI for user interaction (provides a frontend interface for controlling Automoy)
│
│── config/                  # ⚙️ Configuration files (stores global settings and user preferences)
│
│── utils/                   # 🔧 Helper functions (logging, debugging, and utility scripts for common tasks)
│
│── scripts/                 # 📝 Custom Python scripts (extensions, API integrations, and standalone automation tools)
│
│── installer/               # 📦 Installation scripts (handles setup, dependencies, and environment configuration)
│
│── README.md                # 📖 Documentation (project overview, setup instructions, and usage guide)
```

---

## How Does Automoy Function?
Automoy operates using **computer vision**, meaning it analyzes received images, extracts meaningful data, and executes logical actions to achieve an objective.

Currently, Automoy is designed for **computer automation**, but it will expand into **robotics** as the API matures and computer vision improves. Future iterations aim to support **real-time frame analysis**, enabling seamless interactions.

---

## Prerequisites
Automoy requires a **GPU with at least 2GB of VRAM**, along with **at least 4GB of free system RAM**. If the system relies on RAM caching, performance will be **significantly slower**. 

🔹 **Recommended system specifications:**  
- **Minimum:** 8GB system RAM (with swap space)  
- **Optimal:** 16GB system RAM for smooth performance  

🔹 **CUDA Requirement:**  
Automoy relies on **CUDA for GPU acceleration**. Before use, the application will verify:
1. **CUDA is properly configured**.
2. **The corresponding PyTorch package is installed**.

If CUDA is unable to be used or misconfigured, **the program will not start**.

🚀 **Tested on:** CUDA **11.8**  
❓ **Older CUDA versions:** May be compatible but remain untested. Feedback is appreciated!

🔹 **Supported Operating Systems:**  
- **Windows 10+ only (official support).**  
- **Other OS (Linux/macOS) might work with minor modifications, but are untested.**

---

## Running CUDA on AMD GPUs (Experimental)
While Automoy natively supports **NVIDIA CUDA**, there are **alternative toolchains** for AMD GPUs:

🔹 **SCALE Toolkit** (Run CUDA directly on AMD GPUs):  
[Read More](https://wccftech.com/nvidia-cuda-directly-run-on-amd-gpus-using-scale-toolkit/#:~:text=AnnouncementHardware-,NVIDIA%20CUDA%20Can%20Now%20Directly%20Run,GPUs%20Using%20The%20%E2%80%9CSCALE%E2%80%9D%20Toolkit)

🔹 **ZLUDA Toolkit** (Translates CUDA to AMD/Intel APIs):  
[Read More](https://www.xda-developers.com/nvidia-cuda-amd-zluda/#:~:text=The%20project%20was%20undertaken%20by,and%20Intel%20are%20now%20uninterersted.)

---

## Future Plans
🚀 **Automated installation & configuration** (including AMD GPU support) is planned, but Automoy remains **human-developed**, so expect slower iterations. 

For now, **users must manually install prerequisites**. Thank you for your patience!

---

## Installation:
Run setup.py from /installer.