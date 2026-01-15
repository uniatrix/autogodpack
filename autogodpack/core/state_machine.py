"""Screen state detection and state machine."""

import logging
from typing import Optional
from pathlib import Path

from ..adb.client import ADBClient
from ..image.screenshot import ScreenshotCapture
from ..image.matcher import TemplateMatcher
from ..config.settings import Settings

logger = logging.getLogger(__name__)


class StateMachine:
    """Manages screen state detection and transitions."""

    def __init__(
        self,
        client: ADBClient,
        screenshot: ScreenshotCapture,
        matcher: TemplateMatcher,
        settings: Settings,
        template_base_dir: Path,
    ):
        """
        Initialize state machine.

        Args:
            client: ADB client.
            screenshot: Screenshot capture.
            matcher: Template matcher.
            settings: Configuration settings.
            template_base_dir: Base template directory.
        """
        self.client = client
        self.screenshot = screenshot
        self.matcher = matcher
        self.settings = settings
        self.template_base_dir = template_base_dir
        self.battle_dir = template_base_dir / "battle"

    def detect_current_screen(self, verbose: bool = True) -> Optional[str]:
        """
        Detect current screen state.

        Args:
            verbose: Enable verbose logging (deprecated - not used anymore).

        Returns:
            Screen name or None if not recognized.
        """
        # Removed initial detection log - too verbose

        screen = self.screenshot.capture_bgr()
        if screen is None:
            # Only log critical errors
            return None

        # Check screens in priority order (most specific first)
        detected_templates = []

        # Screen 8: Pop-up OK (most specific - appears over other screens)
        ok_path = self.battle_dir / "screen_8" / "ok.png"
        if ok_path.exists():
            ok_pos = self.matcher.find_template(
                screen, str(ok_path), threshold=0.75, verbose=False
            )
            if ok_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "screen_8"
            detected_templates.append(("ok.png", False))

        # Screen Defeat Popup
        back_path = self.battle_dir / "screen_defeat_popup" / "back.png"
        if back_path.exists():
            back_pos = self.matcher.find_template(
                screen, str(back_path), threshold=0.75, verbose=False
            )
            if back_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "defeat_popup"
            detected_templates.append(("back.png", False))

        # Screen 7: Next button
        next_path = self.battle_dir / "screen_7" / "next.png"
        if next_path.exists():
            next_pos = self.matcher.find_template(
                screen, str(next_path), threshold=0.75, verbose=False
            )
            if next_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "screen_7"
            detected_templates.append(("next.png", False))

        # Screen Defeat
        defeat_path = self.battle_dir / "screen_defeat" / "defeat.png"
        if defeat_path.exists():
            defeat_pos = self.matcher.find_template(
                screen, str(defeat_path), threshold=0.75, verbose=False
            )
            if defeat_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "defeat_screen"
            detected_templates.append(("defeat.png", False))

        # Select Expansion Screen
        close_x_path = self.battle_dir / "select_expansion" / "close_button" / "close_x.png"
        has_close_button = False
        if close_x_path.exists():
            close_pos = self.matcher.find_template(
                screen, str(close_x_path), threshold=0.75, verbose=False
            )
            if close_pos:
                has_close_button = True

        if has_close_button:
            # Screen detection logged in battle_bot.py with bot prefix
            return "select_expansion"

        # Check for expansions visible
        for expansion in (
            self.settings.expansions.series_a + self.settings.expansions.series_b
        ):
            exp_path = None
            if expansion in self.settings.expansions.series_a:
                exp_path = self.battle_dir / "select_expansion" / "series_a" / f"{expansion}.png"
            else:
                exp_path = self.battle_dir / "select_expansion" / "series_b" / f"{expansion}.png"

            if exp_path.exists():
                pos = self.matcher.find_template(
                    screen, str(exp_path), threshold=0.75, verbose=False
                )
                if pos:
                    # Check if also has Expansions button (battle_selection)
                    expansions_path = (
                        self.battle_dir / "screen_1_battle_selection" / "expansions.png"
                    )
                    has_expansions_button = False
                    if expansions_path.exists():
                        expansions_pos = self.matcher.find_template(
                            screen, str(expansions_path), threshold=0.75, verbose=False
                        )
                        if expansions_pos:
                            has_expansions_button = True

                    if not has_expansions_button:
                        # Screen detection logged in battle_bot.py with bot prefix
                        return "select_expansion"

        # Screen 1: Battle Selection (expansions button)
        expansions_path = self.battle_dir / "screen_1_battle_selection" / "expansions.png"
        expansions_pos = None
        if expansions_path.exists():
            expansions_pos = self.matcher.find_template(
                screen, str(expansions_path), threshold=0.75, verbose=False
            )
            if expansions_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "battle_selection"
            detected_templates.append(("expansions.png", False))

        # Battle In Progress
        opponent_path = self.battle_dir / "battle_in_progress" / "opponent.png"
        put_basic_path = self.battle_dir / "battle_in_progress" / "put_basic_pokemon.png"
        opponent_pos = None
        put_basic_pos = None

        if opponent_path.exists():
            opponent_pos = self.matcher.find_template(
                screen, str(opponent_path), threshold=0.75, verbose=False
            )
            detected_templates.append(("opponent.png", opponent_pos is not None))

        if put_basic_path.exists():
            put_basic_pos = self.matcher.find_template(
                screen, str(put_basic_path), threshold=0.75, verbose=False
            )
            detected_templates.append(("put_basic_pokemon.png", put_basic_pos is not None))

        if opponent_pos or put_basic_pos:
            # Screen detection logged in battle_bot.py with bot prefix
            return "battle_in_progress"

        # Screen 2: Battle Setup
        auto_path = self.battle_dir / "screen_2_battle_setup" / "auto.png"
        battle_path = self.battle_dir / "screen_2_battle_setup" / "battle.png"
        auto_pos = None
        battle_pos = None

        if auto_path.exists():
            auto_pos = self.matcher.find_template(
                screen, str(auto_path), threshold=0.75, verbose=False
            )
            detected_templates.append(("auto.png", auto_pos is not None))

        if battle_path.exists():
            battle_pos = self.matcher.find_template(
                screen, str(battle_path), threshold=0.75, verbose=False
            )
            detected_templates.append(("battle.png", battle_pos is not None))

        # Only consider Screen 2 if auto.png found AND no Expansions button
        if auto_pos and expansions_pos is None:
            # Screen detection logged in battle_bot.py with bot prefix
            return "battle_setup"

        # Screens 4-5-6: Tap to Proceed
        tap_4_5_6_path = self.battle_dir / "screen_4_5_6" / "tap_to_proceed.png"
        if tap_4_5_6_path.exists():
            tap_4_5_6_pos = self.matcher.find_template(
                screen, str(tap_4_5_6_path), threshold=0.75, verbose=False
            )
            if tap_4_5_6_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "screens_4_5_6"
            detected_templates.append(("tap_to_proceed (4-5-6)", False))

        # Screen 3: Result Screen
        tap_result_path = self.battle_dir / "screen_3_victory" / "tap_to_proceed.png"
        if tap_result_path.exists():
            tap_result_pos = self.matcher.find_template(
                screen, str(tap_result_path), threshold=0.75, verbose=False
            )
            if tap_result_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "result_screen"
            detected_templates.append(("tap_to_proceed (result)", False))

        # Screen 1: Battle Selection (hourglass - secondary indicator)
        hourglass_path = self.battle_dir / "screen_1_battle_selection" / "hourglass.png"
        if hourglass_path.exists():
            hourglass_pos = self.matcher.find_template(
                screen, str(hourglass_path), threshold=0.75, verbose=False
            )
            if hourglass_pos:
                # Screen detection logged in battle_bot.py with bot prefix
                return "battle_selection"
            detected_templates.append(("hourglass.png", False))

        # Removed verbose logging for unknown screens - too noisy
        # Only log if it's a critical issue
        return None






