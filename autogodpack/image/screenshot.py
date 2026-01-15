"""Screenshot capture functionality."""

import io
import logging
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from ..adb.client import ADBClient
from ..utils.exceptions import ScreenshotError

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """Handles screenshot capture from Android device."""

    def __init__(self, client: ADBClient):
        """
        Initialize screenshot capture.

        Args:
            client: ADB client instance.
        """
        self.client = client

    def capture_bgr(self) -> Optional[np.ndarray]:
        """
        Capture screenshot and return as BGR numpy array.

        Returns:
            BGR image array, or None if capture failed.
        """
        try:
            result = self.client.execute(["exec-out", "screencap", "-p"], capture_output=True)

            if result.returncode != 0:
                stderr = (
                    result.stderr.decode("utf-8", errors="ignore")
                    if result.stderr
                    else "Unknown error"
                )
                logger.error(
                    f"Failed to capture screenshot (ADB_SERIAL={self.client.serial}): {stderr}"
                )
                return None

            if not result.stdout:
                logger.error(f"Empty screenshot received (ADB_SERIAL={self.client.serial})")
                return None

            # Convert bytes to image
            img = Image.open(io.BytesIO(result.stdout))
            # Convert RGB to BGR for OpenCV
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        except Exception as e:
            logger.error(f"Error processing screenshot: {e}")
            raise ScreenshotError(f"Failed to process screenshot: {e}") from e

    def capture_rgb(self) -> Optional[np.ndarray]:
        """
        Capture screenshot and return as RGB numpy array.

        Returns:
            RGB image array, or None if capture failed.
        """
        try:
            result = self.client.execute(["exec-out", "screencap", "-p"], capture_output=True)

            if result.returncode != 0:
                stderr = (
                    result.stderr.decode("utf-8", errors="ignore")
                    if result.stderr
                    else "Unknown error"
                )
                logger.error(
                    f"Failed to capture screenshot (ADB_SERIAL={self.client.serial}): {stderr}"
                )
                return None

            if not result.stdout:
                logger.error(f"Empty screenshot received (ADB_SERIAL={self.client.serial})")
                return None

            # Convert bytes to image
            img = Image.open(io.BytesIO(result.stdout))
            return np.array(img)

        except Exception as e:
            logger.error(f"Error processing screenshot: {e}")
            raise ScreenshotError(f"Failed to process screenshot: {e}") from e

    def save_screenshot(self, output_path: str) -> bool:
        """
        Capture screenshot and save to file.

        Args:
            output_path: Path to save screenshot.

        Returns:
            True if successful, False otherwise.
        """
        img = self.capture_rgb()
        if img is None:
            return False

        try:
            pil_img = Image.fromarray(img)
            pil_img.save(output_path)
            logger.info(f"Screenshot saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            return False






