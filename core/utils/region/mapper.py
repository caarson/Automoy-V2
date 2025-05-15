import sys
import json
import argparse
from pathlib import Path
from PIL import Image

# === ✅ FIXED sys.path patch ===
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[3]  # go from core/utils/region/mapper.py → project root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ✅ Now import OmniParserInterface AFTER sys.path is fixed
from core.utils.omniparser.omniparser_interface import OmniParserInterface


def map_elements_to_coords(parsed_result, image_path):
    """Convert normalized bbox to pixel coordinates and map by lowercase content."""
    from pathlib import Path
    from PIL import Image

    coords_raw = parsed_result.get("parsed_content_list", [])
    if not coords_raw:
        print("❌ No parsed_content_list found.")
        return {}

    if not Path(image_path).exists():
        print(f"❌ Image file not found: {image_path}")
        return {}

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    print(f"📐 Image dimensions: {width}x{height}")

    coords_map = {}

    for item in coords_raw:
        x1, y1, x2, y2 = item.get("bbox", (0, 0, 0, 0))
        if (x1, y1, x2, y2) == (0, 0, 0, 0):
            continue  # Skip invalid boxes

        abs_x1 = int(x1 * width)
        abs_y1 = int(y1 * height)
        abs_x2 = int(x2 * width)
        abs_y2 = int(y2 * height)
        center_x = (abs_x1 + abs_x2) // 2
        center_y = (abs_y1 + abs_y2) // 2

        print(f"📦 {item['content']} → px: ({abs_x1}, {abs_y1}) to ({abs_x2}, {abs_y2})")

        content_key = item.get("content", "").strip().lower()
        coords_map[content_key] = {
            "type": item.get("type"),
            "content": item.get("content"),
            "center": (center_x, center_y),
            "top_left": (abs_x1, abs_y1),
            "bottom_right": (abs_x2, abs_y2),
            "interactivity": item.get("interactivity", False),
            "source": item.get("source")
        }

    return coords_map


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Map OmniParser results to pixel coordinates.")
    parser.add_argument("image", nargs="?", help="Path to screenshot image")
    parser.add_argument("--json", help="Path to parsed OmniParser JSON result")
    args = parser.parse_args()

    if not args.image:
        sample = PROJECT_ROOT / "core" / "utils" / "omniparser" / "sample_screenshot.png"
        if not sample.exists():
            print(f"❌ Sample screenshot missing at {sample}")
            sys.exit(1)
        print(f"No image given – using bundled sample: {sample}")
        args.image = str(sample)

    if not args.json:
        default_json = Path(args.image).with_name("parsed_result.json")
        if not default_json.exists():
            print(f"⚠️ No JSON found at {default_json}, generating with OmniParser...")
            op = OmniParserInterface()
            if not op.launch_server():
                print("❌ Failed to launch OmniParser server.")
                sys.exit(1)
            parsed_result = op.parse_screenshot(args.image)
            op.stop_server()

            with open(default_json, "w", encoding="utf-8") as f:
                json.dump(parsed_result, f, indent=2)
            print(f"✅ Saved parsed result to: {default_json}")
        args.json = str(default_json)

    with open(args.json, "r", encoding="utf-8") as f:
        parsed_result = json.load(f)

    coords_map = map_elements_to_coords(parsed_result, args.image)

    print("🗺️  Mapped Elements:")
    print(json.dumps(coords_map, indent=2))
