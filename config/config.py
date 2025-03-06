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

        with open(self.config_file, "r") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):  # Ignore empty lines and comments
                    key, value = line.split(":", 1)
                    config_data[key.strip()] = self._convert_value(value.strip())

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

# Example Usage:
if __name__ == "__main__":
    config = Config()
    print("OPENAI_API_KEY:", config.get("OPENAI_API_KEY"))
    print("LMSTUDIO_API_URL:", config.get("LMSTUDIO_API_URL"))
    print("MODEL:", config.get("MODEL"))
    print("DEFINE_REGION:", config.get("DEFINE_REGION"))
    print("DEBUG:", config.get("DEBUG"))
