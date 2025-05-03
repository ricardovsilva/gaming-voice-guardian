from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QSpinBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

class VisualWarningTab(QWidget):
    """
    Handles visual warning logic and UI, managing its state from config.
    Acts as the widget for the 'Visual Warning' tab.
    """

    def __init__(self, targetWidget, configData=None, parent=None):
        """
        Initializes the VisualWarningHandler.

        Args:
            target_widget (QWidget): The widget whose background will be flashed.
            config_data (dict): Dictionary containing initial settings (e.g., from config file's [visual] section).
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)  # Call QWidget constructor

        self.targetWidget = targetWidget
        self.originalPalette = targetWidget.palette()
        self.warningActive = False

        if configData is None:
            configData = {}

        initialEnabled = configData.get('enableVisualCheck', 'True').lower() == 'true'
        try:
            initialDurationMs = int(configData.get('flashDurationMs', '300'))
            if initialDurationMs <= 0:
                initialDurationMs = 300
        except (ValueError, TypeError):
            initialDurationMs = 300

        self.enabled = initialEnabled
        self.flashDurationMs = initialDurationMs

        self.warningtimer = QTimer()
        self.warningtimer.setSingleShot(True)
        self.warningtimer.timeout.connect(self._reset_visual_warning)
        
        # === UI ELEMENTS ===
        self.visual_layout = QVBoxLayout(self)
        self._init_enable_checkbox()
        self._init_duration_control()
        self.duration_layout.addStretch()
        

    def _init_enable_checkbox(self):
        self.enable_check = QCheckBox("Enable Visual Warning (Flash Background)", self)
        self.enable_check.setChecked(self.enabled)
        self.enable_check.stateChanged.connect(self._handle_enable_change)
        self.visual_layout.addWidget(self.enable_check)

    def _init_duration_control(self):
        self.duration_layout = QHBoxLayout()
        self.visual_layout.addLayout(self.duration_layout)
        self.flash_duration_label = QLabel("Flash Duration (ms):", self)
        self.flash_duration_input = QSpinBox(self)
        self.flash_duration_input.setRange(50, 5000)
        self.flash_duration_input.setSingleStep(50)
        self.flash_duration_input.setMaximumWidth(100)
        self.flash_duration_input.setValue(self.flashDurationMs)
        self.flash_duration_input.valueChanged.connect(self._handle_duration_change)

        self.duration_layout.addWidget(self.flash_duration_label)
        self.duration_layout.addWidget(self.flash_duration_input)

    def _handle_enable_change(self, state):
        """Internal slot for checkbox state changes."""
        self.setEnabled(bool(state))

    def _handle_duration_change(self, value):
        """Internal slot for spinbox value changes."""
        self.setFlashDuration(value)

    def setEnabled(self, enabled):
        """Enables or disables the visual warning (updates internal state and UI)."""
        if isinstance(enabled, int):
            enabled = bool(enabled)
        self.enabled = enabled
        if self.enable_check.isChecked() != self.enabled:
            self.enable_check.setChecked(self.enabled)
        if not enabled and self.warningActive:
            self._reset_visual_warning()
            self.warningtimer.stop()


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
                self.flashDurationMs = duration
                # Update spinbox only if needed (prevent signal loop)
                if self.flash_duration_input.value() != self.flashDurationMs:
                    # Block signals to prevent infinite loop if spinbox value was invalid before
                    self.flash_duration_input.blockSignals(True)
                    self.flash_duration_input.setValue(self.flashDurationMs)
                    self.flash_duration_input.blockSignals(False)
            else:
                print(f"Warning: Visual warning duration must be positive (received {duration}). Keeping previous value ({self.flashDurationMs} ms).")
                # Reset input to last valid value
                if self.flash_duration_input.value() != self.flashDurationMs:
                    self.flash_duration_input.blockSignals(True)
                    self.flash_duration_input.setValue(self.flashDurationMs)
                    self.flash_duration_input.blockSignals(False)
        except (ValueError, TypeError):
            print(f"Warning: Invalid visual warning duration type or value ({duration_ms}). Keeping previous value ({self.flashDurationMs} ms).")
            # Reset input to last valid value
            if self.flash_duration_input.value() != self.flashDurationMs:
                self.flash_duration_input.blockSignals(True)
                self.flash_duration_input.setValue(self.flashDurationMs)
                self.flash_duration_input.blockSignals(False)
                
    def get_config_values(self):
        """Returns the current UI state as a dictionary for saving."""
        return {
            "enableVisualCheck": str(self.enable_check.isChecked()),
            "flashDurationMs": str(self.flash_duration_input.value())
        }

    def trigger(self):
        """Triggers the visual warning if enabled."""
        if self.enabled:
            self._show_warning()

    def _show_warning(self):
        """Flashes the widget background red temporarily."""
        if not self.warningActive:
            self.warningActive = True
            palette = self.targetWidget.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor('red'))
            self.targetWidget.setPalette(palette)
            self.targetWidget.setAutoFillBackground(True)

            self.warningtimer.start(self.flashDurationMs)

    def _reset_visual_warning(self):
        """Resets the widget background to its original color."""
        self.targetWidget.setPalette(self.originalPalette)
        self.targetWidget.setAutoFillBackground(False)
        self.targetWidget.update()
        self.warningActive = False
