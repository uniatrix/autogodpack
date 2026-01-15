"""Custom exception classes for AutoGodPack."""


class AutoGodPackError(Exception):
    """Base exception for AutoGodPack."""

    pass


class ADBError(AutoGodPackError):
    """Exception raised for ADB-related errors."""

    pass


class ScreenshotError(AutoGodPackError):
    """Exception raised for screenshot capture errors."""

    pass


class TemplateNotFoundError(AutoGodPackError):
    """Exception raised when a template image is not found."""

    pass


class ScreenDetectionError(AutoGodPackError):
    """Exception raised for screen detection errors."""

    pass


class ConfigurationError(AutoGodPackError):
    """Exception raised for configuration errors."""

    pass


class StateError(AutoGodPackError):
    """Exception raised for state management errors."""

    pass






