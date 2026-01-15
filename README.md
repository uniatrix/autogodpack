# AutoGodPack

A professional automation bot for Pokemon card game battles using ADB (Android Debug Bridge) and computer vision.

## Features

- **Automated Battle Cycles**: Automatically completes battle cycles from selection to completion
- **Expansion Management**: Intelligently tracks and selects expansions
- **Screen Detection**: Advanced template matching for reliable screen state detection
- **State Persistence**: Remembers completed expansions across sessions
- **Error Recovery**: Robust error handling and recovery mechanisms
- **Configurable**: Easy-to-use YAML configuration file

## Requirements

- Python 3.8 or higher
- ADB (Android Debug Bridge) installed and accessible in PATH
- Android device connected via ADB (USB or network)
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone or download this repository

2. Create a virtual environment (recommended):
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

## Building Executable

To build a standalone executable:

```bash
python build_exe.py
```

Or use PyInstaller directly:

```bash
pyinstaller AutoGodPack.spec
```

The executable will be in `dist/AutoGodPack.exe`. See `README_BUILD.md` for details.

## Configuration

1. Edit `config.yaml` to configure the bot:

```yaml
adb:
  serial: "127.0.0.1:5585"  # Your ADB device serial or IP:port

automation:
  cycle_delay: 1.0          # Delay between cycles
  fast_mode: false          # Enable fast mode

# ... see config.yaml for all options
```

2. Ensure your template images are in `autogodpack/templates/battle/` directory

## Usage

### GUI Application (Recommended)

Run the GUI application:

```bash
python -m autogodpack.gui
```

Or use the executable (after building):

```bash
AutoGodPack.exe
```

The GUI provides:
- **Device Management**: Connect/disconnect to ADB devices
- **Device List**: View all connected devices
- **Bot Control**: Start/stop the bot with a button
- **Live Logs**: Real-time logging output

### Command Line

Run the bot using Python:

```bash
python -m autogodpack
```

Or use the entry point (after installation):

```bash
autogodpack
```

The bot will:
1. Detect the current screen state
2. Navigate through battle selection
3. Handle expansion selection if needed
4. Complete battles automatically
5. Process victory/defeat screens
6. Loop continuously until stopped

### Stopping the Bot

Press `Ctrl+C` to gracefully stop the bot.

### Utility Scripts

#### Capture Screenshot

```bash
python scripts/capture_screen.py
```

#### Reset Expansions

Create a file named `reset_expansions.flag` in the project root, or run:

```bash
python scripts/reset_expansions.py
```

## Project Structure

```
autogodpack/
├── autogodpack/          # Main package
│   ├── core/             # Bot orchestrator and state machine
│   ├── adb/              # ADB operations
│   ├── image/            # Image processing and template matching
│   ├── screens/          # Screen handlers
│   ├── state/            # State management
│   ├── config/           # Configuration management
│   ├── utils/            # Utilities
│   └── templates/        # Template images
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── docs/                 # Documentation
├── logs/                 # Log files
├── config.yaml           # Configuration file
└── requirements.txt      # Python dependencies
```

## Template Images

Template images are stored in `autogodpack/templates/battle/` organized by screen:

- `screen_1_battle_selection/` - Battle selection screen templates
- `screen_2_battle_setup/` - Battle setup screen templates
- `battle_in_progress/` - Battle in progress templates
- `screen_3_victory/` - Victory screen templates
- `screen_4_5_6/` - Intermediate screens
- `screen_7/` - Screen 7 templates
- `screen_8/` - Popup templates
- `screen_defeat/` - Defeat screen templates
- `screen_defeat_popup/` - Defeat popup templates
- `select_expansion/` - Expansion selection templates

## Logging

Logs are written to `logs/battle_bot.log` by default. You can configure logging in `config.yaml`.

## Troubleshooting

### ADB Connection Issues

- Ensure ADB is installed and in your PATH
- Verify device connection: `adb devices`
- Check ADB serial in `config.yaml` matches your device

### Template Matching Issues

- Ensure template images are in the correct directories
- Check that template images match current game UI
- Adjust matching threshold in `config.yaml` if needed

### Screen Detection Issues

- Verify all required template images are present
- Check log file for detailed error messages
- Ensure game UI hasn't changed significantly

## Contributing

Contributions are welcome! Please ensure:

- Code follows Python best practices
- Type hints are included
- Documentation is updated
- Tests pass (if applicable)

## License

MIT License - see LICENSE file for details

## Disclaimer

This tool is for educational purposes. Use responsibly and in accordance with the game's terms of service.

