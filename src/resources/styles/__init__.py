"""Style configuration loader for Ableton Hub."""

import json
from pathlib import Path
from typing import Any, cast


def get_style_config() -> dict[str, Any]:
    """Load and return the style configuration.

    Returns:
        Dictionary containing all style configuration.
    """
    config_path = Path(__file__).parent / "style_config.json"
    with open(config_path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def get_color(category: str, name: str) -> str:
    """Get a color value from the style config.

    Args:
        category: Color category (e.g., 'base', 'accent', 'text')
        name: Color name within the category

    Returns:
        Hex color string, or empty string if not found.
    """
    config = get_style_config()
    colors = cast(dict[str, Any], config.get("colors", {}))
    category_colors = cast(dict[str, str], colors.get(category, {}))
    return cast(str, category_colors.get(name, ""))


def get_font_size(size_name: str) -> int:
    """Get a font size value.

    Args:
        size_name: Font size name (e.g., 'small', 'normal', 'large')

    Returns:
        Font size in pixels.
    """
    config = get_style_config()
    fonts = cast(dict[str, Any], config.get("fonts", {}))
    sizes = cast(dict[str, int], fonts.get("sizes", {}))
    return cast(int, sizes.get(size_name, 12))


def get_spacing(spacing_name: str) -> int:
    """Get a spacing value.

    Args:
        spacing_name: Spacing name (e.g., 'tight', 'normal', 'comfortable')

    Returns:
        Spacing value in pixels.
    """
    config = get_style_config()
    spacing = cast(dict[str, int], config.get("spacing", {}))
    return cast(int, spacing.get(spacing_name, 6))


def get_component_style(component: str, property_path: str | None = None) -> Any:
    """Get component-specific style values.

    Args:
        component: Component name (e.g., 'search_bar', 'project_card')
        property_path: Optional dot-separated path to nested property

    Returns:
        Style value or dictionary.
    """
    config = get_style_config()
    components = config.get("components", {})
    component_style = components.get(component, {})

    if property_path:
        parts = property_path.split(".")
        value = component_style
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, {})
            else:
                return None
        return value

    return component_style
