"""State persistence functionality."""

import json
import logging
from pathlib import Path
from typing import Optional

from .models import ExpansionState, MultiBotExpansionState
from ..utils.exceptions import StateError

logger = logging.getLogger(__name__)


class StatePersistence:
    """Handles persistence of bot state."""

    def __init__(self, state_file: Path):
        """
        Initialize state persistence.

        Args:
            state_file: Path to state file.
        """
        self.state_file = state_file
        self.slot_id: Optional[int] = None  # Bot slot ID for per-bot state

    def load_expansions(self, slot_id: Optional[int] = None) -> ExpansionState:
        """
        Load completed expansions from file for a specific bot slot.

        Args:
            slot_id: Bot slot ID (0-3). If None, uses self.slot_id or defaults to 0.

        Returns:
            ExpansionState with loaded data for the slot, or empty state if slot not found.
        """
        # Use instance slot_id if not provided
        effective_slot_id = slot_id if slot_id is not None else (self.slot_id if self.slot_id is not None else 0)
        
        if not self.state_file.exists():
            logger.debug("State file does not exist, initializing empty state")
            return ExpansionState()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.debug("State file is empty, initializing empty state")
                    return ExpansionState()

                data = json.loads(content)
                
                # Check if it's multi-bot format
                if "bots" in data:
                    multi_state = MultiBotExpansionState.from_dict(data)
                    return multi_state.get_bot_state(effective_slot_id)
                else:
                    # Legacy format - convert to multi-bot
                    multi_state = MultiBotExpansionState.from_legacy_dict(data)
                    return multi_state.get_bot_state(effective_slot_id)

        except json.JSONDecodeError as e:
            logger.warning(f"Error parsing state JSON: {e}")
            logger.warning("Initializing state file with empty structure...")
            # Try to create valid file
            empty_state = ExpansionState()
            self.save_expansions(empty_state, slot_id=0)
            return empty_state

        except Exception as e:
            logger.warning(f"Error loading state: {e}")
            return ExpansionState()

    def load_multi_bot_expansions(self) -> MultiBotExpansionState:
        """
        Load all bot expansion states from file.

        Returns:
            MultiBotExpansionState with all bot data.
        """
        if not self.state_file.exists():
            logger.debug("State file does not exist, initializing empty state")
            return MultiBotExpansionState()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.debug("State file is empty, initializing empty state")
                    return MultiBotExpansionState()

                data = json.loads(content)
                
                # Check if it's multi-bot format
                if "bots" in data:
                    return MultiBotExpansionState.from_dict(data)
                else:
                    # Legacy format - convert to multi-bot
                    return MultiBotExpansionState.from_legacy_dict(data)

        except json.JSONDecodeError as e:
            logger.warning(f"Error parsing state JSON: {e}")
            logger.warning("Initializing state file with empty structure...")
            empty_state = MultiBotExpansionState()
            self.save_multi_bot_expansions(empty_state)
            return empty_state

        except Exception as e:
            logger.warning(f"Error loading state: {e}")
            return MultiBotExpansionState()

    def save_expansions(self, state: ExpansionState, slot_id: Optional[int] = None) -> None:
        """
        Save completed expansions to file for a specific bot slot.

        Args:
            state: ExpansionState to save.
            slot_id: Bot slot ID (0-3). If None, uses self.slot_id or defaults to 0.

        Raises:
            StateError: If save fails.
        """
        # Use instance slot_id if not provided
        effective_slot_id = slot_id if slot_id is not None else (self.slot_id if self.slot_id is not None else 0)
        
        # Load existing multi-bot state
        multi_state = self.load_multi_bot_expansions()
        multi_state.set_bot_state(effective_slot_id, state)
        self.save_multi_bot_expansions(multi_state)

    def save_multi_bot_expansions(self, multi_state: MultiBotExpansionState) -> None:
        """
        Save all bot expansion states to file.

        Args:
            multi_state: MultiBotExpansionState to save.

        Raises:
            StateError: If save fails.
        """
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(multi_state.to_dict(), f, indent=2)

            logger.debug(f"State saved to {self.state_file}")

        except Exception as e:
            logger.error(f"Error saving state: {e}")
            raise StateError(f"Failed to save state: {e}") from e

    def reset_expansions(self, slot_id: Optional[int] = None) -> None:
        """
        Reset completed expansions for a specific bot or all bots.

        Args:
            slot_id: Bot slot ID (0-3). If None, resets all bots.
        """
        if slot_id is not None:
            multi_state = self.load_multi_bot_expansions()
            multi_state.reset_bot(slot_id)
            self.save_multi_bot_expansions(multi_state)
            logger.info(f"✓ Completed expansions reset for bot {slot_id}")
        else:
            empty_state = MultiBotExpansionState()
            self.save_multi_bot_expansions(empty_state)
            logger.info("✓ Completed expansions reset for all bots")

    def check_reset_flag(self, reset_flag_file: Path, slot_id: Optional[int] = None) -> bool:
        """
        Check if reset flag file exists and reset if found.

        Args:
            reset_flag_file: Path to reset flag file.
            slot_id: Bot slot ID (0-3). If None, uses self.slot_id or resets all.

        Returns:
            True if reset was performed, False otherwise.
        """
        if reset_flag_file.exists():
            effective_slot_id = slot_id if slot_id is not None else self.slot_id
            logger.info(f"Reset flag found, resetting expansions for bot {effective_slot_id}...")
            self.reset_expansions(effective_slot_id)
            try:
                reset_flag_file.unlink()
                logger.info("✓ Reset flag file removed")
            except Exception as e:
                logger.warning(f"Error removing reset flag file: {e}")
            return True
        return False
