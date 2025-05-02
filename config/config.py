import os

class Config:
    def __init__(self):
        """Load configuration from config.txt inside the config directory."""
        self.config_file = os.path.join(os.path.dirname(__file__), "config.txt")
        self.config_data = self._load_config()

    def _load_config(self):
        """Reads the config.txt file and returns a dictionary of key-value pairs."""
        config_data = {}
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file '{self.config_file}' not found!")

        with open(self.config_file, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.split("#", 1)[0].strip()  # Strip inline comments
                        config_data[key] = self._convert_value(value)

        return config_data

    def _convert_value(self, value):
        """Converts config values to appropriate types (bool, int, float, str)."""
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value  # Return as string if conversion fails

    def get(self, key, default=None):
        """Retrieve a configuration value with an optional default."""
        return self.config_data.get(key, default)

    def get_api_source(self):
        """
        Determines which LLM API to use based on 'OPENAI' and 'LMSTUDIO' flags.
        Returns a tuple: (source, key_or_url)
        """
        if self.get("OPENAI", False) and self.get("OPENAI_API_KEY"):
            return "openai", self.get("OPENAI_API_KEY")
        elif self.get("LMSTUDIO", False) and self.get("LMSTUDIO_API_URL"):
            return "lmstudio", self.get("LMSTUDIO_API_URL")
        else:
            raise ValueError(
                "No valid API configuration found: "
                "ensure OPENAI or LMSTUDIO is set to True and has a valid key or URL."
            )

    def get_temperature(self):
        """Returns temperature for the active LLM provider."""
        source, _ = self.get_api_source()
        return self.get(
            "OPENAI_TEMPERATURE" if source == "openai" else "LMSTUDIO_TEMPERATURE",
            0.7,
        )

    def get_model(self):
        """Returns the model name configured for the active LLM provider."""
        source, _ = self.get_api_source()
        if source == "openai":
            return self.get("OPENAI_MODEL", "gpt-4o")
        elif source == "lmstudio":
            return self.get("LMSTUDIO_MODEL", "deepseek-r1-distill-qwen-7b")


# Example Usage
if __name__ == "__main__":
    config = Config()

    # Print the active LLM provider and its credentials
    provider, key_or_url = config.get_api_source()
    print(f"Using LLM Provider: {provider}")
    print(f"Credential/URL: {key_or_url}")

    # Print model and temperature settings
    print(f"Model: {config.get_model()}")
    print(f"Temperature: {config.get_temperature()}")

    # Print other misc. configuration values
    print(f"DEFINE_REGION: {config.get('DEFINE_REGION')}")
    print(f"DEBUG: {config.get('DEBUG')}")
