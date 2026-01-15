"""Base screen handler class."""

import logging
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

from ..adb.client import ADBClient
from ..adb.commands import ADBCommands
from ..image.screenshot import ScreenshotCapture
from ..image.matcher import TemplateMatcher
from ..config.settings import Settings

logger = logging.getLogger(__name__)


class ScreenHandler(ABC):
    """Base class for screen handlers."""

    def __init__(
        self,
        client: ADBClient,
        commands: ADBCommands,
        screenshot: ScreenshotCapture,
        matcher: TemplateMatcher,
        settings: Settings,
        template_base_dir: Path,
    ):
        """
        Initialize screen handler.

        Args:
            client: ADB client.
            commands: ADB commands.
            screenshot: Screenshot capture.
            matcher: Template matcher.
            settings: Configuration settings.
            template_base_dir: Base directory for templates.
        """
        self.client = client
        self.commands = commands
        self.screenshot = screenshot
        self.matcher = matcher
        self.settings = settings
        self.template_base_dir = template_base_dir

    @abstractmethod
    def can_handle(self, screen: Optional[object] = None) -> bool:
        """
        Check if this handler can handle the current screen.

        Args:
            screen: Optional screenshot image.

        Returns:
            True if this handler can handle the screen.
        """
        pass

    @abstractmethod
    def handle(self) -> bool:
        """
        Handle the current screen.

        Returns:
            True if handling was successful.
        """
        pass

    def get_template_path(self, filename: str, screen_dir: Optional[Path] = None) -> Path:
        """
        Get full path to template file.

        Args:
            filename: Template filename.
            screen_dir: Optional screen-specific subdirectory.

        Returns:
            Full path to template.
        """
        if screen_dir:
            return screen_dir / filename
        return self.template_base_dir / filename

    def wait_and_tap_template(
        self,
        filename: str,
        timeout: float = 10.0,
        threshold: Optional[float] = None,
        screen_dir: Optional[Path] = None,
        fast_mode: Optional[bool] = None,
    ) -> bool:
        """
        Wait for template to appear and tap it.

        Args:
            filename: Template filename.
            timeout: Maximum wait time.
            threshold: Matching threshold.
            screen_dir: Optional screen directory.
            fast_mode: Override fast mode setting.

        Returns:
            True if found and tapped.
        """
        import time

        if threshold is None:
            threshold = self.settings.matching.default_threshold
        if fast_mode is None:
            fast_mode = self.settings.automation.fast_mode

        path = self.get_template_path(filename, screen_dir)
        end_time = time.time() + timeout
        attempts = 0

        check_interval = (
            self.settings.screens.fast_check_interval
            if fast_mode
            else self.settings.screens.check_interval
        )
        tap_delay = (
            self.settings.screens.fast_tap_delay
            if fast_mode
            else self.settings.screens.tap_delay
        )
        retry_delay = (
            self.settings.screens.fast_retry_delay
            if fast_mode
            else self.settings.screens.retry_delay
        )

        while time.time() < end_time:
            attempts += 1
            screen = self.screenshot.capture_bgr()
            if screen is None:
                logger.warning(f"  Attempt {attempts}: Could not capture screen")
                time.sleep(0.2)
                continue

            pos = self.matcher.find_template(
                screen, str(path), threshold=threshold, verbose=False
            )
            if pos:
                logger.info(f"  Template {filename} found at {pos} (attempt {attempts})")
                if self.commands.tap(pos[0], pos[1], delay=tap_delay):
                    return True
                else:
                    logger.warning("  Tap failed, retrying...")
                    time.sleep(retry_delay)
                    continue

            time.sleep(check_interval)

        logger.error(
            f"Template {filename} not found after {attempts} attempts (timeout={timeout}s)"
        )
        return False






