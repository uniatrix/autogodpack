# Building AutoGodPack Executable

## Prerequisites

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Building the Executable

### Option 1: Using the build script

```bash
python build_exe.py
```

### Option 2: Using PyInstaller directly

```bash
pyinstaller AutoGodPack.spec
```

The executable will be created in the `dist/` directory as `AutoGodPack.exe`.

## Running the Executable

1. Copy `AutoGodPack.exe` to your desired location
2. Ensure `config.yaml` is in the same directory (or edit the spec file to include it)
3. Ensure `autogodpack/templates/` directory is accessible (or edit the spec file to include it)
4. Run `AutoGodPack.exe`

## Notes

- The executable is built with `--windowed` flag, so no console window will appear
- All templates and configuration files should be included in the build
- The executable includes all dependencies, so it's a standalone file
- ADB must be installed on the system and accessible in PATH for device management to work

## Troubleshooting

### Build fails with "PyInstaller not found"
```bash
pip install pyinstaller
```

### Executable doesn't find templates
- Ensure templates are included in the spec file's `datas` section
- Check that paths are correct relative to the executable location

### ADB not found when running executable
- Ensure ADB is installed and in system PATH
- The executable uses system ADB, it's not bundled






