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

# Import logging for better debugging
import logging
logger = logging.getLogger(__name__)

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

import shutil  # for copying processed screenshot


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
         # cache last screenshot parse
         self._last_image_path: Optional[pathlib.Path] = None
         self._last_parsed: Optional[dict] = None

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
            "--device", "cpu",  # Force CPU to avoid CUDA issues
            "--BOX_TRESHOLD", "0.15",
            "--port", str(port),
        ]

        print(f"Launching OmniParser on :{port}")
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
                    logger.info(f"[OmniParser Server] {line.rstrip()}")
                if self.server_process.poll() is not None:
                    break

        threading.Thread(target=_tail, daemon=True).start()

        t0 = time.time()
        while time.time() - t0 < 120:
            if self.server_process.poll() is not None:
                logger.error("❌ OmniParser exited.")
                # Try to get exit code and any stderr
                exit_code = self.server_process.returncode
                stderr_output = ""
                if self.server_process.stderr:
                    try:
                        stderr_output = self.server_process.stderr.read()
                    except:
                        pass
                logger.error(f"Exit code: {exit_code}, stderr: {stderr_output}")
                return False
            try:
                if requests.get(f"http://localhost:{port}/probe/", timeout=3).status_code == 200:
                    logger.info(f"✅ Ready at http://localhost:{port}")
                    return True
            except requests.RequestException as e:
                logger.debug(f"Probe failed: {e}")
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
        img_path = pathlib.Path(image_path)

        # Reuse if cached
        # if we already parsed this exact file, re-use the result
        if self._last_image_path == img_path and self._last_parsed is not None:
            print("♻️ Re-using cached parse result")
            return self._last_parsed

        url = f"{self.server_url}/parse/"

        for label, encoded in _encoding_sequence(img_path):
            logger.info(f"[DEBUG] Sending {label} → {len(encoded):,} bytes to {url}")
            try:
                logger.info(f"[DEBUG] Making POST request to {url} with timeout=120")
                r = requests.post(url, json={"base64_image": encoded}, timeout=120)
                logger.info(f"[DEBUG] Response status code: {r.status_code}")
                logger.info(f"[DEBUG] Response headers: {dict(r.headers)}")
                r.raise_for_status()
                
                raw_response = r.text
                logger.info(f"[DEBUG] Raw response length: {len(raw_response)} characters")
                logger.info(f"[DEBUG] Raw response preview: {raw_response[:200]}...")
                
                parsed = r.json()
                logger.info(f"[DEBUG] Parsed JSON type: {type(parsed)}")
                logger.info(f"[DEBUG] Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")

                # ← HERE ←
                if not isinstance(parsed, dict) or "parsed_content_list" not in parsed:
                    logger.warning(f"⚠️ Unexpected response structure: {parsed}")
                    return None

                # Convert parsed_content_list → coords (legacy format expected by mapper)
                if isinstance(parsed.get("parsed_content_list"), list):
                    coords = []
                    for item in parsed["parsed_content_list"]:
                        logger.info(f"📦 Parsed Item: {json.dumps(item, indent=2)}")
                        coords.append({
                            "bbox": item["bbox_normalized"] if isinstance(item.get("bbox_normalized"), list) else [0, 0, 0, 0],
                            "content": item.get("content", ""),
                            "type": item.get("type", ""),
                            "interactivity": item.get("interactivity", False),
                            "source": item.get("source", ""),
                        })
                    parsed["coords"] = coords
                    logger.info(f"✅ Converted {len(coords)} items to coords")

                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()

                if "som_image_base64" in parsed:
                    out = pathlib.Path(__file__).with_name("processed_screenshot.png")
                    out.write_bytes(base64.b64decode(parsed["som_image_base64"]))
                    logger.info(f"🖼️  Overlay saved → {out}")
                    try:
                        gui_dest = PROJECT_ROOT / "gui" / "static" / "processed_screenshot.png"
                        shutil.copy2(out, gui_dest)
                        logger.info(f"[DEBUG] Copied processed screenshot to GUI static: {gui_dest}")
                    except Exception as e:
                        logger.error(f"[ERROR] Could not copy processed screenshot to GUI static: {e}")

                    logger.info(f"✅ Parsed OK with {label}")

                    # cache and return
                    self._last_image_path = img_path
                    self._last_parsed = parsed
                    return parsed

            except requests.HTTPError as e:
                logger.error(f"❌ HTTPError ({r.status_code}) after {label}: {e}")
                logger.error(f"Response text: {r.text[:1000]}")  # Log response content for debugging
                if r.status_code >= 500 and label == "RAW":
                    logger.warning("⚠️ 5xx on RAW – retrying with JPEG…")
                    continue
                return None
            except requests.RequestException as e:
                logger.error(f"❌ Request failed: {e}")
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
