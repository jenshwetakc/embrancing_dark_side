import json
def generate_repair_suggestion_file(data):
    suggestions = {}

    # Check for edge inconsistencies
    if "edge_inconsistency" in data and isinstance(data["edge_inconsistency"], dict):
        pages = data["edge_inconsistency"].get("pages", [])

        if isinstance(pages, list) and len(pages) > 0 and any(pages):
            suggestions["edge_inconsistency"] = {
            "message": "ChromaEye detects edges inconsistency",
             "suggestion": [
            "Design surface overlays to reflect different elevation levels in dark mode.",
            "Elevation overlay transparencies should range from 0% (lowest level) to 16% (highest level).",
            "Avoid elevation overlays on components that use primary or secondary colors for their surface container.",
            "Do not use light glows instead of dark shadows to express elevation, as they do not accurately represent elevation like cast shadows.",
            "Use SVG, WEBP, or PNG formats instead of JPG to support transparency.",
            "For more details: https://m2.material.io/design/color/dark-theme.html",
            "For more details: https://developer.apple.com/design/human-interface-guidelines/dark-mode"
        ]
}


    # Check for object based inconsistencies
    if "icon_inconsistency" in data and isinstance(data["icon_inconsistency"], dict):
        pages = data["icon_inconsistency"].get("pages", [])

        if isinstance(pages, list) and len(pages) > 0 and any(pages):
            suggestions["icon_inconsistency"] = {
            "message": "ChromaEye detects icon inconsistency",
            "suggestion": [
            "Icons must meet a minimum contrast ratio of 3:1.",
            "Desaturated colors improve legibility and reduce visual vibration.",
            "For dark mode, use lighter tones (200-50) instead of highly saturated tones (900-500) to ensure contrast and usability.",
            "Consistent use of desaturated colors enhances UI coherence across light and dark themes.",
            "For more details: https://m2.material.io/design/color/dark-theme.html",
            "For more details: https://developer.apple.com/design/human-interface-guidelines/dark-mode"
            ]
        }

    if "partial_conversion" in data and isinstance(data["partial_conversion"], dict):
        pages = data["partial_conversion"].get("pages", [])  # Get pages, default to an empty list

        if isinstance(pages, list) and len(pages) > 0:  # Check if pages is a non-empty list
            suggestions["partial_conversion"] = {
                "suggestion": [
                    "Use #121212 as the recommended dark theme surface color.",
                    "Surfaces must be dark enough to support white text readability.",
                    "To create branded dark surfaces, overlay the primary brand color at low opacity over #121212.",
                    "Ensure the background color maintains a contrast ratio of at least 4.5:1 (AA standard) on the highest elevated surfaces.",
                    "For more details: https://m2.material.io/design/color/dark-theme.html",
                    "For more details: https://developer.apple.com/design/human-interface-guidelines/dark-mode"
                ]
            }

    # Check for invisible text inconsistencies
    if "text_inconsistency" in data and isinstance(data["text_inconsistency"], dict) and "invisible_text" in data[
        "text_inconsistency"]:
        pages = data["text_inconsistency"]["invisible_text"].get("pages", [])

        if isinstance(pages, list) and len(pages) > 0 and any(pages):
            # print("icon", data["text_inconsistency"])
            suggestions["invisible_text"] = {
                "message": "ChromaEye detects invisible text inconsistency",
                    "suggestion": [
                        "Text must maintain a minimum contrast ratio of 4.5:1 for readability.",
                        "The contrast ratio should be 3:1 for bold and large text, WCAG defines large text as text that is at least 18pt in size, or 14pt if bold.",
                        "Desaturated colors enhance legibility and reduce visual vibration.",
                        "Using lighter tones (200-50) in dark mode instead of saturated tones (900-500) improves usability.",
                        "For more details: https://m2.material.io/design/color/dark-theme.html",
                        "For more details: https://developer.apple.com/design/human-interface-guidelines/dark-mode",
                        "For more details:https://webaim.org/articles/contrast/"
                    ]


            }

    # Check for missing text inconsistencies
    if "text_inconsistency" in data and isinstance(data["text_inconsistency"], dict) and "missing_text" in data[
        "text_inconsistency"]:
        pages = data["text_inconsistency"]["missing_text"].get("pages", [])

        if isinstance(pages, list) and len(pages) > 0 and any(pages):
            # print("icon", data["missing_text"])
            suggestions["missing_text"] = {
                "message": "ChromaEye detects missing text inconsistency",
                    "suggestion": [
                        "Text must meet a minimum contrast ratio of 4.5:1.",
                        "Ensure proper conversion to support dark mode visibility.",
                        "Avoid text blending with the background, which may create the illusion of missing text.",
                        "For more details: https://m2.material.io/design/color/dark-theme.html",
                        "For more details: https://developer.apple.com/design/human-interface-guidelines/dark-mode"
                    ]


            }
    return suggestions


def inconsistency_repair_suggestion(input_json_path, output_json_path):
    try:
        # Load the JSON file
        with open(input_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Get the repair suggestions
        suggestions = generate_repair_suggestion_file(data)

        if suggestions:
            # Save repair suggestions to a file
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(suggestions, f, indent=4)

            print(f"Repair suggestion file generated: {output_json_path}")
        else:
            print("No inconsistencies found. No repair suggestion file generated.")
    except Exception as e:
        print(f"Error processing the file: {e}")
