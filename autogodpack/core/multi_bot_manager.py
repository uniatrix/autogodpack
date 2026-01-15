"""Multi-bot manager for handling multiple battle bot instances."""

import logging
import threading
from typing import Dict, Optional, List
from pathlib import Path

from ..config.settings import Settings, ADBConfig
from ..adb.device_manager import DeviceManager
from .bot import BattleBot


class BotInstance:
    """Represents a single bot instance with its state."""
    
    def __init__(self, slot_id: int, device_serial: str, settings: Settings, project_root: Path):
        """
        Initialize bot instance.
        
        Args:
            slot_id: Slot identifier (0-3).
            device_serial: Device serial/IP to connect to.
            settings: Base settings (will be cloned and modified).
            project_root: Project root directory.
        """
        self.slot_id = slot_id
        self.device_serial = device_serial
        self.settings = self._create_settings_for_device(settings, device_serial)
        self.project_root = project_root
        
        self.bot: Optional[BattleBot] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.status = "Ready"
        self.error_message: Optional[str] = None
        
    def _create_settings_for_device(self, base_settings: Settings, serial: str) -> Settings:
        """Create a settings copy with device-specific ADB config."""
        from copy import deepcopy
        from ..config.settings import (
            ADBConfig, AutomationConfig, MatchingConfig, ScreenConfig,
            BattleConfig, ExpansionConfig, PathsConfig, LoggingConfig
        )
        
        # Deep copy settings
        new_settings = deepcopy(base_settings)
        
        # Override ADB config with device-specific serial
        new_settings.adb = ADBConfig(
            serial=serial,
            command_timeout=base_settings.adb.command_timeout
        )
        
        return new_settings
    
    def start(self) -> bool:
        """Start the bot instance."""
        if self.is_running:
            logger.warning(f"Bot {self.slot_id} is already running")
            return False
        
        # Test device connection
        if not DeviceManager.test_connection(self.device_serial):
            self.status = "Connection Failed"
            self.error_message = f"Cannot connect to device: {self.device_serial}"
            logging.error(f"[Bot {self.slot_id + 1}] {self.error_message}")
            return False
        
        # Verify templates exist
        template_dir = self.settings.paths.get_template_path(self.project_root) / "battle"
        if not template_dir.exists():
            self.status = "Template Error"
            self.error_message = f"Template directory not found: {template_dir}"
            logging.error(f"[Bot {self.slot_id + 1}] {self.error_message}")
            return False
        
        try:
            # Initialize bot
            self.status = "Initializing..."
            self.error_message = None
            logging.info(f"[Bot {self.slot_id + 1}] Initializing with device {self.device_serial}")
            
            self.bot = BattleBot(self.settings, self.project_root, slot_id=self.slot_id)
            
            # Start bot in separate thread
            self.is_running = True
            self.status = "Starting..."
            
            self.bot_thread = threading.Thread(
                target=self._run_bot,
                daemon=True,
                name=f"BotThread-{self.slot_id}"
            )
            self.bot_thread.start()
            
            logging.info(f"[Bot {self.slot_id + 1}] Started successfully")
            return True
            
        except Exception as e:
            self.is_running = False
            self.status = "Initialization Failed"
            self.error_message = str(e)
            logging.error(f"[Bot {self.slot_id + 1}] Failed to initialize: {e}", exc_info=True)
            return False
    
    def _run_bot(self) -> None:
        """Run bot in thread."""
        try:
            self.status = "Running"
            logging.info(f"[Bot {self.slot_id + 1}] Running battle cycles on {self.device_serial}")
            self.bot.run()
        except Exception as e:
            self.status = "Error"
            self.error_message = str(e)
            logging.error(f"[Bot {self.slot_id + 1}] Error during execution: {e}", exc_info=True)
        except KeyboardInterrupt:
            logging.info(f"[Bot {self.slot_id + 1}] Interrupted by user")
            self.status = "Stopped"
        finally:
            # Ensure we mark as stopped even if there was an error
            self.is_running = False
            if self.status != "Error":
                self.status = "Stopped"
            logging.info(f"[Bot {self.slot_id + 1}] Bot thread finished")
    
    def stop(self) -> None:
        """Stop the bot instance."""
        if not self.is_running and not (self.bot and hasattr(self.bot, '_stop_flag')):
            return
        
        self.status = "Stopping..."
        self.is_running = False
        
        if self.bot:
            try:
                self.bot.stop()
                logging.info(f"[Bot {self.slot_id + 1}] Stop requested")
            except Exception as e:
                logging.error(f"[Bot {self.slot_id + 1}] Error stopping bot: {e}", exc_info=True)
                # Still mark as stopped even if stop() failed
                self.status = "Stopped"
    
    def get_status_info(self) -> Dict[str, any]:
        """Get current status information."""
        return {
            "slot_id": self.slot_id,
            "device_serial": self.device_serial,
            "is_running": self.is_running,
            "status": self.status,
            "error_message": self.error_message,
            "is_connected": DeviceManager.test_connection(self.device_serial) if self.device_serial else False
        }


