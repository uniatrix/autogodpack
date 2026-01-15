"""Template matching functionality."""

import os
import logging
from typing import Optional, Tuple, Dict
from pathlib import Path

import cv2
import numpy as np

from ..utils.exceptions import TemplateNotFoundError

logger = logging.getLogger(__name__)


class TemplateMatcher:
    """Handles template matching on screenshots with caching for performance."""

    def __init__(self, default_threshold: float = 0.75, verbose: bool = True):
        """
        Initialize template matcher.

        Args:
            default_threshold: Default matching threshold (0.0 to 1.0).
            verbose: Enable verbose logging.
        """
        self.default_threshold = default_threshold
        self.verbose = verbose
        # Cache templates in memory to avoid repeated disk I/O
        self._template_cache: Dict[str, np.ndarray] = {}
        self._template_mtime_cache: Dict[str, float] = {}

    def _load_template(self, template_path: str) -> Optional[np.ndarray]:
        """
        Load template with caching. Checks file modification time to invalidate cache.
        
        Args:
            template_path: Path to template image file.
            
        Returns:
            Template image array or None if failed.
        """
        # Check if template is cached and still valid
        if template_path in self._template_cache:
            try:
                current_mtime = os.path.getmtime(template_path)
                if current_mtime == self._template_mtime_cache.get(template_path, 0):
                    return self._template_cache[template_path]
            except OSError:
                # File might have been deleted, remove from cache
                self._template_cache.pop(template_path, None)
                self._template_mtime_cache.pop(template_path, None)
        
        # Load template from disk
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None:
            return None
        
        # Cache template
        try:
            mtime = os.path.getmtime(template_path)
            self._template_cache[template_path] = template
            self._template_mtime_cache[template_path] = mtime
        except OSError:
            pass  # Cache without mtime if can't get it
        
        return template

    def find_template(
        self,
        screen: np.ndarray,
        template_path: str,
        threshold: Optional[float] = None,
        verbose: Optional[bool] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Find template in screen image.

        Args:
            screen: BGR image array of the screen.
            template_path: Path to template image file.
            threshold: Matching threshold (uses default if None).
            verbose: Override verbose setting for this call.

        Returns:
            Tuple of (x, y) center coordinates if found, None otherwise.
        """
        if threshold is None:
            threshold = self.default_threshold

        if verbose is None:
            verbose = self.verbose

        if not os.path.exists(template_path):
            logger.error(f"Template not found: {template_path}")
            raise TemplateNotFoundError(f"Template file not found: {template_path}")

        # Load template (with caching)
        template = self._load_template(template_path)
        if template is None:
            logger.error(f"Failed to load template: {template_path}")
            raise TemplateNotFoundError(f"Failed to load template image: {template_path}")

        # Perform template matching
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape[:2]
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2

            if verbose:
                logger.info(
                    f"Matched {os.path.basename(template_path)} at {cx},{cy} "
                    f"(score={max_val:.3f})"
                )
            return (cx, cy)

        return None

    def get_template_path(
        self, filename: str, base_dir: Path, screen_dir: Optional[Path] = None
    ) -> Path:
        """
        Get full path to template file.

        Args:
            filename: Template filename.
            base_dir: Base template directory.
            screen_dir: Optional screen-specific subdirectory.

        Returns:
            Full path to template file.
        """
        if screen_dir:
            return screen_dir / filename
        return base_dir / filename






