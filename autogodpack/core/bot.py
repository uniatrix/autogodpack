"""Main bot orchestrator."""

import logging
import time
import sys
import os
import threading
from pathlib import Path
from typing import Optional

from ..adb.client import ADBClient
from ..adb.commands import ADBCommands
from ..image.screenshot import ScreenshotCapture
from ..image.matcher import TemplateMatcher
from ..state.persistence import StatePersistence
from ..config.settings import Settings
from .state_machine import StateMachine
from . import stop_checker

logger = logging.getLogger(__name__)

# Import original battle_bot functions for compatibility
# This allows gradual migration while maintaining functionality
run_battle_cycle = None
_battle_bot_module = None

# Registry of active bot instances for per-bot stop checking
_active_bot_instances = {}
_active_bot_lock = threading.Lock()

_src_path = Path(__file__).parent.parent.parent / "src"
if _src_path.exists():
    try:
        # Add to path temporarily
        if str(_src_path) not in sys.path:
            sys.path.insert(0, str(_src_path))
        
        import battle_bot as _battle_bot_module
        if hasattr(_battle_bot_module, 'run_battle_cycle'):
            run_battle_cycle = _battle_bot_module.run_battle_cycle
            logger.info("Loaded battle_bot module from src/")
            
            # Patch check_stop_flag to check all active bots
            _original_check_stop_flag = _battle_bot_module.check_stop_flag
            
            def patched_check_stop_flag():
                """Check stop flag for current thread's bot."""
                import threading
                current_thread = threading.current_thread()
                thread_id = current_thread.ident
                
                # Check if this thread has an associated bot
                with _active_bot_lock:
                    bot_instance = _active_bot_instances.get(thread_id)
                
                if bot_instance:
                    return hasattr(bot_instance, '_stop_flag') and bot_instance._stop_flag
                
                # Fallback to original if no bot registered
                return _original_check_stop_flag()
            
            _battle_bot_module.check_stop_flag = patched_check_stop_flag
        else:
            logger.warning("battle_bot module found but run_battle_cycle not available")
    except ImportError as e:
        logger.warning(f"Could not import battle_bot: {e}")
        run_battle_cycle = None
    except Exception as e:
        logger.error(f"Error loading battle_bot: {e}", exc_info=True)
        run_battle_cycle = None
else:
    logger.warning(f"src/ directory not found at {_src_path}")
    run_battle_cycle = None