class MultiBotManager:
    """Manages multiple battle bot instances (up to 4)."""
    
    MAX_BOTS = 4
    
    def __init__(self, base_settings: Settings, project_root: Path):
        """
        Initialize multi-bot manager.
        
        Args:
            base_settings: Base settings to use for all bots.
            project_root: Project root directory.
        """
        self.base_settings = base_settings
        self.project_root = project_root
        self.bots: Dict[int, BotInstance] = {}
        
    def create_bot(self, slot_id: int, device_serial: str) -> bool:
        """
        Create a bot instance in a slot.
        
        Args:
            slot_id: Slot identifier (0-3).
            device_serial: Device serial/IP to connect to.
        
        Returns:
            True if bot was created successfully.
        """
        if slot_id < 0 or slot_id >= self.MAX_BOTS:
            logging.error(f"Invalid slot_id: {slot_id}. Must be 0-{self.MAX_BOTS-1}")
            return False
        
        if not device_serial or not device_serial.strip():
            logging.error(f"Invalid device_serial for slot {slot_id}")
            return False
        
        device_serial = device_serial.strip()
        
        # Check if slot is already occupied
        if slot_id in self.bots:
            logging.warning(f"Slot {slot_id} already has a bot. Stopping existing bot first.")
            self.stop_bot(slot_id)
        
        # Create bot instance
        try:
            bot_instance = BotInstance(slot_id, device_serial, self.base_settings, self.project_root)
            self.bots[slot_id] = bot_instance
            logging.info(f"[Bot {slot_id + 1}] Created bot instance for device {device_serial}")
            return True
        except Exception as e:
            logging.error(f"Failed to create bot in slot {slot_id}: {e}", exc_info=True)
            return False
    
    def start_bot(self, slot_id: int) -> bool:
        """
        Start a bot instance.
        
        Args:
            slot_id: Slot identifier.
        
        Returns:
            True if bot started successfully.
        """
        if slot_id not in self.bots:
            logging.error(f"No bot in slot {slot_id}")
            return False
        
        return self.bots[slot_id].start()
    
    def stop_bot(self, slot_id: int) -> None:
        """
        Stop a bot instance.
        
        Args:
            slot_id: Slot identifier.
        """
        if slot_id not in self.bots:
            return
        
        self.bots[slot_id].stop()
    
    def remove_bot(self, slot_id: int) -> None:
        """
        Remove a bot instance from a slot.
        
        Args:
            slot_id: Slot identifier.
        """
        if slot_id not in self.bots:
            return
        
        bot_instance = self.bots[slot_id]
        
        # Stop bot if running
        try:
            self.stop_bot(slot_id)
        except Exception as e:
            logging.error(f"[Bot {slot_id + 1}] Error stopping bot during removal: {e}")
        
        # Wait for thread to finish (with shorter timeout to avoid blocking GUI)
        if bot_instance.bot_thread and bot_instance.bot_thread.is_alive():
            logging.info(f"[Bot {slot_id + 1}] Waiting for bot thread to finish...")
            # Use shorter timeout since this runs in background thread
            bot_instance.bot_thread.join(timeout=3.0)
            
            # If thread is still alive after timeout, log warning but continue
            # Since it's a daemon thread, it will be terminated when main thread exits
            if bot_instance.bot_thread.is_alive():
                logging.warning(f"[Bot {slot_id + 1}] Bot thread did not finish within timeout (daemon thread will be terminated)")
        
        # Cleanup bot resources
        try:
            if bot_instance.bot:
                # Ensure stop flag is set
                if hasattr(bot_instance.bot, '_stop_flag'):
                    bot_instance.bot._stop_flag = True
                # Close ADB client if possible
                if hasattr(bot_instance.bot, 'client'):
                    try:
                        # ADBClient doesn't have explicit close, but we can mark it as stopped
                        pass
                    except Exception as e:
                        logging.debug(f"[Bot {slot_id + 1}] Error closing ADB client: {e}")
        except Exception as e:
            logging.warning(f"[Bot {slot_id + 1}] Error during bot cleanup: {e}")
        
        # Remove from dictionary
        try:
            del self.bots[slot_id]
            logging.info(f"[Bot {slot_id + 1}] Removed bot from slot")
        except Exception as e:
            logging.error(f"[Bot {slot_id + 1}] Error removing bot from dictionary: {e}")
    
    def stop_all(self) -> None:
        """Stop all running bots (non-blocking)."""
        # Stop all bots in parallel to avoid blocking
        slot_ids = list(self.bots.keys())
        for slot_id in slot_ids:
            try:
                self.stop_bot(slot_id)
            except Exception as e:
                logging.error(f"[Bot {slot_id + 1}] Error stopping: {e}")
        
        # Note: We don't wait for threads to finish here to avoid blocking GUI shutdown
        # Daemon threads will be terminated when main thread exits
    
    def get_bot_status(self, slot_id: int) -> Optional[Dict[str, any]]:
        """
        Get status of a bot instance.
        
        Args:
            slot_id: Slot identifier.
        
        Returns:
            Status dictionary or None if slot is empty.
        """
        if slot_id not in self.bots:
            return None
        
        return self.bots[slot_id].get_status_info()
    
    def get_all_statuses(self) -> Dict[int, Dict[str, any]]:
        """Get status of all bot instances."""
        return {
            slot_id: bot.get_status_info()
            for slot_id, bot in self.bots.items()
        }
    
    def get_running_count(self) -> int:
        """Get count of currently running bots."""
        return sum(1 for bot in self.bots.values() if bot.is_running)
    
    def has_bot(self, slot_id: int) -> bool:
        """Check if a slot has a bot instance."""
        return slot_id in self.bots

