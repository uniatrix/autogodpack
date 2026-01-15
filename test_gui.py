"""Test script to verify GUI functionality."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing GUI components...")

# Test imports
try:
    print("1. Testing imports...")
    from autogodpack.gui.app import AutoGodPackGUI
    from autogodpack.adb.device_manager import DeviceManager
    from autogodpack.config.loader import load_config
    print("   ✓ All imports successful")
except Exception as e:
    print(f"   ✗ Import error: {e}")
    sys.exit(1)

# Test configuration
try:
    print("2. Testing configuration...")
    config_path = project_root / "config.yaml"
    if config_path.exists():
        settings = load_config(config_path)
        print(f"   ✓ Config loaded: ADB serial = {settings.adb.serial}")
    else:
        print(f"   ⚠ Config file not found at {config_path}")
except Exception as e:
    print(f"   ✗ Config error: {e}")

# Test ADB
try:
    print("3. Testing ADB...")
    devices = DeviceManager.list_devices()
    print(f"   ✓ ADB working: {len(devices)} device(s) found")
    for device in devices:
        print(f"      - {device['serial']} ({device['state']})")
except Exception as e:
    print(f"   ✗ ADB error: {e}")

# Test templates
try:
    print("4. Testing templates...")
    template_dir = project_root / "autogodpack" / "templates" / "battle"
    if template_dir.exists():
        template_files = list(template_dir.rglob("*.png"))
        print(f"   ✓ Templates found: {len(template_files)} files")
    else:
        print(f"   ✗ Template directory not found: {template_dir}")
except Exception as e:
    print(f"   ✗ Template error: {e}")

print("\nAll tests completed. If there are errors above, fix them before running GUI.")






