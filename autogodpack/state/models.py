"""State data models."""

from dataclasses import dataclass, field
from typing import Set, Dict


@dataclass
class ExpansionState:
    """State for tracking completed expansions."""

    completed: Set[str] = field(default_factory=set)

    def add_completed(self, expansion_key: str) -> None:
        """
        Mark an expansion as completed.

        Args:
            expansion_key: Expansion key in format "A_NAME" or "B_NAME".
        """
        self.completed.add(expansion_key)

    def is_completed(self, expansion_key: str) -> bool:
        """
        Check if an expansion is completed.

        Args:
            expansion_key: Expansion key in format "A_NAME" or "B_NAME".

        Returns:
            True if completed, False otherwise.
        """
        return expansion_key in self.completed

    def reset(self) -> None:
        """Reset all completed expansions."""
        self.completed.clear()

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation.
        """
        return {"completed": list(self.completed)}

    @classmethod
    def from_dict(cls, data: dict) -> "ExpansionState":
        """
        Create from dictionary.

        Args:
            data: Dictionary with 'completed' list.

        Returns:
            ExpansionState instance.
        """
        completed = set(data.get("completed", []))
        return cls(completed=completed)


@dataclass
class MultiBotExpansionState:
    """State for tracking completed expansions per bot slot."""

    bot_expansions: Dict[int, ExpansionState] = field(default_factory=dict)

    def get_bot_state(self, slot_id: int) -> ExpansionState:
        """
        Get expansion state for a specific bot slot.

        Args:
            slot_id: Bot slot ID (0-3).

        Returns:
            ExpansionState for the bot slot.
        """
        if slot_id not in self.bot_expansions:
            self.bot_expansions[slot_id] = ExpansionState()
        return self.bot_expansions[slot_id]

    def set_bot_state(self, slot_id: int, state: ExpansionState) -> None:
        """
        Set expansion state for a specific bot slot.

        Args:
            slot_id: Bot slot ID (0-3).
            state: ExpansionState to set.
        """
        self.bot_expansions[slot_id] = state

    def reset_bot(self, slot_id: int) -> None:
        """Reset expansions for a specific bot slot."""
        if slot_id in self.bot_expansions:
            self.bot_expansions[slot_id].reset()

    def reset_all(self) -> None:
        """Reset all bot expansions."""
        self.bot_expansions.clear()

    def to_dict(self) -> dict:
        """
        Convert to dictionary for serialization.
        Uses 1-indexed bot IDs in JSON (1, 2, 3, 4) while internal code uses 0-indexed (0, 1, 2, 3).
        Bots are sorted by ID to ensure consistent ordering in JSON.

        Returns:
            Dictionary representation.
        """
        return {
            "bots": {
                str(slot_id + 1): state.to_dict()  # Convert 0-indexed to 1-indexed for JSON
                for slot_id, state in sorted(self.bot_expansions.items())  # Sort by slot_id for consistent ordering
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MultiBotExpansionState":
        """
        Create from dictionary.
        Converts 1-indexed bot IDs from JSON (1, 2, 3, 4) to 0-indexed for internal use (0, 1, 2, 3).

        Args:
            data: Dictionary with 'bots' mapping slot IDs to expansion states.

        Returns:
            MultiBotExpansionState instance.
        """
        instance = cls()
        bots_data = data.get("bots", {})
        for slot_id_str, state_data in bots_data.items():
            try:
                json_slot_id = int(slot_id_str)  # 1-indexed from JSON
                internal_slot_id = json_slot_id - 1  # Convert to 0-indexed for internal use
                if 0 <= internal_slot_id <= 3:  # Validate range
                    instance.bot_expansions[internal_slot_id] = ExpansionState.from_dict(state_data)
            except (ValueError, KeyError):
                continue
        return instance

    @classmethod
    def from_legacy_dict(cls, data: dict) -> "MultiBotExpansionState":
        """
        Convert from legacy single-bot format.
        Legacy format is treated as bot 1 (internal slot 0).

        Args:
            data: Legacy dictionary with 'completed' list.

        Returns:
            MultiBotExpansionState instance with data in slot 0 (bot 1).
        """
        instance = cls()
        completed = set(data.get("completed", []))
        instance.bot_expansions[0] = ExpansionState(completed=completed)
        return instance

