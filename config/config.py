import os
from pathlib import Path
from typing import Any, Dict, Tuple


class Config:
    """Lightweight configuration loader for Automoy.

    Reads *config.txt* **and** *environment.txt* (if present) that live in the
    same directory as this *config.py* file.  All values are parsed into Python
    types (bool, int, float, str).  ``environment.txt`` values override keys
    from ``config.txt`` when duplicates exist.
    """

    def __init__(self, base_dir: str | os.PathLike | None = None):
        self._base = Path(base_dir) if base_dir else Path(__file__).parent
        self._files: Dict[str, Path] = {
            "config": self._base / "config.txt",
            "environment": self._base / "environment.txt",
        }

        # Load both files (silently ignore environment.txt if missing)
        self._config_data = self._load_file(self._files["config"])
        self._env_data = (
            self._load_file(self._files["environment"])
            if self._files["environment"].exists()
            else {}
        )
        # Merge with precedence: environment > config
        self._data: Dict[str, Any] = {**self._config_data, **self._env_data}

    # --------------------------- Public helpers ---------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def get_env(self, key: str, default: Any = None) -> Any:
        return self._env_data.get(key, default)

    def get_api_source(self) -> Tuple[str, str]:
        if self.get("OPENAI", False) and self.get("OPENAI_API_KEY"):
            return "openai", self.get("OPENAI_API_KEY")
        if self.get("LMSTUDIO", False) and self.get("LMSTUDIO_API_URL"):
            return "lmstudio", self.get("LMSTUDIO_API_URL")
        raise ValueError(
            "No valid API configuration: set OPENAI or LMSTUDIO to True "
            "and provide key/url.")

    def get_temperature(self) -> float:
        return float(self.get("TEMPERATURE", 0.5))

    def get_model(self) -> str:
        source, _ = self.get_api_source()
        return self.get("OPENAI_MODEL" if source == "openai" else "LMSTUDIO_MODEL",
                        "gpt-4o" if source == "openai" else "deepseek-r1-distill-qwen-7b")

    def get_max_retries_per_step(self) -> int:
        return int(self.get("MAX_RETRIES_PER_STEP", 3)) # Default to 3 if not specified

    def get_max_consecutive_errors(self) -> int:
        return int(self.get("MAX_CONSECUTIVE_ERRORS", 5)) # Default to 5 if not specified

    # --------------------------- Internal parsing -------------------------

    def _load_file(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Configuration file '{path}' not found!")

        data: Dict[str, Any] = {}
        lines = path.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if not line or line.startswith("#"):
                continue

            if line.startswith("PROMPT"):
                rest = line.split(":", 1)[1].strip() if ":" in line else ""
                if rest:
                    data["PROMPT"] = rest; continue
                if i < len(lines) and lines[i].strip() == "\"":
                    i += 1
                prompt_lines = []
                while i < len(lines):
                    l = lines[i].rstrip("\n")
                    if l.strip() == "\"":
                        i += 1; break
                    prompt_lines.append(l); i += 1
                data["PROMPT"] = "\n".join(prompt_lines).strip(); continue

            if ":" in line:
                key, val = [s.strip() for s in line.split(":", 1)]
                val = val.split("#", 1)[0].strip()
                data[key] = self._convert_value(val)
        return data

    @staticmethod
    def _convert_value(val: str) -> Any:
        if val.lower() in {"true", "false"}:
            return val.lower() == "true"
        try:
            return float(val) if "." in val else int(val)
        except ValueError:
            return val


# ----------------------------- Manual test ------------------------------
if __name__ == "__main__":
    cfg = Config()

    print("------ MERGED CONFIGURATION ------")
    for k, v in cfg._data.items():
        print(f"{k}: {v}")
    print("----------------------------------")

    # Show key/value pairs parsed specifically from environment.txt
    print("------ ENVIRONMENT.TXT VALUES (parsed) ------")
    if cfg._env_data:
        for k, v in cfg._env_data.items():
            print(f"{k}: {v}")
    else:
        print("<no keys parsed – file missing or empty>")
    print("--------------------------------------------")

    # Raw contents of environment.txt (if present) for debugging
    env_path = cfg._files["environment"]
    print("------ ENVIRONMENT.TXT RAW CONTENT ------")
    if env_path.exists():
        print(env_path.read_text(encoding="utf-8"))
    else:
        print("environment.txt not found at", env_path)
    print("-----------------------------------------")

    # Summary helpers
    print("API source:", cfg.get_api_source())
    print("Model:", cfg.get_model())
    print("Temp:", cfg.get_temperature())

    prompt_val = cfg.get_env("PROMPT")
    if prompt_val:
        print("Prompt (env):" + prompt_val)

# ADDED: Instantiate Config and expose common variables at module level
_config_instance = Config()

# --- Core Application Settings ---
AUTOMOY_APP_NAME = _config_instance.get("AUTOMOY_APP_NAME", "Automoy")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Project root

# --- Logging Configuration ---
LOG_DIR = _config_instance.get("LOG_DIR", os.path.join(BASE_DIR, "debug", "logs"))
LOG_FILE_CORE = os.path.join(LOG_DIR, "core", "core.log")
LOG_FILE_GUI = os.path.join(LOG_DIR, "gui", "gui.log")
LOG_FILE_OMNIPARSER = os.path.join(LOG_DIR, "omniparser", "omniparser.log")
# Use LOG_FILE_CORE as the default LOG_FILE_PATH for main.py, or make it more specific
LOG_FILE_PATH = _config_instance.get("LOG_FILE_PATH", LOG_FILE_CORE) # Defaulting to core.log
MAX_LOG_FILE_SIZE = int(_config_instance.get("MAX_LOG_FILE_SIZE", 1024 * 1024 * 5))  # 5 MB
LOG_BACKUP_COUNT = int(_config_instance.get("LOG_BACKUP_COUNT", 3))

# --- GUI Configuration ---
GUI_HOST = _config_instance.get("GUI_HOST", "127.0.0.1")
GUI_PORT = int(_config_instance.get("GUI_PORT", 8001))
AUTOMOY_GUI_TITLE_PREFIX = _config_instance.get("AUTOMOY_GUI_TITLE_PREFIX", "Automoy GUI @")

# --- OmniParser Configuration ---
OMNIPARSER_HOST = _config_instance.get("OMNIPARSER_HOST", "127.0.0.1")
OMNIPARSER_PORT = int(_config_instance.get("OMNIPARSER_PORT", 8111)) # Default, adjust if needed
OMNIPARSER_BASE_URL = f"http://{OMNIPARSER_HOST}:{OMNIPARSER_PORT}"

# --- Main Loop Configuration ---
MAIN_LOOP_SLEEP_INTERVAL = float(_config_instance.get("MAIN_LOOP_SLEEP_INTERVAL", 0.5)) # seconds
MAIN_LOOP_ERROR_SLEEP_INTERVAL = float(_config_instance.get("MAIN_LOOP_ERROR_SLEEP_INTERVAL", 5.0)) # seconds

# --- LM Configuration ---
# These will use the methods from the Config class to determine source and model
API_SOURCE, API_KEY_OR_URL = _config_instance.get_api_source()
LLM_MODEL_TEMPERATURE = _config_instance.get_temperature()
LLM_MODEL = _config_instance.get_model()
MAX_RETRIES_PER_STEP = _config_instance.get_max_retries_per_step()
MAX_CONSECUTIVE_ERRORS = _config_instance.get_max_consecutive_errors()

# --- Screenshot Configuration ---
SCREENSHOT_DIR = _config_instance.get("SCREENSHOT_DIR", os.path.join(BASE_DIR, "debug", "screenshots"))
CURRENT_SCREENSHOT_FILENAME = _config_instance.get("CURRENT_SCREENSHOT_FILENAME", "automoy_current_capture.png")
CURRENT_SCREENSHOT_PATH = os.path.join(SCREENSHOT_DIR, CURRENT_SCREENSHOT_FILENAME)

# --- Other paths ---
PROCESSED_SCREENSHOT_PATH_GUI = _config_instance.get("PROCESSED_SCREENSHOT_PATH_GUI", os.path.join(BASE_DIR, "gui", "static", "processed_screenshot.png"))

# Ensure necessary directories exist
Path(LOG_DIR, "core").mkdir(parents=True, exist_ok=True)
Path(LOG_DIR, "gui").mkdir(parents=True, exist_ok=True)
Path(LOG_DIR, "omniparser").mkdir(parents=True, exist_ok=True)
Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
Path(os.path.join(BASE_DIR, "gui", "static")).mkdir(parents=True, exist_ok=True) # For processed_screenshot.png

# To allow direct import of the instance if needed elsewhere, though module-level vars are preferred.
# config_provider = _config_instance
