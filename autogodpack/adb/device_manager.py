"""ADB device management."""

import subprocess
import logging
from typing import List, Dict, Optional

from ..utils.exceptions import ADBError

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages ADB device connections."""

    @staticmethod
    def list_devices() -> List[Dict[str, str]]:
        """
        List all connected ADB devices.

        Returns:
            List of device dictionaries with 'serial' and 'state' keys.
        """
        try:
            result = subprocess.run(
                ["adb", "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"Failed to list devices: {result.stderr}")
                return []

            devices = []
            lines = result.stdout.strip().split("\n")[1:]  # Skip header

            for line in lines:
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        devices.append({"serial": parts[0], "state": parts[1]})

            return devices

        except subprocess.TimeoutExpired:
            logger.error("Timeout listing devices")
            return []
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []

    @staticmethod
    def connect_device(serial: str) -> bool:
        """
        Connect to an ADB device.

        Args:
            serial: Device serial or IP:port.

        Returns:
            True if connection successful.
        """
        try:
            result = subprocess.run(
                ["adb", "connect", serial],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                output = result.stdout.strip().lower()
                if "connected" in output or "already connected" in output:
                    logger.info(f"Successfully connected to {serial}")
                    return True

            logger.error(f"Failed to connect to {serial}: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout connecting to {serial}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to {serial}: {e}")
            return False

    @staticmethod
    def disconnect_device(serial: str) -> bool:
        """
        Disconnect from an ADB device.

        Args:
            serial: Device serial or IP:port.

        Returns:
            True if disconnection successful.
        """
        try:
            result = subprocess.run(
                ["adb", "disconnect", serial],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                logger.info(f"Successfully disconnected from {serial}")
                return True

            logger.error(f"Failed to disconnect from {serial}: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout disconnecting from {serial}")
            return False
        except Exception as e:
            logger.error(f"Error disconnecting from {serial}: {e}")
            return False

    @staticmethod
    def test_connection(serial: str, retries: int = 2) -> bool:
        """
        Test connection to a device.

        Args:
            serial: Device serial or IP:port.
            retries: Number of retry attempts for network devices.

        Returns:
            True if device is reachable.
        """
        import time

        # Network devices may need longer timeout and retries
        is_network_device = ":" in serial and not serial.startswith("emulator-")
        timeout = 5 if is_network_device else 2
        max_attempts = retries if is_network_device else 1

        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ["adb", "-s", serial, "shell", "echo", "test"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    return True

                if attempt < max_attempts - 1:
                    logger.debug(f"Connection test failed for {serial}, retrying ({attempt + 1}/{max_attempts})...")
                    time.sleep(0.5)

            except subprocess.TimeoutExpired:
                if attempt < max_attempts - 1:
                    logger.debug(f"Connection test timed out for {serial}, retrying ({attempt + 1}/{max_attempts})...")
                    time.sleep(0.5)
            except Exception:
                pass

        return False

