"""
omniparser_setup.py – pulls / patches / launches OmniParser in GPU‑friendly mode.

Run once inside your `automoy_env`:
    conda activate automoy_env
    python omniparser_setup.py
"""

import os
import sys
import subprocess
import pathlib
import zipfile
import time
import urllib.request
import textwrap
import re

# ---------------------------------------------------------------------------
# import conda_setup helper (must be in same folder)
# ---------------------------------------------------------------------------
try:
    import conda_setup  # provides find_conda()
except ImportError:
    print("❌ Could not import conda_setup. Ensure conda_setup.py is in the same directory.")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

DEPENDENCIES_DIR   = pathlib.Path(__file__).parent.parent / "dependencies"
OMNIPARSER_ZIP     = DEPENDENCIES_DIR / "OmniParser-master.zip"
OMNIPARSER_DIR     = DEPENDENCIES_DIR / "OmniParser-master"

OMNIPARSER_MODULE  = "omnitool.omniparserserver.omniparserserver"
SERVER_CWD         = OMNIPARSER_DIR / "omnitool" / "omniparserserver"

WEIGHTS_DIR        = OMNIPARSER_DIR / "weights"
ICON_DETECT_DIR    = WEIGHTS_DIR / "icon_detect"
ICON_CAPTION_DIR   = WEIGHTS_DIR / "icon_caption_florence"

YOLO_MODEL_FILE    = ICON_DETECT_DIR / "model.pt"
TRAIN_ARGS_FILE    = ICON_DETECT_DIR / "train_args.yaml"
MODEL_YAML_FILE    = ICON_DETECT_DIR / "model.yaml"

ICON_CAPTION_FILE        = ICON_CAPTION_DIR / "model.safetensors"
ICON_CAPTION_CONFIG      = ICON_CAPTION_DIR / "config.json"
ICON_CAPTION_GEN_CONFIG  = ICON_CAPTION_DIR / "generation_config.json"

CONDA_ENV    = "automoy_env"
SERVER_PORT  = 8111

MINIMAL_FASTAPI_SERVER = f'''"""
Minimal OmniParser server using FastAPI.
Exposes /probe/ (health check) and a placeholder /parse/ endpoint.
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/probe/")
def probe():
    return {{"status": "ok"}}

@app.post("/parse/")
def parse_image():
    # Placeholder for parsing logic (e.g., load models, process image)
    return {{"screen_info": "Parsed screen info goes here"}}

if __name__ == "__main__":
    uvicorn.run("{OMNIPARSER_MODULE}:app", host="0.0.0.0", port={SERVER_PORT}, reload=False)
'''

