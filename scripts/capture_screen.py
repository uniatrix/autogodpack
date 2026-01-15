"""Screenshot capture utility script."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from autogodpack.config.loader import load_config
from autogodpack.adb.client import ADBClient
from autogodpack.image.screenshot import ScreenshotCapture


def main():
    """Capture and save screenshot."""
    project_root = Path(__file__).parent.parent

    # Load configuration
    try:
        config_path = project_root / "config.yaml"
        settings = load_config(config_path)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    # Initialize components
    client = ADBClient(settings.adb)
    screenshot = ScreenshotCapture(client)

    # Capture and save
    output_path = project_root / "screen.png"
    if screenshot.save_screenshot(str(output_path)):
        print(f"Screenshot saved to {output_path}")
    else:
        print("Failed to capture screenshot")
        sys.exit(1)


if __name__ == "__main__":
    main()