class BattleBot:
    """Main battle bot orchestrator."""

    def __init__(self, settings: Settings, project_root: Path, slot_id: Optional[int] = None):
        """
        Initialize battle bot.

        Args:
            settings: Configuration settings.
            project_root: Project root directory.
            slot_id: Bot slot ID (0-3) for multi-bot support. None for single bot mode.
        """
        self.settings = settings
        self.project_root = project_root
        self.slot_id = slot_id

        # Initialize components
        self.client = ADBClient(settings.adb)
        self.commands = ADBCommands(self.client)
        self.screenshot = ScreenshotCapture(self.client)
        self.matcher = TemplateMatcher(
            default_threshold=settings.matching.default_threshold,
            verbose=settings.matching.verbose,
        )

        # Initialize state machine
        template_base_dir = settings.paths.get_template_path(project_root)
        self.state_machine = StateMachine(
            self.client,
            self.screenshot,
            self.matcher,
            settings,
            template_base_dir,
        )

        # Initialize state persistence
        state_file = settings.paths.get_state_path(project_root)
        self.state_persistence = StatePersistence(state_file)
        self.state_persistence.slot_id = slot_id  # Store slot_id for per-bot state

        # Check reset flag
        reset_flag_file = settings.paths.get_reset_flag_path(project_root)
        self.state_persistence.check_reset_flag(reset_flag_file, slot_id=slot_id)
        
        # Store reference to this bot instance for stop checking
        self._stop_flag = False
        
        # Patch battle_bot functions if module is loaded
        if _battle_bot_module is not None:
            self._patch_battle_bot_functions(_battle_bot_module)
            # Set per-bot stop checker using a closure that captures this instance
            self._setup_battle_bot_stop_checker()

    def run_cycle(self) -> bool:
        """
        Run a single battle cycle.

        Returns:
            True if cycle completed successfully, False if stopped.
        """
        # Check stop flag before starting cycle
        if hasattr(self, '_stop_flag') and self._stop_flag:
            return False
            
        try:
            # Use original implementation for now (compatibility layer)
            if run_battle_cycle is not None:
                # Set ADB_SERIAL in thread-local storage for this bot instance
                try:
                    if hasattr(_battle_bot_module, 'set_adb_serial'):
                        _battle_bot_module.set_adb_serial(self.settings.adb.serial)
                        # Removed debug logging - too verbose
                    elif hasattr(_battle_bot_module, 'ADB_SERIAL'):
                        # Fallback to global for backward compatibility
                        _battle_bot_module.ADB_SERIAL = self.settings.adb.serial
                        # Removed debug logging - too verbose
                    
                    # Set slot_id in thread-local storage for this bot instance
                    if self.slot_id is not None and hasattr(_battle_bot_module, 'set_slot_id'):
                        _battle_bot_module.set_slot_id(self.slot_id)
                        # Removed debug logging - too verbose
                    
                    # Set slot_id in thread-local storage for this bot instance
                    if self.slot_id is not None and hasattr(_battle_bot_module, 'set_slot_id'):
                        _battle_bot_module.set_slot_id(self.slot_id)
                        # Removed debug logging - too verbose
                    
                    # Inject stop flag checker into battle_bot module
                    if hasattr(_battle_bot_module, 'set_stop_checker'):
                        _battle_bot_module.set_stop_checker(
                            lambda: hasattr(self, '_stop_flag') and self._stop_flag
                        )
                        # Removed debug logging - too verbose
                except Exception as e:
                    logger.warning(f"Could not configure battle_bot module: {e}")
                
                # Check stop flag before running cycle
                if hasattr(self, '_stop_flag') and self._stop_flag:
                    return False
                
                result = run_battle_cycle()
                
                # Check stop flag after cycle
                if hasattr(self, '_stop_flag') and self._stop_flag:
                    return False
                    
                return result
            else:
                # Otherwise, use new implementation
                return self._run_cycle_new()
        except Exception as e:
            logger.error(f"Error in run_cycle: {e}", exc_info=True)
            return False

    def _run_cycle_new(self) -> bool:
        """
        Run cycle using new implementation.

        Returns:
            True if successful.
        """
        # Check reset flag
        reset_flag_file = self.settings.paths.get_reset_flag_path(self.project_root)
        self.state_persistence.check_reset_flag(reset_flag_file)

        # Detect current screen
        current_screen = self.state_machine.detect_current_screen()

        if current_screen == "battle_selection":
            logger.info("Starting from battle selection screen...")
            # Handle battle selection
            # This would call a screen handler
            return True
        elif current_screen == "battle_setup":
            logger.info("Starting from battle setup screen...")
            # Handle battle setup
            return True
        # ... other screen handlers

        logger.warning(f"Unknown screen: {current_screen}")
        return False

    def _setup_battle_bot_stop_checker(self) -> None:
        """Setup stop checker for this bot instance in battle_bot module."""
        if _battle_bot_module is None:
            return
        
        # Create a closure that captures this bot instance
        bot_instance = self
        def check_stop_for_this_bot():
            return hasattr(bot_instance, '_stop_flag') and bot_instance._stop_flag
        
        # Store the checker function in a thread-local way
        # Since battle_bot uses a global, we need to set it each time before use
        # Instead, we'll patch check_stop_flag to check all active bots
        _battle_bot_module.set_stop_checker(check_stop_for_this_bot)
    
    def _patch_battle_bot_functions(self, module) -> None:
        """Patch battle_bot functions to check stop flag."""
        import time
        
        # Capture self in a variable for closure
        bot_instance = self
        
        # Store original functions
        original_wait_for_battle_completion = getattr(module, 'wait_for_battle_completion', None)
        original_wait_and_tap_template = getattr(module, 'wait_and_tap_template', None)
        
        if original_wait_for_battle_completion:
            def patched_wait_for_battle_completion(max_wait_time=None):
                """Patched version that checks stop flag."""
                # Import needed functions from battle_bot (must be at top)
                from battle_bot import (
                    get_template_path, screenshot_bgr, find_template, tap,
                    detect_current_battle_screen, RESULT_DIR, BATTLE_IN_PROGRESS_DIR,
                    BATTLE_SETUP_DIR, get_bot_prefix
                )
                
                start_time = time.time()
                check_interval = 0.5  # Check stop flag every 0.5 seconds
                
                # Wrap the original function's loop logic
                if max_wait_time:
                    logger.info(f"{get_bot_prefix()}Waiting for battle completion (max {max_wait_time}s)...")
                else:
                    logger.info(f"{get_bot_prefix()}Waiting for battle completion (no timeout)...")
                
                tap_to_proceed_path = get_template_path("tap_to_proceed.png", RESULT_DIR)
                opponent_path = get_template_path("opponent.png", BATTLE_IN_PROGRESS_DIR)
                battle_path = get_template_path("battle.png", BATTLE_SETUP_DIR)
                auto_off_path = get_template_path("auto_off.png", BATTLE_IN_PROGRESS_DIR)
                put_basic_path = get_template_path("put_basic_pokemon.png", BATTLE_IN_PROGRESS_DIR)
                
                if not os.path.exists(tap_to_proceed_path):
                    logger.error(f"Template tap_to_proceed.png not found")
                    return False
                
                check_interval_normal = 2.5  # Increased from 2.0 to reduce CPU usage
                check_interval_battle = 0.8  # Increased from 0.5 to reduce CPU usage
                attempts = 0
                battle_started = False
                last_status_log = 0
                
                while True:
                    # Check stop flag frequently
                    if hasattr(bot_instance, '_stop_flag') and bot_instance._stop_flag:
                        logger.info(f"{get_bot_prefix()}Stop requested during battle wait - aborting")
                        return False
                    
                    # Check timeout
                    if max_wait_time and time.time() - start_time >= max_wait_time:
                        logger.error(f"{get_bot_prefix()}Timeout: Battle not completed after {max_wait_time}s")
                        return False
                    
                    attempts += 1
                    elapsed = int(time.time() - start_time)
                    
                    screen = screenshot_bgr()
                    if screen is None:
                        logger.warning(f"{get_bot_prefix()}Attempt {attempts}: Could not capture screenshot (elapsed: {elapsed}s)")
                        time.sleep(check_interval_normal)
                        continue
                    
                    # Check for result screen
                    tap_result_pos = find_template(screen, tap_to_proceed_path, threshold=0.75, verbose=False)
                    if tap_result_pos:
                        logger.info(f"{get_bot_prefix()}Result screen found after {elapsed}s")
                        return True
                    
                    # Detect current screen
                    detected_screen = detect_current_battle_screen(verbose=False)
                    
                    # Check if still in battle setup
                    if detected_screen == "battle_setup":
                        auto_setup_path = get_template_path("auto.png", BATTLE_SETUP_DIR)
                        if os.path.exists(auto_setup_path):
                            auto_setup_pos = find_template(screen, auto_setup_path, threshold=0.75, verbose=False)
                            if auto_setup_pos and os.path.exists(battle_path):
                                battle_pos = find_template(screen, battle_path, threshold=0.75, verbose=False)
                                if battle_pos:
                                    logger.warning(f"{get_bot_prefix()}Still in Battle Setup after {elapsed}s - clicking Battle again")
                                    if tap(battle_pos[0], battle_pos[1]):
                                        time.sleep(2.0)
                                    continue
                    elif detected_screen == "battle_selection":
                        logger.info(f"{get_bot_prefix()}Battle completed! Returned to battle selection after {elapsed}s")
                        return True
                    
                    # Check if in battle
                    is_in_battle = False
                    if detected_screen == "battle_in_progress":
                        is_in_battle = True
                    elif os.path.exists(opponent_path):
                        opponent_pos = find_template(screen, opponent_path, threshold=0.75, verbose=False)
                        if opponent_pos:
                            is_in_battle = True
                    elif os.path.exists(put_basic_path):
                        put_basic_pos = find_template(screen, put_basic_path, threshold=0.75, verbose=False)
                        if put_basic_pos:
                            is_in_battle = True
                    
                    # Check if Auto is OFF during battle
                    if is_in_battle and os.path.exists(auto_off_path):
                        auto_off_pos = find_template(screen, auto_off_path, threshold=0.75, verbose=False)
                        if auto_off_pos:
                            logger.warning(f"{get_bot_prefix()}Auto is OFF during battle after {elapsed}s! Turning Auto ON...")
                            if tap(auto_off_pos[0], auto_off_pos[1]):
                                time.sleep(0.5)
                            continue
                    
                    # Check if battle started
                    if not battle_started:
                        if detected_screen == "battle_in_progress":
                            battle_started = True
                            logger.info(f"{get_bot_prefix()}Battle started! Detected battle_in_progress after {elapsed}s")
                        elif os.path.exists(opponent_path):
                            opponent_pos = find_template(screen, opponent_path, threshold=0.75, verbose=False)
                            if opponent_pos:
                                battle_started = True
                                logger.info(f"{get_bot_prefix()}Battle started! Opponent found after {elapsed}s")
                        elif os.path.exists(put_basic_path):
                            put_basic_pos = find_template(screen, put_basic_path, threshold=0.75, verbose=False)
                            if put_basic_pos:
                                battle_started = True
                                logger.info(f"{get_bot_prefix()}Battle started! 'Put Basic Pokémon' screen detected after {elapsed}s")
                    else:
                        if elapsed - last_status_log >= 60:
                            logger.info(f"{get_bot_prefix()}Battle in progress... waiting for completion ({elapsed}s)")
                            last_status_log = elapsed
                    
                    # Use smaller interval when battle started
                    sleep_time = check_interval_battle if battle_started else check_interval_normal
                    
                    # Optimized interruptible sleep - check less frequently to reduce CPU overhead
                    sleep_remaining = sleep_time
                    check_interval_sleep = 0.3  # Increased from 0.1 to reduce overhead
                    while sleep_remaining > 0:
                        if hasattr(bot_instance, '_stop_flag') and bot_instance._stop_flag:
                            logger.info(f"{get_bot_prefix()}Stop requested during sleep - aborting")
                            return False
                        actual_sleep = min(check_interval_sleep, sleep_remaining)
                        time.sleep(actual_sleep)
                        sleep_remaining -= actual_sleep
            
            # Replace the function in the module
            module.wait_for_battle_completion = patched_wait_for_battle_completion
        
        if original_wait_and_tap_template:
            def patched_wait_and_tap_template(filename, timeout=10, threshold=0.75, screen_dir=None, fast_mode=False):
                """Patched version that checks stop flag."""
                from battle_bot import get_template_path, screenshot_bgr, find_template, tap, get_bot_prefix
                
                path = get_template_path(filename, screen_dir)
                end = time.time() + timeout
                attempts = 0
                
                check_interval = 0.2 if fast_mode else 0.5  # Increased to reduce CPU usage
                tap_delay = 0.2 if fast_mode else 1.0
                retry_delay = 0.15 if fast_mode else 0.5
                
                while time.time() < end:
                    # Check stop flag
                    if hasattr(bot_instance, '_stop_flag') and bot_instance._stop_flag:
                        logger.info(f"{get_bot_prefix()}Stop requested during wait_and_tap_template for {filename} - aborting")
                        return False
                    
                    attempts += 1
                    screen = screenshot_bgr()
                    if screen is None:
                        logger.warning(f"{get_bot_prefix()}Attempt {attempts}: Could not capture screen")
                        time.sleep(0.3)  # Slightly longer wait on failure
                        continue
                    
                    pos = find_template(screen, path, threshold=threshold)
                    if pos:
                        logger.info(f"{get_bot_prefix()}Template {filename} found at {pos} (attempt {attempts})")
                        if tap(pos[0], pos[1]):
                            time.sleep(tap_delay)
                            return True
                        else:
                            logger.warning(f"{get_bot_prefix()}Tap failed, retrying...")
                            time.sleep(retry_delay)
                            continue
                    
                    # Optimized interruptible sleep - check less frequently
                    sleep_remaining = check_interval
                    check_interval_sleep = 0.2  # Increased from 0.05 to reduce overhead
                    while sleep_remaining > 0:
                        if hasattr(bot_instance, '_stop_flag') and bot_instance._stop_flag:
                            logger.info(f"{get_bot_prefix()}Stop requested during sleep in wait_and_tap_template - aborting")
                            return False
                        actual_sleep = min(check_interval_sleep, sleep_remaining)
                        time.sleep(actual_sleep)
                        sleep_remaining -= actual_sleep
                
                logger.error(f"{get_bot_prefix()}Template {filename} not found after {attempts} attempts (timeout={timeout}s)")
                return False
            
            # Replace the function in the module
            module.wait_and_tap_template = patched_wait_and_tap_template
    
    def stop(self) -> None:
        """Stop the bot."""
        self._stop_flag = True
        logger.info("Stop flag set - bot will stop at next check point")
        
    def run(self) -> None:
        """Run bot in continuous loop."""
        self._stop_flag = False
        
        # Register this bot instance with current thread for stop checking
        current_thread = threading.current_thread()
        thread_id = current_thread.ident
        with _active_bot_lock:
            _active_bot_instances[thread_id] = self
        
        try:
            # Set ADB_SERIAL in thread-local storage for this bot instance
            # This must be done at the start of run() to ensure it's set before any battle_bot functions are called
            if _battle_bot_module is not None:
                try:
                    if hasattr(_battle_bot_module, 'set_adb_serial'):
                        _battle_bot_module.set_adb_serial(self.settings.adb.serial)
                        logger.debug(f"Set thread-local ADB_SERIAL to {self.settings.adb.serial} at start of run()")
                    elif hasattr(_battle_bot_module, 'ADB_SERIAL'):
                        # Fallback to global for backward compatibility
                        _battle_bot_module.ADB_SERIAL = self.settings.adb.serial
                        logger.debug(f"Set global ADB_SERIAL to {self.settings.adb.serial} at start of run() (fallback)")
                    
                    # Set slot_id in thread-local storage for this bot instance
                    if self.slot_id is not None and hasattr(_battle_bot_module, 'set_slot_id'):
                        _battle_bot_module.set_slot_id(self.slot_id)
                        logger.debug(f"Set thread-local slot_id to {self.slot_id} at start of run()")
                except Exception as e:
                    logger.warning(f"Could not set ADB_SERIAL/slot_id at start of run(): {e}")
            
            # Setup stop checker for this bot instance (not global to avoid conflicts)
            checker = stop_checker.StopChecker(lambda: hasattr(self, '_stop_flag') and self._stop_flag)
            
            # The patched check_stop_flag in battle_bot will automatically find this bot instance
            # via the thread registry (_active_bot_instances), so no need to set it explicitly
            
            # Removed startup logs - too verbose
            # Bot identification and page info logged in battle_bot.py

            # Verify template directory exists
            template_dir = self.settings.paths.get_template_path(self.project_root) / "battle"
            if not template_dir.exists():
                error_msg = f"Template directory not found: {template_dir}"
                logger.error(error_msg)
                logger.error("Please ensure battle templates exist")
                raise FileNotFoundError(error_msg)

            cycle_count = 0

            try:
                while True:
                    # Check if bot should stop (for GUI control) - check frequently
                    if hasattr(self, '_stop_flag') and self._stop_flag:
                        break
                        
                    cycle_count += 1
                    # Removed cycle header logs - too verbose

                    try:
                        # Check stop flag before cycle
                        if hasattr(self, '_stop_flag') and self._stop_flag:
                            break
                            
                        success = self.run_cycle()
                        
                        # Check stop flag after cycle
                        if hasattr(self, '_stop_flag') and self._stop_flag:
                            break

                        # Removed cycle completion logs - too verbose
                        # Only log page/screen info which is done in battle_bot.py
                    except Exception as cycle_error:
                        logger.error(f"Error in cycle #{cycle_count}: {cycle_error}", exc_info=True)
                        # Check stop flag even after error
                        if hasattr(self, '_stop_flag') and self._stop_flag:
                            break
                        # Continue to next cycle instead of crashing
                        # Removed warning log - too verbose

                    # Check stop flag before delay
                    if hasattr(self, '_stop_flag') and self._stop_flag:
                        break
                    
                    # Delay before next cycle with optimized interruptible sleep
                    delay_remaining = self.settings.automation.cycle_delay
                    check_interval = 0.3  # Check every 300ms (reduced frequency for less CPU usage)
                    while delay_remaining > 0:
                        if hasattr(self, '_stop_flag') and self._stop_flag:
                            break
                        sleep_time = min(check_interval, delay_remaining)
                        time.sleep(sleep_time)
                        delay_remaining -= sleep_time
                    
                    # Final check before next iteration
                    if hasattr(self, '_stop_flag') and self._stop_flag:
                        break

            except KeyboardInterrupt:
                # Removed verbose interruption logs - too noisy
                pass
            except Exception as e:
                logger.error(f"Unexpected error in bot loop: {e}", exc_info=True)
                # Removed cycle count log - too verbose
                raise  # Re-raise to be caught by outer handler
                
        except Exception as e:
            logger.critical(f"Critical error in bot.run(): {e}", exc_info=True)
            # Don't re-raise - let the thread finish gracefully
            # The exception will be logged and the thread will exit
        finally:
            # Cleanup resources
            try:
                # Unregister this bot instance from thread registry
                current_thread = threading.current_thread()
                thread_id = current_thread.ident
                with _active_bot_lock:
                    _active_bot_instances.pop(thread_id, None)
                
                # Clear stop checker for this bot instance
                if _battle_bot_module is not None:
                    _battle_bot_module.set_stop_checker(None)
                # Removed debug logging - too verbose
            except Exception as cleanup_error:
                logger.warning(f"Error during bot cleanup: {cleanup_error}")

