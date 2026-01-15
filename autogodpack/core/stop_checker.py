"""Stop flag checker for interrupting long-running operations."""

import threading
from typing import Callable, Optional


class StopChecker:
    """Manages stop flag checking for interruptible operations."""

    def __init__(self, check_func: Callable[[], bool]):
        """
        Initialize stop checker.

        Args:
            check_func: Function that returns True if stop is requested.
        """
        self.check_func = check_func

    def check(self) -> bool:
        """
        Check if stop is requested.

        Returns:
            True if stop requested, False otherwise.
        """
        return self.check_func()

    def interruptible_sleep(self, duration: float, check_interval: float = 0.1) -> bool:
        """
        Sleep for duration, checking stop flag periodically.

        Args:
            duration: Total sleep duration in seconds.
            check_interval: How often to check stop flag.

        Returns:
            True if interrupted by stop request, False if completed normally.
        """
        remaining = duration
        while remaining > 0:
            if self.check():
                return True  # Interrupted
            sleep_time = min(check_interval, remaining)
            import time
            time.sleep(sleep_time)
            remaining -= sleep_time
        return False  # Completed normally


# Global stop checker instance (set by BattleBot)
_global_stop_checker: Optional[StopChecker] = None


def set_global_stop_checker(checker: StopChecker) -> None:
    """Set global stop checker instance."""
    global _global_stop_checker
    _global_stop_checker = checker


def get_global_stop_checker() -> Optional[StopChecker]:
    """Get global stop checker instance."""
    return _global_stop_checker


def check_stop() -> bool:
    """
    Check global stop flag.

    Returns:
        True if stop requested, False otherwise.
    """
    if _global_stop_checker:
        return _global_stop_checker.check()
    return False