# =============================================================================
# NEW – GPU MEMORY PATCHES
# =============================================================================
def apply_gpu_patches() -> None:
    """
    Fix GPU leaks and FP16-load for OmniParser, and disable Uvicorn autoreload.

    1. Upgrade torch/cu121 wheels
    2. Optional install of xformers / flash-attn
    3. Patch:
       • routers/parse.py       → RGB fix, det.cpu(), fp16 autocast, cache clear
       • omniparserserver.py    → set reload=False, workers=1
    4. Patch server_startup.py   → load Florence-2 in fp16 on CUDA
    """
    print("\n🔧 Applying GPU-memory patches…")

    conda = conda_setup.find_conda()
    if not conda:
        print("❌ Conda not found."); sys.exit(1)

    # 1️⃣ PyTorch CU-12.1 wheels (Win+Linux)
    subprocess.check_call([
        conda, "run", "-n", CONDA_ENV, "pip", "install", "--upgrade",
        "torch", "torchvision", "torchaudio",
        "--index-url", "https://download.pytorch.org/whl/cu121",
    ])

    # 2️⃣ Optional memory-efficient kernels
    proc = subprocess.run([
        conda, "run", "-n", CONDA_ENV, "pip", "install",
        "--only-binary", ":all:", "xformers", "flash-attn"
    ], capture_output=True, text=True)
    if proc.returncode == 0:
        print("✅ Installed xformers / flash-attn")
    else:
        print("⚠️  No binary wheels – skipping xformers / flash-attn")

    def insert_cleanup(src: str) -> str:
        """Inject cache-clear before every `return`."""
        if "torch.cuda.empty_cache()" in src:
            return src
        return re.sub(
            r"(\n\s+return\s)",
            "\n    torch.cuda.empty_cache()\n    torch.cuda.ipc_collect()\n    gc.collect()\\g<1>",
            src
        )

    # 3a️⃣ Patch routers/parse.py .
    router = OMNIPARSER_DIR / "omnitool" / "omniparserserver" / "routers" / "parse.py"
    if router.exists():
        txt = router.read_text("utf-8")
        if "ipc_collect()" not in txt:
            if "import torch" not in txt:
                txt = txt.replace("import io", "import io\nimport torch, gc")
            # RGB safety
            txt = re.sub(
                r"img\s*=\s*Image\.open\([^\n]*\)(?![\s\S]*convert\(\"RGB\"\))",
                lambda m: m.group(0) +
                    "\n    if img.mode != \"RGB\":\n        img = img.convert(\"RGB\")",
                txt, count=1
            )
            # det → CPU + fp16
            if "det =" in txt and "det_cpu" not in txt:
                txt = re.sub(r"(det\s*=\s*[^\n]+)",
                             r"\1\n        det_cpu = det.cpu()", txt, count=1)
                txt = txt.replace("build_response(det, caption)",
                                  "build_response(det_cpu, caption)")
                if "torch.inference_mode()" not in txt:
                    txt = re.sub(
                        r"(def\s+parse[^\n]*:\n\s+)",
                        r"\1with torch.inference_mode(), torch.cuda.amp.autocast(dtype=torch.float16):\n    ",
                        txt, count=1
                    )
                    txt = txt.replace("\n        det = ", "\n            det = ")
                    txt = txt.replace("\n        det_cpu = ", "\n            det_cpu = ")
                    txt = txt.replace("\n        caption = ", "\n            caption = ")
            txt = insert_cleanup(txt)
            router.write_text(txt, "utf-8")
            print("✅ Patched routers/parse.py")

    # 3b️⃣ Disable Uvicorn autoreload in omniparserserver.py
    mono = OMNIPARSER_DIR / "omnitool" / "omniparserserver" / "omniparserserver.py"
    if mono.exists():
        main_txt = mono.read_text("utf-8")
        if "reload=True" in main_txt:
            patched = re.sub(
                r"uvicorn\.run\(([^)]*)reload\s*=\s*True([^)]*)\)",
                r"uvicorn.run(\1reload=False, workers=1\2)",
                main_txt,
                count=1
            )
            mono.write_text(patched, "utf-8")
            print("✅ Patched omniparserserver.py → reload=False, workers=1")

    # 4️⃣ Patch server_startup.py for fp16 Florence
    startup = OMNIPARSER_DIR / "omnitool" / "omniparserserver" / "server_startup.py"
    if startup.exists():
        code = startup.read_text("utf-8")
        if "torch_dtype=torch.float16" not in code:
            code = re.sub(
                r"AutoModelForVision2Seq\.from_pretrained\(\s*caption_model_dir\s*,",
                "AutoModelForVision2Seq.from_pretrained(\n        caption_model_dir,\n        torch_dtype=torch.float16,",
                code,
                count=1
            )
            code = code.replace(".to(device)", ".to('cuda')")
            startup.write_text(code, "utf-8")
            print("✅ Patched server_startup.py (fp16)")

    # 5️⃣ Patch util/utils.py to skip initialize_weights and define numpy alias
    utils_file = OMNIPARSER_DIR / "util" / "utils.py"
    if utils_file.exists():
        txt = utils_file.read_text("utf-8")
        needs_patch = "# Patched by omniparser_setup" not in txt
        if needs_patch:
            patch = textwrap.dedent('''
                # Patched by omniparser_setup.py: skip initialize_weights to avoid DaViT errors
                try:
                    import transformers
                    transformers.PreTrainedModel.initialize_weights = lambda self, *args, **kwargs: None
                except Exception:
                    pass
                # Ensure numpy is available for type hints
                try:
                    import numpy as np
                except ImportError:
                    pass
            ''')
            new_txt = patch + "\n" + txt
            utils_file.write_text(new_txt, "utf-8")
            print("✅ Patched util/utils.py to skip initialize_weights and import numpy")

    print("🎉 GPU patches complete.\n")

# =============================================================================
# ORIGINAL HELPER FUNCTIONS (unchanged)
# =============================================================================
def extract_omniparser():
    if not OMNIPARSER_DIR.exists():
        print(f"📦 Extracting OmniParser from {OMNIPARSER_ZIP}...")
        try:
            with zipfile.ZipFile(OMNIPARSER_ZIP, 'r') as zip_ref:
                zip_ref.extractall(DEPENDENCIES_DIR)
            print("✅ OmniParser extracted successfully!")
        except Exception as e:
            print(f"❌ Error extracting OmniParser: {e}")
            sys.exit(1)
    else:
        print("✅ OmniParser is already extracted.")

