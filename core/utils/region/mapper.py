from PIL import Image

def map_elements_to_coords(parsed_result, image_path):
    """Convert normalized bbox to pixel coordinates and map by lowercase content."""
    if not parsed_result or "parsed_content_list" not in parsed_result:
        return {}

    image = Image.open(image_path)
    width, height = image.size
    coords_map = {}

    for item in parsed_result["parsed_content_list"]:
        x1, y1, x2, y2 = item["bbox"]
        abs_x1 = int(x1 * width)
        abs_y1 = int(y1 * height)
        abs_x2 = int(x2 * width)
        abs_y2 = int(y2 * height)
        center_x = (abs_x1 + abs_x2) // 2
        center_y = (abs_y1 + abs_y2) // 2

        content_key = item["content"].strip().lower()
        coords_map[content_key] = {
            "type": item["type"],
            "content": item["content"],
            "center": (center_x, center_y),
            "top_left": (abs_x1, abs_y1),
            "bottom_right": (abs_x2, abs_y2),
            "interactivity": item.get("interactivity", False),
            "source": item.get("source", None)
        }

    return coords_map
