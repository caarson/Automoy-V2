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
