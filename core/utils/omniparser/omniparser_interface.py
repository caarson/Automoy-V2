"""
omniparser_interface.py · 2025‑05‑03
RAW‑first encode strategy + optional CUDA‑cache flush.
Saves the overlay image as processed_screenshot.png
"""

from __future__ import annotations

import base64
import io
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
from typing import Optional, Iterable

import requests

# torch is optional – used only to free CUDA cache if available
try:
    import torch
except ImportError:
    torch = None  # type: ignore

# Pillow is optional – used only for JPEG fallback
try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


# ───────────────────────── helper: locate conda ────────────────────────────
def _auto_find_conda() -> Optional[str]:
    conda = os.environ.get("CONDA_EXE")
    if conda and os.path.isfile(conda):
        return conda
    try:
        out = subprocess.check_output(["where", "conda"], shell=True, text=True)
        return next(line for line in out.splitlines() if line.strip())
    except Exception:
        return None


# ───────────────────────────── paths / constants ────────────────────────────
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]

DEFAULT_SERVER_CWD = PROJECT_ROOT / "dependencies" / "OmniParser-master" / \
    "omnitool" / "omniparserserver"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "dependencies" / "OmniParser-master" / \
    "weights" / "icon_detect" / "model.pt"
DEFAULT_CAPTION_MODEL_DIR = PROJECT_ROOT / "dependencies" / "OmniParser-master" / \
    "weights" / "icon_caption_florence"


# ───────────────────────── image encoding helpers ───────────────────────────
def _raw_b64(img_path: pathlib.Path) -> str:
    with img_path.open("rb") as f:
        return base64.b64encode(f.read()).decode()


def _jpeg_b64(img_path: pathlib.Path, max_dim: int) -> str:
    if Image is None:
        return _raw_b64(img_path)

    with Image.open(img_path) as im:
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()


def _encoding_sequence(img_path: pathlib.Path) -> Iterable[tuple[str, str]]:
    """RAW first, then 1920‑/1280‑/720‑pixel JPEGs."""
    yield "RAW", _raw_b64(img_path)
    for dim in (1920, 1280, 720):
        yield f"JPEG‑{dim}px", _jpeg_b64(img_path, dim)


# ─────────────────────────── main interface class ───────────────────────────
class OmniParserInterface:
    def __init__(self, server_url: str = "http://localhost:8111") -> None:
        self.server_url = server_url.rstrip("/")
        self.server_process: Optional[subprocess.Popen] = None

    # ――― context manager ―――
    def __enter__(self):
        if not self.server_process and not self.launch_server():
            raise RuntimeError("Failed to start OmniParser.")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop_server()

    # ――― server lifecycle ―――
    def launch_server(
        self,
        *,
        conda_path: Optional[str] = None,
        conda_env: str = "automoy_env",
        omiparser_module: str = "omniparserserver",
        cwd: Optional[str | os.PathLike] = None,
        port: int = 8111,
        model_path: Optional[str | os.PathLike] = None,
        caption_model_dir: Optional[str | os.PathLike] = None,
    ) -> bool:

        conda_path = conda_path or _auto_find_conda()
        if not conda_path:
            print("❌ Could not locate conda.")
            return False

        cwd = str(cwd or DEFAULT_SERVER_CWD)
        cmd = [
            conda_path, "run", "-n", conda_env,
            sys.executable, f"{omiparser_module}.py",
            "--som_model_path", str(model_path or DEFAULT_MODEL_PATH),
            "--caption_model_name", "florence2",
            "--caption_model_path", str(caption_model_dir or DEFAULT_CAPTION_MODEL_DIR),
            "--device", "cuda",
            "--BOX_TRESHOLD", "0.05",
            "--port", str(port),
        ]

        print(f"🚀 Launching OmniParser on :{port}")
        try:
            self.server_process = subprocess.Popen(
                cmd,
                cwd=cwd,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as e:
            print(f"❌ Spawn failed: {e}")
            return False

        def _tail():
            for line in iter(self.server_process.stdout.readline, ""):
                if line:
                    print("[Server]", line.rstrip())
                if self.server_process.poll() is not None:
                    break

        threading.Thread(target=_tail, daemon=True).start()

        t0 = time.time()
        while time.time() - t0 < 120:
            if self.server_process.poll() is not None:
                print("❌ OmniParser exited.")
                return False
            try:
                if requests.get(f"http://localhost:{port}/probe/", timeout=3).status_code == 200:
                    print(f"✅ Ready at http://localhost:{port}")
                    return True
            except requests.RequestException:
                pass
            time.sleep(2)

        print("❌ OmniParser did not become ready.")
        self.stop_server()
        return False

    def _check_server_ready(self) -> bool:
        """
        Check if the OmniParser HTTP API is up and responding.
        """
        try:
            resp = requests.get(f"{self.server_url}/probe/", timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def stop_server(self) -> None:
        if self.server_process and self.server_process.poll() is None:
            print("Stopping OmniParser...")
            self.server_process.terminate()
            try:
                self.server_process.wait(10)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
        self.server_process = None

    # ――― parse screenshot ―――
    def parse_screenshot(self, image_path: str | os.PathLike) -> Optional[dict]:
        """
        Parse the screenshot at *image_path*.
        On success:
          • saves overlay as 'processed_screenshot.png'
          • returns the full JSON result
        Returns None on any unrecoverable error.
        """
        img_path = pathlib.Path(image_path)
        url = f"{self.server_url}/parse/"

        for label, encoded in _encoding_sequence(img_path):
            print(f"[DEBUG] Sending {label} → {len(encoded):,} bytes")

            try:
                r = requests.post(
                    url,
                    json={"base64_image": encoded},
                    headers={"Content-Type": "application/json"},
                    timeout=120,
                )
                r.raise_for_status()
                parsed = r.json()

                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()  # avoid Florence hidden‑state leak

                if not isinstance(parsed, dict) or "coords" not in parsed:
                    print(f"⚠️ Unexpected response: {parsed}")
                    return None

                # save overlay if present
                if "som_image_base64" in parsed:
                    out_path = pathlib.Path(__file__).with_name("processed_screenshot.png")
                    with out_path.open("wb") as f:
                        f.write(base64.b64decode(parsed["som_image_base64"]))
                    print(f"🖼️  Overlay saved → {out_path}")

                print(f"✅ Parsed OK with {label}")
                return parsed

            except requests.HTTPError as e:
                if r.status_code >= 500 and label == "RAW":
                    print("⚠️ 5xx on RAW – retrying with JPEG...")
                    continue
                print(f"❌ HTTPError ({r.status_code}) after {label}: {e}")
                return None

            except requests.RequestException as e:
                print(f"❌ Request failed: {e}")
                return None

        return None


# ───────────────────────── CLI demo ─────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run OmniParser on screenshots.")
    parser.add_argument("images", nargs="*", help="image path(s)")
    parser.add_argument("--keep-alive", action="store_true",
                        help="Do not stop the server at the end")
    args = parser.parse_args()

    if not args.images:
        sample = PROJECT_ROOT / "core" / "utils" / "omniparser" / "sample_screenshot.png"
        if not sample.exists():
            print(f"❌ Sample screenshot missing at {sample}")
            sys.exit(1)
        print(f"No images given – using bundled sample: {sample}")
        args.images = [str(sample)]

    op = OmniParserInterface()
    if not op.launch_server():
        sys.exit(1)

    for img in args.images:
        res = op.parse_screenshot(img)
        print("🔍 Parsed:", json.dumps(res, indent=2)[:500], "...\n")

    if not args.keep_alive:
        op.stop_server()
