"""Entry point for AutoGodPack."""

import sys
import signal
from pathlib import Path

from .config.loader import load_config
from .config.settings import Settings
from .utils.logging import setup_logging
from .core.bot import BattleBot


def main() -> None:
    """Main entry point."""
    # Get project root (parent of autogodpack package)
    project_root = Path(__file__).parent.parent

    # Load configuration
    try:
        config_path = project_root / "config.yaml"
        settings = load_config(config_path)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}")
        print("Please create config.yaml in the project root.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Setup logging
    log_dir = settings.paths.get_log_path(project_root)
    setup_logging(settings.logging, log_dir)

    # Initialize bot
    bot = BattleBot(settings, project_root)

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run bot
    bot.run()


if __name__ == "__main__":
    main()






