"""Main GUI application."""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import traceback
import sys
from pathlib import Path
from typing import Optional, Dict

from ..config.loader import load_config
from ..config.settings import Settings
from ..adb.device_manager import DeviceManager
from ..adb.client import ADBClient
from ..utils.logging import setup_logging
from ..core.bot import BattleBot
from ..core.multi_bot_manager import MultiBotManager
from .debug_window import DebugWindow
from .error_handler import safe_call, log_to_file
from ..image.screenshot import ScreenshotCapture


class ExpansionManagerWindow:
    """Window for managing expansion completion status."""
    
    # Expansion lists (matching battle_bot.py)
    EXPANSIONS_SERIES_A = ["GA", "MI", "STS", "TL", "SR", "CG", "EC", "EG", "WSS", "SS", "DPex"]
    EXPANSIONS_SERIES_B = ["CB", "MR"]
    
    def __init__(self, parent: tk.Tk, project_root: Path):
        """
        Initialize expansion manager window.
        
        Args:
            parent: Parent window.
            project_root: Project root directory.
        """
        self.project_root = project_root
        self.expansions_file = project_root / "completed_expansions.json"
        
        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("Manage Expansions")
        self.window.geometry("500x600")
        self.window.resizable(False, False)
        
        # Load current completed expansions
        self.completed_expansions = self._load_completed_expansions()
        
        # Create UI
        self._create_widgets()
        
        # Center window
        self.window.transient(parent)
        self.window.grab_set()
        
    def _load_completed_expansions(self) -> set:
        """Load completed expansions from file."""
        import json
        if self.expansions_file.exists():
            try:
                with open(self.expansions_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return set()
                    data = json.loads(content)
                    return set(data.get('completed', []))
            except Exception as e:
                logging.warning(f"Error loading expansions: {e}")
                return set()
        return set()
    
    def _save_completed_expansions(self) -> None:
        """Save completed expansions to file."""
        import json
        try:
            with open(self.expansions_file, 'w') as f:
                json.dump({'completed': list(self.completed_expansions)}, f, indent=2)
            logging.info("Expansion completion status saved")
        except Exception as e:
            logging.error(f"Error saving expansions: {e}")
            messagebox.showerror("Error", f"Failed to save expansions: {e}")
    
    def _create_widgets(self) -> None:
        """Create UI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = ttk.Label(
            main_frame,
            text="Check expansions to mark them as completed (will be skipped).\n"
                 "Uncheck to make them available for checking.\n\n"
                 "Note: The bot will still mark expansions as completed automatically\n"
                 "when no hourglasses are found.",
            justify=tk.LEFT,
            font=("Arial", 9)
        )
        instructions.pack(pady=(0, 10))
        
        # Scrollable frame for checkboxes
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(canvas_frame, height=400)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Store checkboxes
        self.checkboxes = {}
        
        # Series A
        series_a_label = ttk.Label(scrollable_frame, text="Series A", font=("Arial", 10, "bold"))
        series_a_label.pack(anchor=tk.W, pady=(0, 5))
        
        series_a_frame = ttk.Frame(scrollable_frame)
        series_a_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        for expansion in self.EXPANSIONS_SERIES_A:
            expansion_key = f"A_{expansion}"
            var = tk.BooleanVar(value=expansion_key in self.completed_expansions)
            checkbox = ttk.Checkbutton(
                series_a_frame,
                text=expansion,
                variable=var,
                command=lambda key=expansion_key, v=var: self._on_checkbox_change(key, v)
            )
            checkbox.pack(anchor=tk.W, pady=2)
            self.checkboxes[expansion_key] = var
        
        # Series B
        series_b_label = ttk.Label(scrollable_frame, text="Series B", font=("Arial", 10, "bold"))
        series_b_label.pack(anchor=tk.W, pady=(10, 5))
        
        series_b_frame = ttk.Frame(scrollable_frame)
        series_b_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        for expansion in self.EXPANSIONS_SERIES_B:
            expansion_key = f"B_{expansion}"
            var = tk.BooleanVar(value=expansion_key in self.completed_expansions)
            checkbox = ttk.Checkbutton(
                series_b_frame,
                text=expansion,
                variable=var,
                command=lambda key=expansion_key, v=var: self._on_checkbox_change(key, v)
            )
            checkbox.pack(anchor=tk.W, pady=2)
            self.checkboxes[expansion_key] = var
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            buttons_frame,
            text="Select All",
            command=self._select_all
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="Deselect All",
            command=self._deselect_all
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="Reset to Current Status",
            command=self._reset_to_current
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame,
            text="Close",
            command=self.window.destroy
        ).pack(side=tk.RIGHT, padx=5)
    
    def _on_checkbox_change(self, expansion_key: str, var: tk.BooleanVar) -> None:
        """Handle checkbox change."""
        if var.get():
            self.completed_expansions.add(expansion_key)
        else:
            self.completed_expansions.discard(expansion_key)
        self._save_completed_expansions()
    
    def _select_all(self) -> None:
        """Select all expansions."""
        for expansion_key, var in self.checkboxes.items():
            var.set(True)
            self.completed_expansions.add(expansion_key)
        self._save_completed_expansions()
    
    def _deselect_all(self) -> None:
        """Deselect all expansions."""
        for expansion_key, var in self.checkboxes.items():
            var.set(False)
            self.completed_expansions.discard(expansion_key)
        self._save_completed_expansions()
    
    def _reset_to_current(self) -> None:
        """Reset checkboxes to current file status."""
        self.completed_expansions = self._load_completed_expansions()
        for expansion_key, var in self.checkboxes.items():
            var.set(expansion_key in self.completed_expansions)


class AutoGodPackGUI:
    """Main GUI application window."""

    def __init__(self, root: tk.Tk):
        """
        Initialize GUI application.

        Args:
            root: Tkinter root window.
        """
        self.root = root
        self.root.title("AutoGodPack - Battle Bot")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        self.root.minsize(700, 500)
        
        # Flag to track if GUI is shutting down
        self._shutting_down = False
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Apply navy color theme - single shade of navy and gray
        NAVY_COLOR = '#1e3a5f'
        # Use the same gray shade as inside LabelFrames (system default for clam theme)
        GRAY_COLOR = '#f0f0f0'
        
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure root window background to navy
        self.root.configure(bg=NAVY_COLOR)
        
        # Notebook styling - gray background for content area
        style.configure('TNotebook', background=GRAY_COLOR, borderwidth=0, relief='flat')
        
        # Valve-style tabs: selected tab expands upward with gray bg and navy text
        # Unselected tabs: navy bg with gray text (no white)
        style.configure('TNotebook.Tab', 
                       background=NAVY_COLOR, 
                       foreground=GRAY_COLOR, 
                       borderwidth=0,
                       padding=[12, 8],
                       focuscolor='none',
                       relief='flat',
                       font=('Arial', 9))
        style.map('TNotebook.Tab', 
                 background=[('selected', GRAY_COLOR), ('active', NAVY_COLOR)], 
                 foreground=[('selected', NAVY_COLOR), ('active', GRAY_COLOR)],
                 # Expand upward when selected - increase top padding
                 padding=[('selected', [12, 16, 8, 8]), ('!selected', [12, 8])],
                 # Use expand for additional upward push
                 expand=[('selected', [1, 1, 6, 0])])
        
        # Frame styling - all frames use gray background
        style.configure('TFrame', background=GRAY_COLOR)
        style.configure('TLabelFrame', background=GRAY_COLOR, foreground=NAVY_COLOR, borderwidth=1)
        style.configure('TLabelFrame.Label', background=GRAY_COLOR, foreground=NAVY_COLOR, font=('Arial', 9, 'bold'))
        
        # Button styling - gray text on navy (no white)
        style.configure('TButton', background=NAVY_COLOR, foreground=GRAY_COLOR, borderwidth=1, padding=5)
        style.map('TButton', background=[('active', NAVY_COLOR), ('pressed', NAVY_COLOR)], foreground=[('active', GRAY_COLOR), ('pressed', GRAY_COLOR)])
        
        # Icon button style for bot controls
        style.configure('Icon.TButton', background=NAVY_COLOR, foreground=GRAY_COLOR, borderwidth=1, padding=3, font=('Arial', 10))
        style.map('Icon.TButton', background=[('active', NAVY_COLOR), ('pressed', NAVY_COLOR)], foreground=[('active', GRAY_COLOR), ('pressed', GRAY_COLOR)])
        
        # Label styling
        style.configure('TLabel', background=GRAY_COLOR)
        style.configure('TCheckbutton', background=GRAY_COLOR)
        
        # Entry styling - use navy background with gray text (no white)
        style.configure('TEntry', fieldbackground=NAVY_COLOR, foreground=GRAY_COLOR, borderwidth=1)
        
        # Scrollbar styling - ensure no white parts
        style.configure('TScrollbar', 
                       background=GRAY_COLOR, 
                       troughcolor=GRAY_COLOR, 
                       borderwidth=0,
                       darkcolor=GRAY_COLOR,
                       lightcolor=GRAY_COLOR)
        style.map('TScrollbar',
                 background=[('active', GRAY_COLOR), ('pressed', GRAY_COLOR)],
                 troughcolor=[('active', GRAY_COLOR), ('pressed', GRAY_COLOR)])
        
        # Store colors for use in canvas
        self.navy_color = NAVY_COLOR
        self.gray_color = GRAY_COLOR

        # Get project root
        self.project_root = Path(__file__).parent.parent.parent

        # Load configuration
        try:
            # Try multiple possible config locations
            config_paths = [
                self.project_root / "config.yaml",
                Path(__file__).parent.parent.parent / "config.yaml",
                Path.cwd() / "config.yaml",
            ]
            
            config_path = None
            for path in config_paths:
                if path.exists():
                    config_path = path
                    break
            
            if config_path:
                self.settings = load_config(config_path)
            else:
                # Create default config
                from ..config.settings import Settings
                self.settings = Settings()
                messagebox.showwarning(
                    "Configuration Warning",
                    "config.yaml not found. Using default settings.\n"
                    "Please create config.yaml for full functionality."
                )
        except Exception as e:
            messagebox.showerror("Configuration Error", f"Failed to load config: {e}")
            from ..config.settings import Settings
            self.settings = Settings()
        
        # Setup logging to text widget
        self.setup_logging()

        # Initialize multi-bot manager
        self.multi_bot_manager = MultiBotManager(self.settings, self.project_root)
        
        # Bot slot widgets storage
        self.bot_slots: Dict[int, Dict[str, any]] = {}
        
        # Expansion checkboxes storage (initialized early to avoid AttributeError)
        self.expansion_checkboxes: Dict[int, Dict[str, tk.BooleanVar]] = {}
        
        # Legacy bot state (for backward compatibility)
        self.bot: Optional[BattleBot] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.bot_running = False
        
        # ADB client for utilities (screenshot, etc.)
        self.adb_client: Optional[ADBClient] = None
        
        # Device preferences file
        self.devices_file = self.project_root / "bot_devices.json"
        
        # Load saved device IPs
        self.saved_devices = self._load_saved_devices()
        
        # Create UI
        self.create_widgets()

        # Start device refresh timer
        self.refresh_devices()
        self.root.after(2000, self.auto_refresh_devices)

    def setup_logging(self) -> None:
        """Setup logging to GUI text widget."""
        # Create custom handler for GUI
        self.log_handler = GUILogHandler(self)
        self.log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        self.log_handler.setFormatter(formatter)

        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(logging.INFO)

    def create_widgets(self) -> None:
        """Create GUI widgets with tabbed interface."""
        # Main container - use gray background, no padding
        main_container = ttk.Frame(self.root, padding="0")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook (tabs) - no padding, gray background
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        # Force notebook background to gray (override any defaults)
        self.notebook.configure(style='TNotebook')
        
        # Tab 1: Bot Control (with logs) - gray background, no padding (use manual spacing)
        bot_tab = ttk.Frame(self.notebook, padding="0")
        self.notebook.add(bot_tab, text="Bot Control")
        self._create_bot_control_tab(bot_tab)
        
        # Tab 2: Expansion Management - gray background, no padding
        expansion_tab = ttk.Frame(self.notebook, padding="0")
        self.notebook.add(expansion_tab, text="Expansions")
        self._create_expansion_tab(expansion_tab)
        
        # Tab 3: Device Management - gray background, no padding
        device_tab = ttk.Frame(self.notebook, padding="0")
        self.notebook.add(device_tab, text="Devices")
        self._create_device_tab(device_tab)
    
    def _create_bot_control_tab(self, parent: ttk.Frame) -> None:
        """Create multi-bot control tab with grid layout."""
        # Outer padding frame with gray background
        outer_frame = ttk.Frame(parent, padding="10")
        outer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = ttk.Label(
            outer_frame,
            text="Configure up to 4 battle bots, each connected to a different BlueStacks instance.\n"
                 "Enter the ADB IP:Port for each bot (e.g., 127.0.0.1:5585) and click Start.",
            justify=tk.LEFT,
            font=("Arial", 9),
            foreground="gray"
        )
        instructions.pack(fill=tk.X, pady=(0, 10))
        
        # Multi-bot grid container
        grid_container = ttk.Frame(outer_frame)
        grid_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create 2x2 grid of bot slots
        self.bot_slots = {}
        for slot_id in range(4):
            row = slot_id // 2
            col = slot_id % 2
            
            slot_frame = self._create_bot_slot(grid_container, slot_id)
            slot_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        
        # Configure grid weights for equal distribution
        grid_container.columnconfigure(0, weight=1)
        grid_container.columnconfigure(1, weight=1)
        grid_container.rowconfigure(0, weight=1)
        grid_container.rowconfigure(1, weight=1)
        
        # Global controls
        global_controls = ttk.LabelFrame(outer_frame, text="Global Controls", padding="8")
        global_controls.pack(fill=tk.X, pady=(0, 10))
        
        global_buttons = ttk.Frame(global_controls)
        global_buttons.pack()
        
        ttk.Button(
            global_buttons,
            text="Start All",
            command=self.start_all_bots,
            width=14
        ).pack(side=tk.LEFT, padx=3)
        
        ttk.Button(
            global_buttons,
            text="Stop All",
            command=self.stop_all_bots,
            width=14
        ).pack(side=tk.LEFT, padx=3)
        
        ttk.Button(
            global_buttons,
            text="Debug Info",
            command=self.show_debug_info,
            width=14
        ).pack(side=tk.LEFT, padx=3)
        
        # Combined logs section
        log_frame = ttk.LabelFrame(outer_frame, text="Combined Logs", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=15, 
            state=tk.DISABLED, 
            wrap=tk.WORD, 
            font=("Consolas", 8),
            bg=self.gray_color,
            fg='black',
            insertbackground='black',
            selectbackground=self.navy_color,
            selectforeground=self.gray_color,
            highlightbackground=self.gray_color,
            highlightcolor=self.gray_color,
            highlightthickness=0,
            borderwidth=0,
            relief='flat'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Style the scrollbar
        def style_scrollbar():
            for widget in self.log_text.winfo_children():
                if isinstance(widget, tk.Scrollbar):
                    widget.configure(
                        bg=self.gray_color,
                        troughcolor=self.gray_color,
                        activebackground=self.gray_color,
                        borderwidth=0,
                        highlightthickness=0
                    )
        self.root.after(100, style_scrollbar)
        
        # Start status update timer
        self.update_bot_statuses()
        
        # Start expansion checkbox auto-update timer
        self.update_expansion_checkboxes()
    
    def _create_bot_slot(self, parent: ttk.Frame, slot_id: int) -> ttk.Frame:
        """Create a bot slot widget."""
        slot_frame = ttk.LabelFrame(parent, text=f"Bot {slot_id + 1}", padding="10")
        
        # Main control frame
        main_frame = ttk.Frame(slot_frame)
        main_frame.pack(fill=tk.X)
        
        # Status dot (left side) - using checkmark instead of bullet
        status_dot = ttk.Label(
            main_frame,
            text="✓",
            font=("Arial", 14),
            foreground="gray"
        )
        status_dot.pack(side=tk.LEFT, padx=(0, 8))
        
        # Device input section
        device_frame = ttk.Frame(main_frame)
        device_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        device_label = ttk.Label(device_frame, text="Device:", font=("Arial", 8))
        device_label.pack(side=tk.LEFT, padx=(0, 5))
        
        device_entry = ttk.Entry(device_frame, width=18, font=("Arial", 9))
        device_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Load saved device IP or use default
        saved_device = self.saved_devices.get(slot_id, "127.0.0.1:0000")
        device_entry.insert(0, saved_device)
        
        # Bind to save when user changes the value
        device_entry.bind('<FocusOut>', lambda e, sid=slot_id: self._save_device_ip(sid))
        device_entry.bind('<Return>', lambda e, sid=slot_id: self._save_device_ip(sid))
        
        # Status text (inline with device)
        status_text = ttk.Label(
            main_frame,
            text="Ready",
            font=("Arial", 8),
            foreground="gray"
        )
        status_text.pack(side=tk.LEFT, padx=(5, 0))
        
        # Toggle button (Play/Stop)
        toggle_button = ttk.Button(
            main_frame,
            text="▶",
            command=lambda: self.toggle_slot_bot(slot_id),
            width=3,
            style='Icon.TButton'
        )
        toggle_button.pack(side=tk.RIGHT, padx=(5, 0))
        self._create_tooltip(toggle_button, "Start Bot")
        
        # Store widgets
        self.bot_slots[slot_id] = {
            "frame": slot_frame,
            "device_entry": device_entry,
            "status_dot": status_dot,
            "status_text": status_text,
            "toggle_button": toggle_button
        }
        
        return slot_frame
    
    def _create_expansion_tab(self, parent: ttk.Frame) -> None:
        """Create expansion management tab with per-bot configurations."""
        # Outer padding frame with gray background
        outer_frame = ttk.Frame(parent, padding="10")
        outer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions = ttk.Label(
            outer_frame,
            text="Configure expansion settings for each bot. Check to skip, uncheck to enable.\n"
                 "Each bot maintains its own expansion completion status.",
            justify=tk.LEFT,
            font=("Arial", 9),
            foreground="gray"
        )
        instructions.pack(fill=tk.X, pady=(0, 10))
        
        # Create notebook for bot tabs
        bot_notebook = ttk.Notebook(outer_frame)
        bot_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Store expansion checkboxes per bot (already initialized in __init__)
        
        # Create a tab for each bot
        for slot_id in range(4):
            bot_tab = ttk.Frame(bot_notebook, padding="10")
            bot_notebook.add(bot_tab, text=f"Bot {slot_id + 1}")
            self._create_bot_expansion_tab(bot_tab, slot_id)
    
    def _create_bot_expansion_tab(self, parent: ttk.Frame, slot_id: int) -> None:
        """Create expansion configuration tab for a specific bot."""
        # Main content frame
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollable frame for checkboxes
        canvas_frame = ttk.Frame(content_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(canvas_frame, bg=self.gray_color, highlightthickness=0, highlightbackground=self.gray_color)
        expansion_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        def update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", update_scrollregion)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=expansion_scrollbar.set)
        
        # Update canvas window width when canvas resizes
        def configure_canvas_width(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        canvas.pack(side="left", fill="both", expand=True)
        expansion_scrollbar.pack(side="right", fill="y")
        
        # Load current completed expansions for this bot
        from ..state.persistence import StatePersistence
        state_file = self.settings.paths.get_state_path(self.project_root)
        persistence = StatePersistence(state_file)
        expansion_state = persistence.load_expansions(slot_id=slot_id)
        completed_expansions = expansion_state.completed
        
        # Store checkboxes for this bot
        self.expansion_checkboxes[slot_id] = {}
        
        # Expansion lists (matching battle_bot.py)
        EXPANSIONS_SERIES_A = ["GA", "MI", "STS", "TL", "SR", "CG", "EC", "EG", "WSS", "SS", "DPex"]
        EXPANSIONS_SERIES_B = ["CB", "MR"]
        
        # Series A
        series_a_frame = ttk.LabelFrame(scrollable_frame, text="Series A", padding="8")
        series_a_frame.pack(fill=tk.X, padx=5, pady=5)
        
        series_a_inner = ttk.Frame(series_a_frame)
        series_a_inner.pack(fill=tk.X)
        
        # Create checkboxes using pack to fill horizontal space
        for expansion in EXPANSIONS_SERIES_A:
            expansion_key = f"A_{expansion}"
            var = tk.BooleanVar(value=expansion_key in completed_expansions)
            checkbox = ttk.Checkbutton(
                series_a_inner,
                text=expansion,
                variable=var,
                command=lambda key=expansion_key, v=var, sid=slot_id: self._on_expansion_checkbox_change(key, v, sid)
            )
            checkbox.pack(side=tk.LEFT, padx=10, pady=2)
            self.expansion_checkboxes[slot_id][expansion_key] = var
        
        # Series B
        series_b_frame = ttk.LabelFrame(scrollable_frame, text="Series B", padding="8")
        series_b_frame.pack(fill=tk.X, padx=5, pady=5)
        
        series_b_inner = ttk.Frame(series_b_frame)
        series_b_inner.pack(fill=tk.X)
        
        for expansion in EXPANSIONS_SERIES_B:
            expansion_key = f"B_{expansion}"
            var = tk.BooleanVar(value=expansion_key in completed_expansions)
            checkbox = ttk.Checkbutton(
                series_b_inner,
                text=expansion,
                variable=var,
                command=lambda key=expansion_key, v=var, sid=slot_id: self._on_expansion_checkbox_change(key, v, sid)
            )
            checkbox.pack(side=tk.LEFT, padx=10, pady=2)
            self.expansion_checkboxes[slot_id][expansion_key] = var
        
        # Buttons frame (compact)
        buttons_frame = ttk.Frame(parent)
        buttons_frame.pack(fill=tk.X, pady=(8, 0))
        
        ttk.Button(
            buttons_frame,
            text="Select All",
            command=lambda sid=slot_id: self._select_all_expansions(sid),
            width=12
        ).pack(side=tk.LEFT, padx=3)
        
        ttk.Button(
            buttons_frame,
            text="Deselect All",
            command=lambda sid=slot_id: self._deselect_all_expansions(sid),
            width=12
        ).pack(side=tk.LEFT, padx=3)
        
        ttk.Button(
            buttons_frame,
            text="Refresh",
            command=lambda sid=slot_id: self._reset_expansions_to_current(sid),
            width=12
        ).pack(side=tk.LEFT, padx=3)
    
    def _create_device_tab(self, parent: ttk.Frame) -> None:
        """Create device management tab."""
        # Outer padding frame with gray background
        outer_frame = ttk.Frame(parent, padding="10")
        outer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Current device section (compact)
        current_frame = ttk.LabelFrame(outer_frame, text="Current Device", padding="8")
        current_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.current_device_var = tk.StringVar(value="Not connected")
        device_info_frame = ttk.Frame(current_frame)
        device_info_frame.pack(fill=tk.X)
        ttk.Label(device_info_frame, text="Status:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(device_info_frame, textvariable=self.current_device_var, foreground="red", font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Connect section (compact)
        connect_frame = ttk.LabelFrame(outer_frame, text="Connect to Device", padding="8")
        connect_frame.pack(fill=tk.X, pady=(0, 8))
        
        connect_inner = ttk.Frame(connect_frame)
        connect_inner.pack(fill=tk.X)
        
        ttk.Label(connect_inner, text="Address:", font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 5))
        self.connect_entry = ttk.Entry(connect_inner, width=20)
        self.connect_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.connect_entry.insert(0, "127.0.0.1:5585")
        
        ttk.Button(connect_inner, text="Connect", command=self.connect_device, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(connect_inner, text="Refresh", command=self.refresh_devices, width=12).pack(side=tk.LEFT, padx=2)
        
        # Connected devices list
        devices_frame = ttk.LabelFrame(outer_frame, text="Connected Devices", padding="8")
        devices_frame.pack(fill=tk.BOTH, expand=True)
        
        devices_list_frame = ttk.Frame(devices_frame)
        devices_list_frame.pack(fill=tk.BOTH, expand=True)
        devices_list_frame.columnconfigure(0, weight=1)
        
        ttk.Label(devices_list_frame, text="Select a device to disconnect:", font=("Arial", 8)).pack(anchor=tk.W, pady=(0, 5))
        
        listbox_frame = ttk.Frame(devices_list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        listbox_frame.columnconfigure(0, weight=1)
        
        self.devices_listbox = tk.Listbox(
            listbox_frame, 
            height=8,
            bg=self.gray_color,
            fg='black',
            selectbackground=self.navy_color,
            selectforeground=self.gray_color,
            highlightbackground=self.gray_color,
            highlightcolor=self.gray_color,
            highlightthickness=0,
            borderwidth=0,
            relief='flat'
        )
        self.devices_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.devices_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.devices_listbox.config(yscrollcommand=scrollbar.set)
        
        ttk.Button(
            devices_frame, text="Disconnect Selected", command=self.disconnect_selected, width=18
        ).pack(pady=(8, 0))
    
    
    def _on_expansion_checkbox_change(self, expansion_key: str, var: tk.BooleanVar, slot_id: int) -> None:
        """Handle expansion checkbox change for a specific bot."""
        from ..state.persistence import StatePersistence
        from ..state.models import ExpansionState
        
        state_file = self.settings.paths.get_state_path(self.project_root)
        persistence = StatePersistence(state_file)
        expansion_state = persistence.load_expansions(slot_id=slot_id)
        
        if var.get():
            expansion_state.add_completed(expansion_key)
        else:
            expansion_state.completed.discard(expansion_key)
        
        persistence.save_expansions(expansion_state, slot_id=slot_id)
        logging.info(f"Bot {slot_id + 1}: Expansion {expansion_key} {'marked as completed' if var.get() else 'enabled'}")
    
    def _select_all_expansions(self, slot_id: int) -> None:
        """Select all expansions for a specific bot."""
        from ..state.persistence import StatePersistence
        from ..state.models import ExpansionState
        
        state_file = self.settings.paths.get_state_path(self.project_root)
        persistence = StatePersistence(state_file)
        expansion_state = persistence.load_expansions(slot_id=slot_id)
        
        if slot_id in self.expansion_checkboxes:
            for expansion_key, var in self.expansion_checkboxes[slot_id].items():
                var.set(True)
                expansion_state.add_completed(expansion_key)
        
        persistence.save_expansions(expansion_state, slot_id=slot_id)
        logging.info(f"Bot {slot_id + 1}: All expansions selected")
    
    def _deselect_all_expansions(self, slot_id: int) -> None:
        """Deselect all expansions for a specific bot."""
        from ..state.persistence import StatePersistence
        from ..state.models import ExpansionState
        
        state_file = self.settings.paths.get_state_path(self.project_root)
        persistence = StatePersistence(state_file)
        expansion_state = persistence.load_expansions(slot_id=slot_id)
        
        if slot_id in self.expansion_checkboxes:
            for expansion_key, var in self.expansion_checkboxes[slot_id].items():
                var.set(False)
                expansion_state.completed.discard(expansion_key)
        
        persistence.save_expansions(expansion_state, slot_id=slot_id)
        logging.info(f"Bot {slot_id + 1}: All expansions deselected")
    
    def _reset_expansions_to_current(self, slot_id: int) -> None:
        """Reset checkboxes to current file status for a specific bot."""
        from ..state.persistence import StatePersistence
        
        state_file = self.settings.paths.get_state_path(self.project_root)
        persistence = StatePersistence(state_file)
        expansion_state = persistence.load_expansions(slot_id=slot_id)
        completed_expansions = expansion_state.completed
        
        if slot_id in self.expansion_checkboxes:
            for expansion_key, var in self.expansion_checkboxes[slot_id].items():
                var.set(expansion_key in completed_expansions)
    
    def update_expansion_checkboxes(self) -> None:
        """Update expansion checkboxes to reflect current state from file (auto-check when script completes)."""
        # Stop updating if shutting down
        if hasattr(self, '_shutting_down') and self._shutting_down:
            return
        
        # Guard against calling before expansion_checkboxes is initialized
        if not hasattr(self, 'expansion_checkboxes') or not self.expansion_checkboxes:
            # Schedule next update (every 2 seconds) only if not shutting down
            if not (hasattr(self, '_shutting_down') and self._shutting_down):
                try:
                    self.root.after(2000, self.update_expansion_checkboxes)
                except (tk.TclError, RuntimeError):
                    if hasattr(self, '_shutting_down'):
                        self._shutting_down = True
            return
        
        try:
            from ..state.persistence import StatePersistence
            
            state_file = self.settings.paths.get_state_path(self.project_root)
            persistence = StatePersistence(state_file)
            
            for slot_id in range(4):
                if slot_id in self.expansion_checkboxes:
                    try:
                        expansion_state = persistence.load_expansions(slot_id=slot_id)
                        completed_expansions = expansion_state.completed
                        
                        # Update checkboxes to match current state
                        for expansion_key, var in self.expansion_checkboxes[slot_id].items():
                            try:
                                current_value = expansion_key in completed_expansions
                                if var.get() != current_value:
                                    var.set(current_value)
                            except (tk.TclError, RuntimeError):
                                # Widget may have been destroyed
                                break
                    except (KeyboardInterrupt, SystemExit):
                        # Stop scheduling updates on interrupt
                        if hasattr(self, '_shutting_down'):
                            self._shutting_down = True
                        return
                    except Exception as e:
                        # Log but continue - don't let one slot failure stop updates
                        logging.debug(f"Error updating checkboxes for slot {slot_id}: {e}")
                        continue
        
        except (KeyboardInterrupt, SystemExit):
            # Stop scheduling updates on interrupt
            if hasattr(self, '_shutting_down'):
                self._shutting_down = True
            return
        except Exception as e:
            # Log error but continue - don't crash GUI
            logging.debug(f"Error in update_expansion_checkboxes: {e}")
        
        # Schedule next update (every 2 seconds) only if not shutting down
        if not (hasattr(self, '_shutting_down') and self._shutting_down):
            try:
                self.root.after(2000, self.update_expansion_checkboxes)
            except (tk.TclError, RuntimeError):
                # Root window may have been destroyed
                if hasattr(self, '_shutting_down'):
                    self._shutting_down = True
    
    def _on_closing(self) -> None:
        """Handle window close event gracefully."""
        if self._shutting_down:
            # Already shutting down, force destroy
            try:
                self.root.destroy()
            except:
                pass
            return
        
        self._shutting_down = True
        
        # Stop all bots (non-blocking)
        try:
            if self.multi_bot_manager:
                self.multi_bot_manager.stop_all()
        except Exception as e:
            logging.error(f"Error stopping bots on close: {e}")
        
        # Schedule window destruction after a short delay to allow bots to stop
        # Use after() to ensure it runs in the main thread
        try:
            self.root.after(100, self._force_destroy)
        except:
            # If after() fails, destroy immediately
            try:
                self.root.destroy()
            except:
                pass
    
    def _force_destroy(self) -> None:
        """Force destroy the window."""
        try:
            self.root.quit()
        except:
            pass
        try:
            self.root.destroy()
        except:
            pass
    
    def log_message(self, message: str, level: str = "INFO") -> None:
        """
        Add message to log text widget.

        Args:
            message: Log message.
            level: Log level.
        """
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{level}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def refresh_devices(self) -> None:
        """Refresh connected devices list."""
        devices = DeviceManager.list_devices()
        self.devices_listbox.delete(0, tk.END)

        current_device = self.settings.adb.serial if self.settings else None
        found_current = False

        for device in devices:
            serial = device["serial"]
            state = device["state"]
            display_text = f"{serial} ({state})"
            self.devices_listbox.insert(tk.END, display_text)

            if serial == current_device:
                found_current = True
                self.current_device_var.set(f"{serial} ({state})")
                self.current_device_var.set(f"{serial} ({state})")

        if not found_current and current_device:
            self.current_device_var.set(f"{current_device} (Not connected)")
        elif not found_current:
            self.current_device_var.set("Not connected")

    def auto_refresh_devices(self) -> None:
        """Auto-refresh devices periodically."""
        self.refresh_devices()
        self.root.after(2000, self.auto_refresh_devices)

    def connect_device(self) -> None:
        """Connect to device from entry."""
        serial = self.connect_entry.get().strip()
        if not serial:
            messagebox.showwarning("Input Error", "Please enter a device serial or IP:port")
            return

        if DeviceManager.connect_device(serial):
            # Update config
            self.settings.adb.serial = serial
            # Update current device display
            self.current_device_var.set(f"{serial} (connected)")
            self.refresh_devices()
            messagebox.showinfo("Success", f"Connected to {serial}")
            logging.info(f"Connected to device: {serial}")
        else:
            messagebox.showerror("Connection Error", f"Failed to connect to {serial}")

    def disconnect_selected(self) -> None:
        """Disconnect selected device."""
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select a device to disconnect")
            return

        device_text = self.devices_listbox.get(selection[0])
        serial = device_text.split(" ")[0]  # Extract serial from display text

        if DeviceManager.disconnect_device(serial):
            self.refresh_devices()
            messagebox.showinfo("Success", f"Disconnected from {serial}")
            logging.info(f"Disconnected from device: {serial}")
        else:
            messagebox.showerror("Disconnect Error", f"Failed to disconnect from {serial}")

    def toggle_slot_bot(self, slot_id: int) -> None:
        """Toggle bot start/stop in a specific slot."""
        if slot_id not in self.bot_slots:
            return
        
        widgets = self.bot_slots[slot_id]
        status_info = self.multi_bot_manager.get_bot_status(slot_id) if self.multi_bot_manager else None
        is_running = status_info.get("is_running", False) if status_info else False
        
        if is_running:
            # Stop the bot
            self.stop_slot_bot(slot_id)
        else:
            # Start the bot
            self.start_slot_bot(slot_id)
    
    def start_slot_bot(self, slot_id: int) -> None:
        """Start a bot in a specific slot."""
        if slot_id not in self.bot_slots:
            return
        
        widgets = self.bot_slots[slot_id]
        device_serial = widgets["device_entry"].get().strip()
        
        if not device_serial:
            messagebox.showwarning("Input Error", f"Please enter a device IP:Port for Bot {slot_id + 1}")
            return
        
        # Update UI - switch to stop button
        widgets["toggle_button"].config(text="■", state=tk.DISABLED)
        self._create_tooltip(widgets["toggle_button"], "Stop Bot")
        widgets["status_text"].config(text="Connecting...", foreground="blue")
        widgets["status_dot"].config(foreground="orange")
        
        def start_in_thread():
            try:
                # Create bot instance
                if not self.multi_bot_manager.create_bot(slot_id, device_serial):
                    self.root.after(0, lambda: widgets["status_text"].config(
                        text="Creation Failed", foreground="red"
                    ))
                    self.root.after(0, lambda: widgets["toggle_button"].config(text="▶", state=tk.NORMAL))
                    self.root.after(0, lambda: self._create_tooltip(widgets["toggle_button"], "Start Bot"))
                    self.root.after(0, lambda: widgets["status_dot"].config(foreground="red"))
                    return
                
                # Start bot
                if self.multi_bot_manager.start_bot(slot_id):
                    self.root.after(0, lambda: widgets["status_text"].config(
                        text="Running", foreground="green"
                    ))
                    self.root.after(0, lambda: widgets["toggle_button"].config(text="■", state=tk.NORMAL))
                    self.root.after(0, lambda: self._create_tooltip(widgets["toggle_button"], "Stop Bot"))
                    self.root.after(0, lambda: widgets["status_dot"].config(foreground="green"))
                    logging.info(f"Bot {slot_id + 1} started successfully on {device_serial}")
                else:
                    status_info = self.multi_bot_manager.get_bot_status(slot_id)
                    error_msg = status_info.get("error_message", "Unknown error") if status_info else "Failed to start"
                    status = status_info.get("status", "Failed") if status_info else "Failed"
                    self.root.after(0, lambda: widgets["status_text"].config(
                        text=status, foreground="red"
                    ))
                    self.root.after(0, lambda: widgets["toggle_button"].config(text="▶", state=tk.NORMAL))
                    self.root.after(0, lambda: self._create_tooltip(widgets["toggle_button"], "Start Bot"))
                    self.root.after(0, lambda: widgets["status_dot"].config(foreground="red"))
                    logging.error(f"Bot {slot_id + 1} failed to start: {error_msg}")
            except Exception as e:
                error_msg = f"Error starting bot {slot_id + 1}: {e}"
                logging.error(error_msg, exc_info=True)
                self.root.after(0, lambda: widgets["status_text"].config(
                    text="Error", foreground="red"
                ))
                self.root.after(0, lambda: widgets["toggle_button"].config(text="▶", state=tk.NORMAL))
                self.root.after(0, lambda: self._create_tooltip(widgets["toggle_button"], "Start Bot"))
                self.root.after(0, lambda: widgets["status_dot"].config(foreground="red"))
        
        threading.Thread(target=start_in_thread, daemon=True).start()
    
    def stop_slot_bot(self, slot_id: int) -> None:
        """Stop a bot in a specific slot (completely removes and restarts the bot instance)."""
        if slot_id not in self.bot_slots:
            return
        
        widgets = self.bot_slots[slot_id]
        # Update UI - switch to start button
        widgets["toggle_button"].config(text="▶", state=tk.DISABLED)
        self._create_tooltip(widgets["toggle_button"], "Start Bot")
        widgets["status_text"].config(text="Stopping...", foreground="orange")
        widgets["status_dot"].config(foreground="orange")
        
        # Run removal in background thread to avoid freezing GUI
        def remove_in_thread():
            try:
                if self.multi_bot_manager and self.multi_bot_manager.has_bot(slot_id):
                    self.multi_bot_manager.remove_bot(slot_id)
                    logging.info(f"Bot {slot_id + 1} stopped and removed successfully")
                else:
                    logging.debug(f"Bot {slot_id + 1} was not running, no removal needed")
                
                # Update UI on main thread after removal completes
                self.root.after_idle(lambda: self._update_slot_to_stopped(slot_id))
            except Exception as e:
                logging.error(f"Error stopping bot {slot_id + 1}: {e}", exc_info=True)
                # Update UI on main thread even if there was an error
                self.root.after_idle(lambda: self._update_slot_to_stopped_error(slot_id))
        
        # Start removal in background thread
        threading.Thread(target=remove_in_thread, daemon=True).start()
    
    def _update_slot_to_stopped(self, slot_id: int) -> None:
        """Helper to update slot UI to stopped state after successful stop."""
        if slot_id in self.bot_slots:
            widgets = self.bot_slots[slot_id]
            widgets["status_text"].config(text="Stopped", foreground="gray")
            widgets["status_dot"].config(foreground="gray")
            widgets["toggle_button"].config(text="▶", state=tk.NORMAL)
            self._create_tooltip(widgets["toggle_button"], "Start Bot")
    
    def _update_slot_to_stopped_error(self, slot_id: int) -> None:
        """Helper to update slot UI after error during stop."""
        if slot_id in self.bot_slots:
            widgets = self.bot_slots[slot_id]
            widgets["status_text"].config(text="Error stopping", foreground="red")
            widgets["status_dot"].config(foreground="red")
            # After a delay, show as stopped anyway
            self.root.after(2000, lambda: self._update_slot_to_stopped(slot_id))
    
    def _update_slot_to_stopped(self, slot_id: int) -> None:
        """Helper to update slot UI to stopped state."""
        if slot_id in self.bot_slots:
            widgets = self.bot_slots[slot_id]
            widgets["status_text"].config(text="Stopped", foreground="gray")
            widgets["status_dot"].config(foreground="gray")
            widgets["toggle_button"].config(text="▶", state=tk.NORMAL)
            self._create_tooltip(widgets["toggle_button"], "Start Bot")
    
    
    def start_all_bots(self) -> None:
        """Start all configured bots (only bots with valid device IPs)."""
        # Collect bots to start
        bots_to_start = []
        for slot_id in range(4):
            if slot_id in self.bot_slots:
                widgets = self.bot_slots[slot_id]
                device_serial = widgets["device_entry"].get().strip()
                # Skip if no device configured or device is default/empty
                if not device_serial or device_serial == "127.0.0.1:0000" or device_serial == "":
                    continue
                # Check if bot needs to be started
                if not self.multi_bot_manager.has_bot(slot_id):
                    bots_to_start.append(slot_id)
                elif self.multi_bot_manager.has_bot(slot_id):
                    status_info = self.multi_bot_manager.get_bot_status(slot_id)
                    if status_info and not status_info.get("is_running", False):
                        bots_to_start.append(slot_id)
        
        # Start bots with staggered delays to avoid ADB conflicts
        def start_bots_staggered():
            import time
            for i, slot_id in enumerate(bots_to_start):
                # Add delay between starts to avoid ADB conflicts
                if i > 0:
                    time.sleep(0.5)  # 500ms delay between bot starts
                self.start_slot_bot(slot_id)
        
        # Run in background thread to avoid blocking GUI
        if bots_to_start:
            threading.Thread(target=start_bots_staggered, daemon=True).start()
    
    def stop_all_bots(self) -> None:
        """Stop all running bots (completely removes and restarts all bot instances)."""
        # Run stop operations in background thread to avoid lag
        def stop_all_in_thread():
            try:
                # Stop all bots
                if self.multi_bot_manager:
                    self.multi_bot_manager.stop_all()
                
                # Remove all bots completely
                for slot_id in range(4):
                    if slot_id in self.bot_slots:
                        if self.multi_bot_manager and self.multi_bot_manager.has_bot(slot_id):
                            try:
                                self.multi_bot_manager.remove_bot(slot_id)
                            except Exception as e:
                                logging.error(f"Error removing bot {slot_id + 1}: {e}")
                        
                        # Update UI on main thread
                        widgets = self.bot_slots[slot_id]
                        self.root.after_idle(lambda sid=slot_id, w=widgets: self._update_slot_to_stopped(sid))
                
                logging.info("All bots stopped and removed")
            except Exception as e:
                logging.error(f"Error stopping all bots: {e}", exc_info=True)
        
        # Start in background thread
        threading.Thread(target=stop_all_in_thread, daemon=True).start()
    
    def update_bot_statuses(self) -> None:
        """Update status displays for all bot slots."""
        # Stop updating if shutting down
        if hasattr(self, '_shutting_down') and self._shutting_down:
            return
            
        if not self.multi_bot_manager:
            return
        
        try:
            for slot_id in range(4):
                if slot_id in self.bot_slots:
                    widgets = self.bot_slots[slot_id]
                    status_info = self.multi_bot_manager.get_bot_status(slot_id)
                    
                    if status_info:
                        is_running = status_info.get("is_running", False)
                        status = status_info.get("status", "Unknown")
                        # Only check connection if bot is running to avoid blocking
                        is_connected = status_info.get("is_connected", False) if is_running else False
                        
                        # Update status text
                        widgets["status_text"].config(
                            text=status,
                            foreground="green" if is_running else ("red" if "Error" in status or "Failed" in status else "blue")
                        )
                        
                        # Update status dot
                        widgets["status_dot"].config(
                            foreground="green" if is_connected else ("orange" if "Connecting" in status or "Stopping" in status else "red")
                        )
                        
                        # Update toggle button
                        if is_running:
                            widgets["toggle_button"].config(text="■", state=tk.NORMAL)
                            self._create_tooltip(widgets["toggle_button"], "Stop Bot")
                        else:
                            widgets["toggle_button"].config(text="▶", state=tk.NORMAL)
                            self._create_tooltip(widgets["toggle_button"], "Start Bot")
                    else:
                        # No bot in slot - show as stopped
                        # Don't test connection here to avoid blocking - just show gray
                        widgets["status_dot"].config(foreground="gray")
                        widgets["status_text"].config(
                            text="Stopped",
                            foreground="gray"
                        )
                        # Ensure toggle button shows start state when no bot
                        widgets["toggle_button"].config(text="▶", state=tk.NORMAL)
                        self._create_tooltip(widgets["toggle_button"], "Start Bot")
        except (tk.TclError, RuntimeError, AttributeError):
            # Window may have been destroyed or widgets don't exist
            if hasattr(self, '_shutting_down'):
                self._shutting_down = True
            return
        except Exception as e:
            # Log but don't crash GUI
            logging.debug(f"Error updating bot statuses: {e}")
        
        # Schedule next update only if not shutting down
        if not (hasattr(self, '_shutting_down') and self._shutting_down):
            try:
                self.root.after(2000, self.update_bot_statuses)
            except (tk.TclError, RuntimeError):
                # Window may have been destroyed
                if hasattr(self, '_shutting_down'):
                    self._shutting_down = True
        
        # Also update expansion checkboxes periodically (but less frequently to reduce load)
        # Expansion checkboxes have their own schedule, so we don't need to call it here every time
    
    def start_bot(self) -> None:
        """Start the bot (legacy method for backward compatibility)."""
        # Run bot start in a thread to prevent GUI blocking
        # But keep GUI updates in main thread
        def start_in_thread():
            try:
                self._start_bot_impl()
            except Exception as e:
                error_msg = f"Error starting bot: {e}\n{traceback.format_exc()}"
                logging.error(error_msg, exc_info=True)
                log_to_file(error_msg)
                self.root.after_idle(lambda: self._show_error("Start Error", str(e)))
                self.root.after_idle(self.bot_stopped)
        
        threading.Thread(target=start_in_thread, daemon=True).start()
    
    def _start_bot_impl(self) -> None:
        """Internal bot start implementation."""
        if self.bot_running:
            messagebox.showwarning("Bot Running", "Bot is already running")
            return

        # Check device connection
        current_serial = self.settings.adb.serial
        if not current_serial or current_serial == "Not connected":
            messagebox.showerror(
                "Device Error",
                "No device selected. Please connect to a device first."
            )
            return
        
        # Test connection with timeout
        try:
            # For network devices (IP:port format), connect first
            if ":" in current_serial and not current_serial.startswith("emulator-"):
                logging.info(f"Connecting to network device {current_serial}")
                DeviceManager.connect_device(current_serial)

            if not DeviceManager.test_connection(current_serial):
                messagebox.showerror(
                    "Device Error",
                    f"Cannot connect to device: {current_serial}\n"
                    "Please ensure the device is connected and ADB is working.",
                )
                return
        except Exception as e:
            error_msg = f"Error testing device connection: {e}"
            logging.error(error_msg)
            messagebox.showerror("Device Error", error_msg)
            return

        # Verify templates exist before starting
        template_dir = self.settings.paths.get_template_path(self.project_root) / "battle"
        if not template_dir.exists():
            error_msg = (
                f"Template directory not found: {template_dir}\n\n"
                "Please ensure templates are in the correct location."
            )
            messagebox.showerror("Template Error", error_msg)
            logging.error(error_msg)
            log_to_file(error_msg)
            return

        # Update UI first to show we're starting (non-blocking)
        # Legacy UI elements may not exist in new multi-bot interface
        if hasattr(self, 'start_button'):
            self.root.after(0, lambda: self.start_button.config(state=tk.DISABLED))
        if hasattr(self, 'status_var'):
            self.root.after(0, lambda: self.status_var.set("Initializing bot..."))
        self.root.update_idletasks()  # Non-blocking update

        # Initialize bot in a try-except to catch initialization errors
        try:
            logging.info(f"Initializing bot with device: {self.settings.adb.serial}")
            logging.info(f"Project root: {self.project_root}")
            logging.info(f"Template dir: {template_dir}")
            
            self.bot = BattleBot(self.settings, self.project_root)
            
        except Exception as init_error:
            self.bot_running = False
            error_msg = f"Failed to initialize bot: {init_error}\n\n{traceback.format_exc()}"
            logging.error(error_msg, exc_info=True)
            log_to_file(error_msg)
            
            # Reset UI (non-blocking)
            if hasattr(self, 'start_button'):
                self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            if hasattr(self, 'status_var'):
                self.root.after(0, lambda: self.status_var.set("Initialization Failed"))
            
            # Show error (non-blocking)
            self.root.after(0, lambda: messagebox.showerror(
                "Initialization Error", 
                f"Failed to initialize bot:\n{init_error}\n\nCheck Debug Info for details."
            ))
            
            # Show debug window (non-blocking)
            self.root.after(100, lambda: safe_call(self._show_debug_window, init_error))
            return

        # If initialization succeeded, start bot thread
        self.bot_running = True
        if hasattr(self, 'stop_button'):
            self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))
        if hasattr(self, 'status_var'):
            self.root.after(0, lambda: self.status_var.set("Bot Starting..."))
        self.root.update_idletasks()

        # Start bot in separate thread with explicit error handling
        self.bot_thread = threading.Thread(
            target=self._safe_run_bot, 
            daemon=True,
            name="BotThread"
        )
        self.bot_thread.start()
        
        logging.info("Bot thread started")
    
    def _safe_run_bot(self) -> None:
        """Safely run bot with comprehensive error handling."""
        try:
            self.run_bot()
        except Exception as e:
            error_msg = f"Critical error in bot thread: {e}\n{traceback.format_exc()}"
            logging.critical(error_msg, exc_info=True)
            log_to_file(error_msg)
            
            # Try to show error in GUI (non-blocking)
            try:
                self.root.after_idle(lambda: self._show_error("Critical Bot Error", str(e)))
            except:
                pass
    
    def _show_debug_window(self, exception: Exception) -> None:
        """Show debug window with exception."""
        try:
            debug_window = DebugWindow(self.root)
            debug_window.show_exception(exception)
            debug_window.show_system_info()
        except Exception as e:
            logging.error(f"Failed to show debug window: {e}")

    def run_bot(self) -> None:
        """Run bot in separate thread."""
        import traceback
        
        try:
            logging.info("Bot thread started")
            
            # Add a small delay to ensure GUI is responsive
            import time
            time.sleep(0.1)
            
            if not self.bot:
                error_msg = "Bot instance is None"
                logging.error(error_msg)
                self.root.after(0, lambda: self._show_error("Bot Error", error_msg))
                self.bot_running = False
                self.root.after(0, self.bot_stopped)
                return
            
            logging.info(f"Starting bot with device: {self.settings.adb.serial}")
            
            # Run bot - this should not block GUI
            self.bot.run()
            
        except KeyboardInterrupt:
            logging.info("Bot interrupted by user")
        except Exception as e:
            error_msg = f"Bot crashed: {str(e)}"
            traceback_str = traceback.format_exc()
            logging.error(f"{error_msg}\n{traceback_str}", exc_info=True)
            
            # Show error in GUI (use after_idle to ensure GUI is responsive)
            self.root.after_idle(lambda: self._show_error("Bot Crashed", f"{error_msg}\n\n{traceback_str[:500]}..."))
        finally:
            self.bot_running = False
            # Use after_idle to ensure GUI thread processes this
            self.root.after_idle(self.bot_stopped)
    
    def _show_error(self, title: str, message: str) -> None:
        """Safely show error message."""
        try:
            messagebox.showerror(title, message)
        except Exception as e:
            # Fallback: print to console if GUI fails
            print(f"ERROR [{title}]: {message}")
            print(f"GUI Error handler failed: {e}")

    def bot_stopped(self) -> None:
        """Called when bot stops."""
        if hasattr(self, 'start_button'):
            self.start_button.config(state=tk.NORMAL)
        if hasattr(self, 'stop_button'):
            self.stop_button.config(state=tk.DISABLED)
        if hasattr(self, 'status_var'):
            self.status_var.set("Bot Stopped")
        logging.info("Bot stopped")

    def stop_bot(self) -> None:
        """Stop the bot."""
        if not self.bot_running:
            return

        self.bot_running = False
        if hasattr(self, 'status_var'):
            self.status_var.set("Stopping bot...")
        logging.info("Stopping bot...")
        
        # Stop the bot
        if self.bot:
            try:
                self.bot.stop()
            except Exception as e:
                logging.error(f"Error stopping bot: {e}")
        
        # Update UI immediately
        self.bot_stopped()

    def show_debug_info(self) -> None:
        """Show debug information window."""
        debug_window = DebugWindow(self.root)
        debug_window.show_system_info()
        
        # Add configuration info
        if self.settings:
            config_info = f"""
ADB Serial: {self.settings.adb.serial}
Template Path: {self.settings.paths.templates}
Log Path: {self.settings.paths.logs}
State Path: {self.settings.paths.state}
Project Root: {self.project_root}
            """
            debug_window.add_info("Configuration", config_info)
        
        # Check template directory
        if self.settings:
            template_dir = self.settings.paths.get_template_path(self.project_root) / "battle"
            template_info = f"""
Template Directory: {template_dir}
Exists: {template_dir.exists()}
            """
            if template_dir.exists():
                template_files = list(template_dir.rglob("*.png"))
                template_info += f"\nTemplate Files Found: {len(template_files)}"
            debug_window.add_info("Templates", template_info)
        
        # Check ADB
        try:
            devices = DeviceManager.list_devices()
            adb_info = f"""
ADB Devices: {len(devices)}
Devices: {devices}
            """
            debug_window.add_info("ADB Status", adb_info)
        except Exception as e:
            debug_window.add_info("ADB Status", f"Error: {e}")
        
        # Check bot status
        bot_info = f"""
Bot Running: {self.bot_running}
Bot Instance: {self.bot is not None}
Bot Thread: {self.bot_thread is not None if self.bot_thread else None}
            """
        debug_window.add_info("Bot Status", bot_info)

    def _load_saved_devices(self) -> Dict[int, str]:
        """Load saved device IPs from file."""
        import json
        if self.devices_file.exists():
            try:
                with open(self.devices_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    data = json.loads(content)
                    # Convert string keys to int keys
                    return {int(k): v for k, v in data.get("devices", {}).items()}
            except Exception as e:
                logging.warning(f"Error loading saved devices: {e}")
                return {}
        return {}
    
    def _save_device_ip(self, slot_id: int) -> None:
        """Save device IP for a specific slot."""
        if slot_id not in self.bot_slots:
            return
        
        import json
        widgets = self.bot_slots[slot_id]
        device_serial = widgets["device_entry"].get().strip()
        
        # Update saved devices
        self.saved_devices[slot_id] = device_serial
        
        # Save to file
        try:
            # Load existing data if file exists
            existing_data = {}
            if self.devices_file.exists():
                try:
                    with open(self.devices_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            existing_data = json.loads(content)
                except Exception:
                    pass
            
            # Update devices
            existing_data["devices"] = {str(k): v for k, v in self.saved_devices.items()}
            
            # Save to file
            with open(self.devices_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2)
            
            logging.debug(f"Saved device IP for slot {slot_id}: {device_serial}")
        except Exception as e:
            logging.warning(f"Error saving device IP: {e}")

    def _create_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Create a tooltip for a widget."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            
            label = tk.Label(
                tooltip,
                text=text,
                background=self.navy_color,
                foreground=self.gray_color,
                relief=tk.SOLID,
                borderwidth=1,
                font=("Arial", 9),
                justify=tk.LEFT,
                padx=5,
                pady=5
            )
            label.pack()
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def show_expansion_manager(self) -> None:
        """Show expansion management (switch to expansions tab)."""
        # Switch to expansions tab (index 1)
        self.notebook.select(1)

    def take_screenshot(self) -> None:
        """Take a screenshot from the first connected device."""
        try:
            # Try to find a connected bot first
            device_serial = None
            for slot_id in range(4):
                status_info = self.multi_bot_manager.get_bot_status(slot_id)
                if status_info and status_info.get("is_connected", False):
                    device_serial = status_info.get("device_serial")
                    break
            
            # Fallback to first slot's device entry
            if not device_serial and 0 in self.bot_slots:
                device_serial = self.bot_slots[0]["device_entry"].get().strip()
            
            # Fallback to settings
            if not device_serial:
                device_serial = self.settings.adb.serial
            
            if not device_serial or device_serial == "Not connected":
                messagebox.showerror(
                    "Device Error",
                    "No device connected. Please configure a bot with a device IP:Port first."
                )
                return
            
            # For network devices (IP:port format), connect first
            if ":" in device_serial and not device_serial.startswith("emulator-"):
                logging.info(f"Connecting to network device {device_serial}")
                DeviceManager.connect_device(device_serial)

            # Test connection
            if not DeviceManager.test_connection(device_serial):
                messagebox.showerror(
                    "Connection Error",
                    f"Cannot connect to device: {device_serial}\n"
                    "Please ensure the device is connected and ADB is working."
                )
                return
            
            # Create ADB client for screenshot
            from ..config.settings import ADBConfig
            adb_config = ADBConfig(serial=device_serial, command_timeout=self.settings.adb.command_timeout)
            adb_client = ADBClient(adb_config)
            
            # Take screenshot
            screenshot_path = self.project_root / "screen.png"
            screenshot_capture = ScreenshotCapture(adb_client)
            
            logging.info(f"Taking screenshot from {device_serial}...")
            
            if screenshot_capture.save_screenshot(str(screenshot_path)):
                logging.info(f"Screenshot saved to {screenshot_path}")
                messagebox.showinfo(
                    "Success",
                    f"Screenshot saved successfully!\n\n{screenshot_path}"
                )
            else:
                raise Exception("Failed to capture screenshot")
                
        except Exception as e:
            error_msg = f"Failed to take screenshot: {e}"
            logging.error(error_msg, exc_info=True)
            messagebox.showerror("Error", error_msg)


class GUILogHandler(logging.Handler):
    """Custom log handler for GUI with batching to reduce load."""

    def __init__(self, gui_app: AutoGodPackGUI):
        """
        Initialize GUI log handler.

        Args:
            gui_app: GUI application instance.
        """
        super().__init__()
        self.gui_app = gui_app
        self.log_queue = []
        self.batch_size = 10  # Batch logs before updating GUI
        self.max_queue_size = 500  # Limit queue size to prevent memory issues
        self.update_scheduled = False

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit log record to GUI (batched for performance).

        Args:
            record: Log record.
        """
        try:
            # Stop accepting logs if shutting down
            if hasattr(self.gui_app, '_shutting_down') and self.gui_app._shutting_down:
                return
                
            msg = self.format(record)
            level = record.levelname
            
            # Limit queue size to prevent memory issues during long runs
            if len(self.log_queue) >= self.max_queue_size:
                # Remove oldest entries (keep most recent)
                self.log_queue = self.log_queue[-self.max_queue_size//2:]
                # Add a warning that logs were dropped
                self.log_queue.insert(0, ("[WARNING] Log queue full, some logs were dropped", "WARNING"))
            
            # Add to queue
            self.log_queue.append((msg, level))
            
            # Schedule batch update if not already scheduled
            if not self.update_scheduled:
                self.update_scheduled = True
                # Use after() with small delay instead of after_idle to prevent callback queue buildup
                # This gives the GUI time to process other events between log batches
                try:
                    self.gui_app.root.after(50, self._flush_logs)
                except (tk.TclError, RuntimeError, AttributeError):
                    self.update_scheduled = False
        except Exception:
            pass  # Ignore errors in logging
    
    def _flush_logs(self) -> None:
        """Flush batched logs to GUI."""
        try:
            # Stop if shutting down
            if hasattr(self.gui_app, '_shutting_down') and self.gui_app._shutting_down:
                self.update_scheduled = False
                self.log_queue.clear()
                return
            
            if not self.log_queue:
                self.update_scheduled = False
                return
            
            # Process batch (limit to prevent GUI freeze)
            batch = self.log_queue[:self.batch_size]
            self.log_queue = self.log_queue[self.batch_size:]
            
            # Update GUI with batch
            if batch:
                self.gui_app.log_text.config(state=tk.NORMAL)
                for msg, level in batch:
                    self.gui_app.log_text.insert(tk.END, f"[{level}] {msg}\n")
                self.gui_app.log_text.see(tk.END)
                # Limit log size to prevent memory issues (keep last 1000 lines)
                lines = int(self.gui_app.log_text.index('end-1c').split('.')[0])
                if lines > 1000:
                    self.gui_app.log_text.delete('1.0', f'{lines - 1000}.0')
                self.gui_app.log_text.config(state=tk.DISABLED)
            
            # Schedule next batch if queue not empty and not shutting down
            # Use after() with delay instead of after_idle to prevent callback queue buildup
            if self.log_queue and not (hasattr(self.gui_app, '_shutting_down') and self.gui_app._shutting_down):
                try:
                    self.gui_app.root.after(50, self._flush_logs)
                except (tk.TclError, RuntimeError, AttributeError):
                    self.update_scheduled = False
            else:
                self.update_scheduled = False
        except (tk.TclError, RuntimeError, AttributeError):
            # Window may have been destroyed
            self.update_scheduled = False
        except Exception:
            self.update_scheduled = False


def main() -> None:
    """Launch GUI application."""
    import signal
    import threading
    
    # Global shutdown flag and lock to prevent multiple shutdown attempts
    _shutdown_lock = threading.Lock()
    _shutdown_initiated = False
    
    # Setup exception handler for uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Allow KeyboardInterrupt to propagate normally for clean shutdown
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.critical(f"Uncaught exception: {error_msg}")
        
        # Try to show error in GUI if possible
        try:
            import tkinter.messagebox as mb
            mb.showerror("Critical Error", f"Uncaught exception:\n{exc_value}\n\nCheck logs for details.")
        except:
            pass
    
    sys.excepthook = handle_exception
    
    root = tk.Tk()
    app_instance = None
    
    def initiate_shutdown():
        """Initiate shutdown process from main thread."""
        nonlocal _shutdown_initiated
        
        with _shutdown_lock:
            if _shutdown_initiated:
                return
            _shutdown_initiated = True
        
        logging.info("Initiating shutdown...")
        
        if app_instance:
            app_instance._shutting_down = True
            try:
                if app_instance.multi_bot_manager:
                    app_instance.multi_bot_manager.stop_all()
            except Exception as e:
                logging.error(f"Error stopping bots during shutdown: {e}")
        
        # Schedule window destruction with timeout
        def force_quit():
            """Force quit after timeout."""
            try:
                logging.warning("Forcing application exit after timeout")
                root.quit()
                root.destroy()
            except:
                pass
            # Force exit if still running
            import os
            try:
                os._exit(0)
            except:
                pass
        
        # Give bots 3 seconds to stop, then force quit
        try:
            root.after(3000, force_quit)
        except:
            force_quit()
        
        # Try graceful shutdown
        def graceful_quit():
            """Attempt graceful quit."""
            try:
                root.quit()
            except (tk.TclError, AttributeError, RuntimeError):
                pass
        
        try:
            root.after(100, graceful_quit)
        except (tk.TclError, AttributeError, RuntimeError):
            pass
    
    # Setup signal handler for graceful shutdown (Windows compatible)
    def signal_handler(signum=None, frame=None):
        """Handle SIGINT (Ctrl+C) gracefully."""
        # On Windows, signal handlers run in a different thread
        # Use root.after() to schedule shutdown in main thread
        try:
            # Try to schedule shutdown in main thread
            root.after(0, initiate_shutdown)
        except (tk.TclError, AttributeError, RuntimeError):
            # If root doesn't exist or after() fails, try direct shutdown
            initiate_shutdown()
    
    # Register signal handler for Ctrl+C (if available on platform)
    try:
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)
    except (ValueError, OSError):
        # Signal handling not available on this platform (e.g., Windows main thread)
        pass
    
    try:
        app_instance = AutoGodPackGUI(root)
        
        # Wrap mainloop to catch KeyboardInterrupt
        try:
            root.mainloop()
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received in mainloop, shutting down...")
            initiate_shutdown()
            # Wait a moment for shutdown to process
            try:
                root.update()
            except:
                pass
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, shutting down...")
        initiate_shutdown()
    except Exception as e:
        logging.critical(f"Failed to start GUI: {e}", exc_info=True)
        try:
            import tkinter.messagebox as mb
            mb.showerror("Startup Error", f"Failed to start GUI:\n{e}\n\nCheck logs for details.")
        except:
            pass
    finally:
        # Final cleanup - force exit if needed
        with _shutdown_lock:
            if not _shutdown_initiated:
                initiate_shutdown()
        
        # Give a moment for cleanup, then force exit
        import time
        time.sleep(0.5)
        
        try:
            root.quit()
            root.destroy()
        except (tk.TclError, AttributeError, RuntimeError):
            pass
        
        # Force exit if still running (last resort)
        import os
        try:
            os._exit(0)
        except:
            pass


if __name__ == "__main__":
    main()

