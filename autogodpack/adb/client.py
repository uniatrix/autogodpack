"""ADB client wrapper for device communication."""

import subprocess
import logging
from typing import Optional, List

from ..utils.exceptions import ADBError
from ..config.settings import ADBConfig

logger = logging.getLogger(__name__)


class ADBClient:
    """ADB client for executing commands on Android devices."""

    def __init__(self, config: ADBConfig):
        """
        Initialize ADB client.

        Args:
            config: ADB configuration settings.
        """
        self.config = config
        self.serial = config.serial
        self.timeout = config.command_timeout

    def execute(self, args: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Execute an ADB command.

        Args:
            args: ADB command arguments (without 'adb' prefix).
            capture_output: Whether to capture stdout/stderr.

        Returns:
            CompletedProcess object with command result.

        Raises:
            ADBError: If command execution fails.
        """
        cmd = ["adb", "-s", self.serial] + args

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
            )
            return result
        except subprocess.TimeoutExpired as e:
            raise ADBError(f"ADB command timed out after {self.timeout}s: {' '.join(cmd)}") from e
        except Exception as e:
            raise ADBError(f"Failed to execute ADB command: {' '.join(cmd)}") from e

    def test_connection(self) -> bool:
        """
        Test ADB connection to device.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            result = self.execute(["shell", "echo", "test"], capture_output=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"ADB connection test failed: {e}")
            return False






