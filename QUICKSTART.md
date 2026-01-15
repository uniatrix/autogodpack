# Quick Start Guide - AutoGodPack GUI

## Running the GUI Application

### Option 1: Run from Source

1. Activate your virtual environment:
```bash
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac
```

2. Run the GUI:
```bash
python run_gui.py
```

Or:
```bash
python -m autogodpack.gui
```

### Option 2: Run Executable

1. Build the executable:
```bash
python build_exe.py
```

2. Run `dist/AutoGodPack.exe`

## Using the GUI

### 1. Connect to a Device

1. Enter the device serial or IP:port in the "Connect to:" field (e.g., `127.0.0.1:5585`)
2. Click "Connect"
3. The device will appear in the "Connected Devices" list
4. The current device will be shown at the top

### 2. View Connected Devices

- Click "Refresh" to update the device list
- Devices are automatically refreshed every 2 seconds
- Connected devices show their serial and connection state

### 3. Disconnect from a Device

1. Select a device from the "Connected Devices" list
2. Click "Disconnect Selected"

### 4. Start the Bot

1. Ensure a device is connected (shown in "Current Device")
2. Click "Start Bot"
3. The bot will begin running battle cycles
4. Logs will appear in the log window

### 5. Stop the Bot

1. Click "Stop Bot"
2. The bot will stop after completing the current cycle

## Features

- **Device Management**: Easy connection/disconnection to multiple ADB devices
- **Real-time Status**: See current device and bot status
- **Live Logging**: View bot activity in real-time
- **Simple Controls**: Start/stop bot with one click

## Troubleshooting

### "Cannot connect to device"
- Ensure ADB is installed and in your PATH
- Verify the device is accessible: `adb devices`
- Check that the IP:port is correct for network connections

### "No device selected"
- Connect to a device first using the "Connect" button
- Ensure the device appears in the connected devices list

### GUI doesn't start
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that Python 3.8+ is being used
- Verify tkinter is available (usually included with Python)

### Executable doesn't work
- Ensure `config.yaml` is in the same directory as the executable
- Check that templates directory is accessible
- Verify ADB is installed on the system






