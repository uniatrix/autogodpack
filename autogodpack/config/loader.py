"""Configuration loader from YAML file."""

import yaml
from pathlib import Path
from typing import Optional

from .settings import (
    Settings,
    ADBConfig,
    AutomationConfig,
    MatchingConfig,
    ScreenConfig,
    BattleConfig,
    ExpansionConfig,
    PathsConfig,
    LoggingConfig,
)


def load_config(config_path: Optional[Path] = None) -> Settings:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, looks for config.yaml in project root.

    Returns:
        Settings object with loaded configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is invalid YAML.
    """
    if config_path is None:
        # Look for config.yaml in project root (parent of autogodpack package)
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    if config_data is None:
        config_data = {}

    # Build Settings object from config data
    settings = Settings()

    # Load ADB config
    if "adb" in config_data:
        adb_data = config_data["adb"]
        settings.adb = ADBConfig(
            serial=adb_data.get("serial", "127.0.0.1:5585"),
            command_timeout=adb_data.get("command_timeout", 10),
        )

    # Load automation config
    if "automation" in config_data:
        auto_data = config_data["automation"]
        settings.automation = AutomationConfig(
            type=auto_data.get("type", "battle"),
            cycle_delay=auto_data.get("cycle_delay", 1.0),
            fast_mode=auto_data.get("fast_mode", False),
        )

    # Load matching config
    if "matching" in config_data:
        match_data = config_data["matching"]
        settings.matching = MatchingConfig(
            default_threshold=match_data.get("default_threshold", 0.75),
            verbose=match_data.get("verbose", True),
        )

    # Load screen config
    if "screens" in config_data:
        screen_data = config_data["screens"]
        settings.screens = ScreenConfig(
            check_interval=screen_data.get("check_interval", 0.4),
            fast_check_interval=screen_data.get("fast_check_interval", 0.1),
            tap_delay=screen_data.get("tap_delay", 1.0),
            fast_tap_delay=screen_data.get("fast_tap_delay", 0.2),
            retry_delay=screen_data.get("retry_delay", 0.5),
            fast_retry_delay=screen_data.get("fast_retry_delay", 0.15),
        )

    # Load battle config
    if "battle" in config_data:
        battle_data = config_data["battle"]
        settings.battle = BattleConfig(
            max_wait_time=battle_data.get("max_wait_time"),
            auto_toggle_verification=battle_data.get("auto_toggle_verification", True),
            battle_start_check_interval=battle_data.get("battle_start_check_interval", 2.0),
            battle_progress_check_interval=battle_data.get("battle_progress_check_interval", 0.5),
        )

    # Load expansion config
    if "expansions" in config_data:
        exp_data = config_data["expansions"]
        settings.expansions = ExpansionConfig(
            series_a=exp_data.get("series_a"),
            series_b=exp_data.get("series_b"),
            max_scrolls=exp_data.get("max_scrolls", 8),
            max_reset_attempts=exp_data.get("max_reset_attempts", 2),
            max_attempts_per_expansion=exp_data.get("max_attempts_per_expansion", 3),
        )

    # Load paths config
    if "paths" in config_data:
        paths_data = config_data["paths"]
        settings.paths = PathsConfig(
            templates=paths_data.get("templates", "autogodpack/templates"),
            logs=paths_data.get("logs", "logs"),
            state=paths_data.get("state", "completed_expansions.json"),
            reset_flag=paths_data.get("reset_flag", "reset_expansions.flag"),
        )

    # Load logging config
    if "logging" in config_data:
        log_data = config_data["logging"]
        settings.logging = LoggingConfig(
            level=log_data.get("level", "INFO"),
            file=log_data.get("file", "logs/battle_bot.log"),
            console=log_data.get("console", True),
            format=log_data.get("format", "%(asctime)s %(levelname)s %(message)s"),
        )

    return settings






