"""Error handler for GUI to prevent freezing."""

import logging
import traceback
import sys
from typing import Callable, Any


def safe_call(func: Callable, *args, **kwargs) -> Any:
    """
    Safely call a function and catch all exceptions.
    
    Args:
        func: Function to call.
        *args: Positional arguments.
        **kwargs: Keyword arguments.
        
    Returns:
        Function result or None if error occurred.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {e}\n{traceback.format_exc()}"
        logging.error(error_msg)
        print(f"ERROR: {error_msg}", file=sys.stderr)
        return None


def log_to_file(message: str, level: str = "ERROR") -> None:
    """
    Log message to file as fallback.
    
    Args:
        message: Message to log.
        level: Log level.
    """
    try:
        from pathlib import Path
        log_file = Path(__file__).parent.parent.parent / "logs" / "gui_errors.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{level}] {message}\n")
    except Exception:
        pass  # If logging fails, at least we tried