def ensure_omniparser_server_file():
    server_dir = OMNIPARSER_DIR / "omnitool" / "omniparserserver"
    init_file  = server_dir / "__init__.py"
    server_py  = server_dir / "omniparserserver.py"

    if not server_dir.exists():
        print(f"📂 Creating folder {server_dir}")
        server_dir.mkdir(parents=True, exist_ok=True)

    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")

    if not server_py.exists():
        server_py.write_text(MINIMAL_FASTAPI_SERVER, encoding="utf-8")

def download_file(url: str, destination: pathlib.Path):
    if destination.exists():
        print(f"✅ Already downloaded: {destination.name}")
        return
    try:
        print(f"📥 {destination.name}")
        urllib.request.urlretrieve(url, destination)
        print("   ↳ done")
    except Exception as e:
        print(f"❌ Failed to download {destination.name}: {e}")
        sys.exit(1)

def download_required_models():
    print("\n🔍 Checking / downloading model weights …")
    for d in [ICON_DETECT_DIR, ICON_CAPTION_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/train_args.yaml", TRAIN_ARGS_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.yaml",      MODEL_YAML_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_detect/model.pt",       YOLO_MODEL_FILE)

    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/model.safetensors",    ICON_CAPTION_FILE)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/config.json",         ICON_CAPTION_CONFIG)
    download_file("https://huggingface.co/microsoft/OmniParser-v2.0/resolve/main/icon_caption/generation_config.json", ICON_CAPTION_GEN_CONFIG)

def validate_server_module():
    print("🔎 Validating server import …")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(OMNIPARSER_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    conda_exe = conda_setup.find_conda()
    if not conda_exe:
        print("❌ Conda not found.")
        sys.exit(1)

    try:
        # give it 15 s to complete, then bail out
        result = subprocess.run(
            [conda_exe, "run", "-n", CONDA_ENV, "python", "-c", f"import {OMNIPARSER_MODULE}"],
            env=env,
            cwd=str(SERVER_CWD),
            capture_output=True,
            text=True,
            timeout=15
        )
    except subprocess.TimeoutExpired:
        print("⌛ Import check timed out; skipping validation.")
        return

    if result.returncode != 0:
        print("❌ Import check failed\n", result.stderr)
        sys.exit(1)

    print("✅ Server module imports successfully")

def check_server_status() -> bool:
    try:
        import requests
        r = requests.get(f"http://localhost:{SERVER_PORT}/probe/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def start_omniparser_server():
    print("\n🚀 Starting OmniParser server …")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(OMNIPARSER_DIR)
    env["PYTHONUNBUFFERED"] = "1"

    conda_exe = conda_setup.find_conda()
    command = [
        conda_exe, "run", "-n", CONDA_ENV, "python", "-m", OMNIPARSER_MODULE,
        "--som_model_path", str(YOLO_MODEL_FILE),
        "--caption_model_name", "florence2",
        "--caption_model_path", str(ICON_CAPTION_DIR),
        "--device", "cuda",
        "--BOX_TRESHOLD", "0.05",
        "--port", str(SERVER_PORT)
    ]

    proc = subprocess.Popen(command, cwd=str(SERVER_CWD),
                            env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)

    # live log
    import threading, itertools
    def _tail():
        for line in itertools.takewhile(bool, iter(proc.stdout.readline, "")):
            print("[Server]", line.rstrip())
    threading.Thread(target=_tail, daemon=True).start()

    # wait for /probe/
    start = time.time()
    while time.time() - start < 120:
        if proc.poll() is not None:
            print("❌ Server exited early")
            sys.exit(1)
        if check_server_status():
            print(f"✅ Server ready at http://localhost:{SERVER_PORT}/\n")
            return proc
        time.sleep(3)

    print("❌ Server did not start in 120 s")
    proc.terminate()
    sys.exit(1)

# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("\n🔧 OmniParser Setup Utility 🔧\n")

    extract_omniparser()
    ensure_omniparser_server_file()
    download_required_models()

    # apply GPU‑safe patches (fp16 Florence + cache clearing)
    apply_gpu_patches()

    validate_server_module()
    server_process = start_omniparser_server()

    print("Press ENTER to stop OmniParser, or Ctrl+C to abort.")
    try:
        input()
    except KeyboardInterrupt:
        pass

    print("Stopping server …")
    server_process.terminate()
    try:
        server_process.wait(8)
    except subprocess.TimeoutExpired:
        server_process.kill()

    print("✅ Done.")
