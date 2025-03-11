import requests

class OmniParserInterface:
    def __init__(self, server_url="http://localhost:8111"):
        """Initialize the OmniParser client interface."""
        self.server_url = server_url

    def parse_screenshot(self, image_path):
        """
        Sends an image to the OmniParser server for analysis.

        :param image_path: Path to the image file
        :return: Parsed response from the server
        """
        url = f"{self.server_url}/parse"
        files = {"file": open(image_path, "rb")}
        
        try:
            response = requests.post(url, files=files)
            response.raise_for_status()  # Raise error for bad responses
            return response.json()  # Return parsed JSON response
        except requests.exceptions.RequestException as e:
            print(f"❌ OmniParser request failed: {e}")
            return None

# Example Usage
if __name__ == "__main__":
    omniparser = OmniParserInterface()
    result = omniparser.parse_screenshot("sample_screenshot.png")
    print("🔍 Parsed Data:", result)
