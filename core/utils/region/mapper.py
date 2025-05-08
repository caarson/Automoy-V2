from PIL import Image

def map_elements_to_coords(parsed_result, image_path):
    """Convert normalized bbox to pixel coordinates and map by lowercase content."""
    # Ensure the parser's output is in the expected 'coords' key
    if not parsed_result or "coords" not in parsed_result:
        return {}

    image = Image.open(image_path)
    width, height = image.size
    coords_map = {}

    # Iterate over each detected element in parsed_result["coords"]
    for item in parsed_result["coords"]:
        x1, y1, x2, y2 = item.get("bbox", (0, 0, 0, 0))
        abs_x1 = int(x1 * width)
        abs_y1 = int(y1 * height)
        abs_x2 = int(x2 * width)
        abs_y2 = int(y2 * height)
        center_x = (abs_x1 + abs_x2) // 2
        center_y = (abs_y1 + abs_y2) // 2

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

    # Return the full mapping after processing all items
    return coords_map
