"""Build executable script."""

import subprocess
import sys
from pathlib import Path

def build_exe():
    """Build executable using PyInstaller."""
    project_root = Path(__file__).parent
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=AutoGodPack",
        "--onefile",
        "--windowed",  # No console window
        "--icon=NONE",  # Add icon path if you have one
        "--add-data=config.yaml;.",
        "--add-data=autogodpack/templates;autogodpack/templates",
        "--hidden-import=autogodpack",
        "--hidden-import=autogodpack.gui",
        "--hidden-import=autogodpack.core",
        "--hidden-import=autogodpack.adb",
        "--hidden-import=autogodpack.image",
        "--hidden-import=autogodpack.state",
        "--hidden-import=autogodpack.config",
        "--hidden-import=autogodpack.utils",
        "--hidden-import=yaml",
        "--hidden-import=cv2",
        "--hidden-import=numpy",
        "--hidden-import=PIL",
        "autogodpack/gui/__main__.py"
    ]
    
    print("Building executable...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=project_root, check=True)
        print("\n✓ Build successful!")
        print(f"Executable location: {project_root / 'dist' / 'AutoGodPack.exe'}")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("\n✗ PyInstaller not found. Please install it:")
        print("  pip install pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()






