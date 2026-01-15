"""Reset expansions utility script."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from autogodpack.config.loader import load_config
from autogodpack.state.persistence import StatePersistence


def main():
    """Reset completed expansions."""
    project_root = Path(__file__).parent.parent

    # Load configuration
    try:
        config_path = project_root / "config.yaml"
        settings = load_config(config_path)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    # Reset expansions
    state_file = settings.paths.get_state_path(project_root)
    persistence = StatePersistence(state_file)
    persistence.reset_expansions()
    print("✓ Expansions reset successfully")


if __name__ == "__main__":
    main()






