"""Configuration settings dataclass."""

from dataclasses import dataclass
from typing import Optional, List
from pathlib import Path


@dataclass
class ADBConfig:
    """ADB configuration settings."""
    serial: str = "127.0.0.1:5585"
    command_timeout: int = 10


@dataclass
class AutomationConfig:
    """Automation settings."""
    type: str = "battle"
    cycle_delay: float = 1.0
    fast_mode: bool = False


@dataclass
class MatchingConfig:
    """Template matching configuration."""
    default_threshold: float = 0.75
    verbose: bool = True


@dataclass
class ScreenConfig:
    """Screen detection and interaction settings."""
    check_interval: float = 0.4
    fast_check_interval: float = 0.1
    tap_delay: float = 1.0
    fast_tap_delay: float = 0.2
    retry_delay: float = 0.5
    fast_retry_delay: float = 0.15


@dataclass
class BattleConfig:
    """Battle-specific settings."""
    max_wait_time: Optional[float] = None
    auto_toggle_verification: bool = True
    battle_start_check_interval: float = 2.0
    battle_progress_check_interval: float = 0.5


@dataclass
class ExpansionConfig:
    """Expansion selection settings."""
    series_a: List[str] = None
    series_b: List[str] = None
    max_scrolls: int = 8
    max_reset_attempts: int = 2
    max_attempts_per_expansion: int = 3

    def __post_init__(self):
        """Initialize default expansion lists if not provided."""
        if self.series_a is None:
            self.series_a = ["GA", "MI", "STS", "TL", "SR", "CG", "EC", "EG", "WSS", "SS", "DPex"]
        if self.series_b is None:
            self.series_b = ["CB", "MR"]


@dataclass
class PathsConfig:
    """Path configuration."""
    templates: str = "autogodpack/templates"
    logs: str = "logs"
    state: str = "completed_expansions.json"
    reset_flag: str = "reset_expansions.flag"

    def get_template_path(self, base_path: Path) -> Path:
        """Get absolute template path."""
        return base_path / self.templates

    def get_log_path(self, base_path: Path) -> Path:
        """Get absolute log path."""
        return base_path / self.logs

    def get_state_path(self, base_path: Path) -> Path:
        """Get absolute state file path."""
        return base_path / self.state

    def get_reset_flag_path(self, base_path: Path) -> Path:
        """Get absolute reset flag path."""
        return base_path / self.reset_flag


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "logs/battle_bot.log"
    console: bool = True
    format: str = "%(asctime)s %(levelname)s %(message)s"


@dataclass
class Settings:
    """Main settings container."""

    adb: ADBConfig = None
    automation: AutomationConfig = None
    matching: MatchingConfig = None
    screens: ScreenConfig = None
    battle: BattleConfig = None
    expansions: ExpansionConfig = None
    paths: PathsConfig = None
    logging: LoggingConfig = None

    def __post_init__(self):
        """Initialize default configs if not provided."""
        if self.adb is None:
            self.adb = ADBConfig()
        if self.automation is None:
            self.automation = AutomationConfig()
        if self.matching is None:
            self.matching = MatchingConfig()
        if self.screens is None:
            self.screens = ScreenConfig()
        if self.battle is None:
            self.battle = BattleConfig()
        if self.expansions is None:
            self.expansions = ExpansionConfig()
        if self.paths is None:
            self.paths = PathsConfig()
        if self.logging is None:
            self.logging = LoggingConfig()






