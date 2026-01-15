"""Logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Optional

from ..config.settings import LoggingConfig


def setup_logging(config: LoggingConfig, log_dir: Path) -> None:
    """
    Set up logging configuration.

    Args:
        config: Logging configuration.
        log_dir: Directory for log files.
    """
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get log file path
    log_file = log_dir / Path(config.file).name

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(getattr(logging, config.level.upper()))
    file_formatter = logging.Formatter(config.format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    if config.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level.upper()))
        console_formatter = logging.Formatter(config.format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    logging.info(f"Logging configured: level={config.level}, file={log_file}")






