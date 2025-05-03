from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPalette, QColor

class VisualWarningHandler:
    """Handles the visual warning logic (flashing background) for a QWidget."""

    def __init__(self, target_widget, default_duration_ms=300):
        """
        Initializes the VisualWarningHandler.

        Args:
            target_widget (QWidget): The widget whose background will be flashed.
            default_duration_ms (int): The default flash duration in milliseconds.
        """
        self.target_widget = target_widget
        self.original_palette = target_widget.palette()
        self.warning_active = False
        self.enabled = True
        self.flash_duration_ms = default_duration_ms

        self.warning_timer = QTimer()
        self.warning_timer.setSingleShot(True)
        self.warning_timer.timeout.connect(self._reset_visual_warning)

    def setEnabled(self, enabled):
        """Enables or disables the visual warning."""
        self.enabled = enabled
        if not enabled and self.warning_active:
             self._reset_visual_warning()
             self.warning_timer.stop()


    def isEnabled(self):
         """Returns True if the visual warning is enabled."""
         return self.enabled

    def setFlashDuration(self, duration_ms):
        """
        Sets the duration of the visual warning flash in milliseconds.

        Args:
            duration_ms (int): The desired duration in milliseconds. Must be positive.
        """
        try:
            duration = int(duration_ms)
            if duration > 0:
                self.flash_duration_ms = duration
            else:
                print(f"Warning: Visual warning duration must be positive (received {duration}). Keeping previous value ({self.flash_duration_ms} ms).")
        except (ValueError, TypeError):
            print(f"Warning: Invalid visual warning duration type or value ({duration_ms}). Keeping previous value ({self.flash_duration_ms} ms).")

    def trigger(self):
        """Triggers the visual warning if enabled."""
        if self.enabled:
            self._show_warning()

    def _show_warning(self):
        """Flashes the widget background red temporarily."""
        if not self.warning_active:
            self.warning_active = True
            palette = self.target_widget.palette()
            # Use WindowText color role for better visibility with different themes
            palette.setColor(QPalette.ColorRole.Window, QColor('red'))
            self.target_widget.setPalette(palette)
            # Ensure the background color is actually drawn
            self.target_widget.setAutoFillBackground(True)

            self.warning_timer.start(self.flash_duration_ms) # Use configurable duration

    def _reset_visual_warning(self):
        """Resets the widget background to its original color."""
        self.target_widget.setPalette(self.original_palette)
        self.target_widget.setAutoFillBackground(False) # Reset auto fill
        self.warning_active = False
