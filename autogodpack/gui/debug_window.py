"""Debug window for troubleshooting."""

import tkinter as tk
from tkinter import ttk, scrolledtext
import traceback
import sys
from pathlib import Path


class DebugWindow:
    """Debug window for showing detailed error information."""

    def __init__(self, parent: tk.Tk):
        """
        Initialize debug window.

        Args:
            parent: Parent window.
        """
        self.window = tk.Toplevel(parent)
        self.window.title("Debug Information")
        self.window.geometry("800x600")

        # Create text widget
        self.text = scrolledtext.ScrolledText(self.window, wrap=tk.WORD)
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Add close button
        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(pady=5)

    def add_info(self, title: str, info: str) -> None:
        """
        Add information to debug window.

        Args:
            title: Section title.
            info: Information text.
        """
        self.text.insert(tk.END, f"\n{'='*60}\n")
        self.text.insert(tk.END, f"{title}\n")
        self.text.insert(tk.END, f"{'='*60}\n")
        self.text.insert(tk.END, f"{info}\n")
        self.text.see(tk.END)

    def show_exception(self, exc: Exception) -> None:
        """
        Show exception details.

        Args:
            exc: Exception object.
        """
        self.add_info("Exception", str(exc))
        self.add_info("Traceback", traceback.format_exc())

    def show_system_info(self) -> None:
        """Show system information."""
        import platform
        import sys

        info = f"""
Python Version: {sys.version}
Platform: {platform.platform()}
Architecture: {platform.architecture()}
Current Directory: {Path.cwd()}
Executable: {sys.executable}
        """
        self.add_info("System Information", info)

