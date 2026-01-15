"""ADB command implementations for device interaction."""

import time
import logging
from typing import Optional, Tuple

from .client import ADBClient
from ..utils.exceptions import ADBError, ScreenshotError

logger = logging.getLogger(__name__)


class ADBCommands:
    """High-level ADB commands for device interaction."""

    def __init__(self, client: ADBClient):
        """
        Initialize ADB commands.

        Args:
            client: ADB client instance.
        """
        self.client = client

    def tap(self, x: float, y: float, delay: float = 0.3) -> bool:
        """
        Execute a tap at the specified coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            delay: Delay after tap in seconds.

        Returns:
            True if successful, False otherwise.
        """
        x_int = int(x)
        y_int = int(y)
        # Removed verbose logging - too noisy

        try:
            result = self.client.execute(
                ["shell", "input", "tap", str(x_int), str(y_int)],
                capture_output=True,
            )

            if result.returncode == 0:
                # Removed verbose logging - too noisy
                time.sleep(delay)
                return True
            else:
                # Only log critical errors
                return False
        except ADBError as e:
            # Only log critical errors
            return False

    def swipe(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int = 500,
        delay: float = 0.3,
    ) -> bool:
        """
        Execute a swipe gesture.

        Args:
            x1: Start X coordinate.
            y1: Start Y coordinate.
            x2: End X coordinate.
            y2: End Y coordinate.
            duration_ms: Swipe duration in milliseconds.
            delay: Delay after swipe in seconds.

        Returns:
            True if successful, False otherwise.
        """
        x1_int = int(x1)
        y1_int = int(y1)
        x2_int = int(x2)
        y2_int = int(y2)

        # Removed verbose logging - too noisy

        try:
            result = self.client.execute(
                [
                    "shell",
                    "input",
                    "swipe",
                    str(x1_int),
                    str(y1_int),
                    str(x2_int),
                    str(y2_int),
                    str(duration_ms),
                ],
                capture_output=True,
            )

            if result.returncode == 0:
                # Removed verbose logging - too noisy
                time.sleep(delay)
                return True
            else:
                # Only log critical errors
                return False
        except ADBError as e:
            # Only log critical errors
            return False

    def scroll_down(
        self, slow_mode: bool = False, screen_height: int = 1920, screen_width: int = 1080
    ) -> bool:
        """
        Scroll screen down by swiping.

        Args:
            slow_mode: If True, use slower scroll (useful for expansions).
            screen_height: Screen height in pixels (default 1920).
            screen_width: Screen width in pixels (default 1080).

        Returns:
            True if successful, False otherwise.
        """
        # Calculate points at center of screen
        center_x = screen_width // 2
        start_y = int(screen_height * 0.7)  # Start at 70% height (bottom visible area)
        end_y = int(screen_height * 0.3)  # End at 30% height (top)

        # Use longer duration for slower scroll in slow mode
        duration_ms = 1000 if slow_mode else 500

        logger.info(
            f"Scrolling screen down: from ({center_x}, {start_y}) to ({center_x}, {end_y}) "
            f"(duration: {duration_ms}ms)"
        )
        return self.swipe(center_x, start_y, center_x, end_y, duration_ms=duration_ms)

