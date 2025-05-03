import sys
from PyQt6.QtCore import QTimer, Qt, pyqtSignal # Import pyqtSignal
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QSpinBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QColorDialog,
    QSizePolicy
)

class VisualWarningTab(QWidget):
    """
    Handles visual warning logic and UI, managing its state from config.
    Acts as the widget for the 'Visual Warning' tab.
    Allows warning display on the main target or a separate window.
    Includes color selection.
    Emits settingsChanged signal when user modifies settings.
    """

    # --- Add this signal ---
    settingsChanged = pyqtSignal()
    # -----------------------

    # Signal emitted when the separate window is closed by the user
    separateWindowClosed = pyqtSignal()

    # ... (init remains the same) ...
    def __init__(self, targetWidget, configData=None, parent=None):
        """
        Initializes the VisualWarningHandler.

        Args:
            targetWidget (QWidget): The primary widget whose background can be flashed.
            configData (dict): Dictionary containing initial settings.
            parent (QWidget, optional): Parent widget. Defaults to None.
        """
        super().__init__(parent)

        if targetWidget is None:
             print("Warning: No targetWidget provided for VisualWarningTab. Using internal dummy.")
             self._internal_target_widget = QWidget() # Create an internal one if none provided
             self.targetWidget = self._internal_target_widget
             self.targetWidget.setMinimumSize(200, 100)
        else:
            self.targetWidget = targetWidget
            self._internal_target_widget = None # Flag that we are using external target

        self.originalPalette = self.targetWidget.palette() # Store original palette of the main target
        self.warningActive = False # Is main target currently flashing?

        # --- State for Separate Warning Window ---
        self.alternate_warning_window = None
        self.alternate_window_original_palette = None
        self.alternate_window_timer = QTimer(self) # Timer for the separate window
        self.alternate_window_timer.setSingleShot(True)
        self.alternate_window_timer.timeout.connect(self._reset_alternate_window_warning)

        if configData is None:
            configData = {}

        # --- Load Configuration ---
        initialEnabled = configData.get('enableVisualCheck', 'True').lower() == 'true'
        initialUseSeparate = configData.get('useSeparateWindow', 'False').lower() == 'true'
        try:
            initialDurationMs = int(configData.get('flashDurationMs', '300'))
            if initialDurationMs <= 0: initialDurationMs = 300
        except (ValueError, TypeError):
            initialDurationMs = 300

        initialColorStr = configData.get('warningColor', 'red')
        initialColor = QColor(initialColorStr)
        if not initialColor.isValid():
            print(f"Warning: Invalid color '{initialColorStr}' in config. Defaulting to red.")
            initialColor = QColor('red')

        self.enabled = initialEnabled
        self.flashDurationMs = initialDurationMs
        self.warningColor = initialColor

        # --- Timer for Main Target ---
        self.warningtimer = QTimer(self) # Timer for the main target widget
        self.warningtimer.setSingleShot(True)
        self.warningtimer.timeout.connect(self._reset_visual_warning)

        # === UI ELEMENTS ===
        self.visual_layout = QVBoxLayout(self)
        self._init_enable_checkbox()
        self._init_duration_control()
        self._init_color_picker()
        self._init_separate_window_checkbox(initialUseSeparate) # New checkbox
        self.visual_layout.addStretch()

        # --- Ensure initial state is consistent ---
        if self.use_separate_window_check.isChecked():
             print("Initial state: Separate window enabled. Ensuring window exists.")
             QTimer.singleShot(0, self._ensure_alternate_window_exists_on_init)


    def _ensure_alternate_window_exists_on_init(self):
        """Helper called shortly after init if separate window is initially checked."""
        if self.use_separate_window_check.isChecked(): # Double check state
            if not self._ensure_alternate_window_exists():
                print("Error: Failed to create/show alternate window during initialization.")
                self.use_separate_window_check.blockSignals(True)
                self.use_separate_window_check.setChecked(False)
                self.use_separate_window_check.blockSignals(False)


    def _init_enable_checkbox(self):
        self.enable_check = QCheckBox("Enable Visual Warning", self)
        self.enable_check.setChecked(self.enabled)
        self.enable_check.stateChanged.connect(self._handle_enable_change)
        self.visual_layout.addWidget(self.enable_check)

    def _init_duration_control(self):
        duration_layout = QHBoxLayout()
        self.flash_duration_label = QLabel("Flash Duration (ms):", self)
        self.flash_duration_input = QSpinBox(self)
        self.flash_duration_input.setRange(50, 5000)
        self.flash_duration_input.setSingleStep(50)
        self.flash_duration_input.setMaximumWidth(100)
        self.flash_duration_input.setValue(self.flashDurationMs)
        self.flash_duration_input.valueChanged.connect(self._handle_duration_change) # Connect here

        duration_layout.addWidget(self.flash_duration_label)
        duration_layout.addWidget(self.flash_duration_input)
        duration_layout.addStretch()
        self.visual_layout.addLayout(duration_layout)

    def _init_color_picker(self):
        color_layout = QHBoxLayout()
        self.color_button = QPushButton("Select Warning Color", self)
        self.color_button.clicked.connect(self._select_warning_color) # Connect here

        self.color_preview_label = QLabel("Current Color:", self)
        self.color_preview = QLabel(self)
        self.color_preview.setFixedSize(30, 20)
        self.color_preview.setAutoFillBackground(True)
        self.color_preview.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._update_color_preview()

        color_layout.addWidget(self.color_button)
        color_layout.addWidget(self.color_preview_label)
        color_layout.addWidget(self.color_preview)
        color_layout.addStretch()
        self.visual_layout.addLayout(color_layout)

    def _init_separate_window_checkbox(self, initial_state):
        """Initializes the checkbox to control warning destination."""
        self.use_separate_window_check = QCheckBox("Show Warning in Separate Window", self)
        self.use_separate_window_check.setChecked(initial_state)
        self.use_separate_window_check.stateChanged.connect(self._handle_separate_window_change) # Connect here
        self.visual_layout.addWidget(self.use_separate_window_check)

    # --- Event Handlers / Slots ---

    def _select_warning_color(self):
        new_color = QColorDialog.getColor(self.warningColor, self, "Select Warning Color")
        if new_color.isValid():
            # Check if the color actually changed before emitting
            if self.warningColor != new_color:
                self.warningColor = new_color
                self._update_color_preview()
                # --- Emit the signal ---
                print("Color changed, emitting settingsChanged.")
                self.settingsChanged.emit()
                # -----------------------

    def _update_color_preview(self):
        palette = self.color_preview.palette()
        palette.setColor(QPalette.ColorRole.Window, self.warningColor)
        self.color_preview.setPalette(palette)

    def _handle_enable_change(self, state):
        # Check if state actually changed before emitting
        if self.enabled != bool(state):
            self.setEnabled(bool(state)) # setEnabled already updates self.enabled
            # --- Emit the signal ---
            print("Enable checkbox changed, emitting settingsChanged.")
            self.settingsChanged.emit()
            # -----------------------

    def _handle_duration_change(self, value):
        # Check if value actually changed before emitting
        if self.flashDurationMs != value:
            self.setFlashDuration(value) # setFlashDuration updates self.flashDurationMs
            # --- Emit the signal ---
            print("Duration changed, emitting settingsChanged.")
            self.settingsChanged.emit()
            # -----------------------

    def _handle_separate_window_change(self, state):
        """Handles changes to the 'Use Separate Window' checkbox."""
        use_separate = bool(state)
        # Check if state actually changed before emitting
        # We need to compare against the *intended* state after this handler runs.
        # The checkbox state *is* the new intended state.
        # We can simply emit the signal after handling the logic.

        if use_separate:
            print("Separate window checkbox checked. Ensuring window exists.")
            if not self._ensure_alternate_window_exists():
                print("Error: Failed to create/show alternate window immediately.")
                self.use_separate_window_check.blockSignals(True)
                self.use_separate_window_check.setChecked(False)
                self.use_separate_window_check.blockSignals(False)
                # Don't emit signal if we reverted the change
                return # Exit early
        else:
            print("Separate window checkbox unchecked. Destroying window.")
            self._destroy_alternate_window()

        # --- Emit the signal (if we didn't exit early) ---
        print("Separate window checkbox changed, emitting settingsChanged.")
        self.settingsChanged.emit()
        # -------------------------------------------------


    def _handle_alternate_window_closed(self):
        """Slot connected to the destroyed signal of the alternate window."""
        print("Separate warning window closed by user.")
        # Store previous state before cleanup
        was_checked = self.use_separate_window_check.isChecked()

        self.alternate_warning_window = None
        self.alternate_window_original_palette = None
        self.alternate_window_timer.stop()

        if self.use_separate_window_check.isChecked():
            self.use_separate_window_check.blockSignals(True)
            self.use_separate_window_check.setChecked(False)
            self.use_separate_window_check.blockSignals(False)

        self.separateWindowClosed.emit()

        # Emit settingsChanged only if the checkbox state *was* changed by this handler
        if was_checked: # If it was checked and now is unchecked
             print("Alternate window closed by user, emitting settingsChanged.")
             self.settingsChanged.emit()


    # --- Public Methods ---

    def setEnabled(self, enabled):
        """Enables or disables the visual warning feature entirely."""
        # This method is called by _handle_enable_change, which emits the signal.
        # No need to emit here directly.
        if isinstance(enabled, int): enabled = bool(enabled)
        self.enabled = enabled # Update internal state
        if self.enable_check.isChecked() != self.enabled:
            self.enable_check.setChecked(self.enabled)

        if not enabled:
            if self.warningActive:
                self._reset_visual_warning()
                self.warningtimer.stop()
            if self.alternate_window_timer.isActive():
                self._reset_alternate_window_warning()
                self.alternate_window_timer.stop()
            if self.use_separate_window_check.isChecked():
                 print("Visual warning disabled, destroying separate window.")
                 self._destroy_alternate_window()
                 # Destroying the window will trigger _handle_alternate_window_closed,
                 # which will uncheck the box and emit settingsChanged if needed.


    def isEnabled(self):
         return self.enabled

    def setFlashDuration(self, duration_ms):
        # This method is called by _handle_duration_change, which emits the signal.
        # No need to emit here directly.
        try:
            duration = int(duration_ms)
            if duration > 0:
                self.flashDurationMs = duration # Update internal state
                if self.flash_duration_input.value() != self.flashDurationMs:
                    self.flash_duration_input.blockSignals(True)
                    self.flash_duration_input.setValue(self.flashDurationMs)
                    self.flash_duration_input.blockSignals(False)
            else:
                print(f"Warning: Duration must be positive.")
                if self.flash_duration_input.value() != self.flashDurationMs:
                     self.flash_duration_input.blockSignals(True)
                     self.flash_duration_input.setValue(self.flashDurationMs)
                     self.flash_duration_input.blockSignals(False)
        except (ValueError, TypeError):
            print(f"Warning: Invalid duration value.")
            if self.flash_duration_input.value() != self.flashDurationMs:
                 self.flash_duration_input.blockSignals(True)
                 self.flash_duration_input.setValue(self.flashDurationMs)
                 self.flash_duration_input.blockSignals(False)


    def get_config_values(self):
        """Returns the current UI state as a dictionary for saving."""
        return {
            "enableVisualCheck": str(self.enable_check.isChecked()),
            "flashDurationMs": str(self.flash_duration_input.value()),
            "warningColor": self.warningColor.name(),
            "useSeparateWindow": str(self.use_separate_window_check.isChecked())
        }

    # ... (trigger and other methods remain the same) ...
    def trigger(self):
        """Triggers the visual warning based on current settings."""
        if not self.enabled:
            return

        if self.use_separate_window_check.isChecked():
            self._trigger_alternate_warning()
        else:
            self._trigger_main_warning()

    # --- Internal Warning Logic ---

    def _trigger_main_warning(self):
        """Triggers the flash on the main target widget."""
        if self.warningActive or self.warningtimer.isActive():
            return # Ignore subsequent triggers while active
        self.warningActive = True
        # Ensure we have the latest original palette before flashing
        try:
            if self.targetWidget and self.targetWidget.isWindow():
                self.originalPalette = self.targetWidget.palette()
            else:
                 print("Main target invalid before flashing.")
                 self.warningActive = False # Don't proceed
                 return
        except RuntimeError:
             print("Error getting main target palette before flash (deleted?).")
             self.warningActive = False
             return

        self._flash_widget(self.targetWidget, self.originalPalette, self.warningtimer)

    def _trigger_alternate_warning(self):
        """Ensures the separate window exists and triggers the flash on it."""
        if self.alternate_window_timer.isActive():
             return # Already flashing this window

        # Ensure window exists (it should if checkbox is checked, due to handler)
        if not self.alternate_warning_window or not self.alternate_warning_window.isWindow():
             print("Alternate window missing or invalid when triggering. Attempting recovery.")
             if not self._ensure_alternate_window_exists():
                 print("Error: Could not recover alternate warning window.")
                 # Uncheck the box as we failed?
                 self.use_separate_window_check.blockSignals(True)
                 self.use_separate_window_check.setChecked(False)
                 self.use_separate_window_check.blockSignals(False)
                 # Don't emit settingsChanged here, _handle_separate_window_change handles it if needed
                 return # Failed to create/show

        # Ensure we have the latest original palette before flashing
        try:
            if self.alternate_warning_window and self.alternate_warning_window.isWindow():
                 self.alternate_window_original_palette = self.alternate_warning_window.palette()
            else:
                 print("Alternate window invalid before getting palette for flash.")
                 return # Don't flash if window is bad
        except RuntimeError:
             print("Error getting alternate window palette before flash (deleted?).")
             # self._handle_alternate_window_closed() # Let destroyed signal handle cleanup
             return

        self._flash_widget(self.alternate_warning_window, self.alternate_window_original_palette, self.alternate_window_timer)


    def _ensure_alternate_window_exists(self):
        """Creates the alternate window if needed, ensures it's visible. Returns True on success."""
        window_valid = False
        if self.alternate_warning_window:
            try:
                # Check if the underlying C++ object still exists and is potentially visible
                if self.alternate_warning_window.isWindow():
                    window_valid = True
            except RuntimeError:
                print("Alternate warning window was deleted externally.")
                self.alternate_warning_window = None # Clear ref
                window_valid = False # Needs recreation

        if not window_valid:
            print("Creating new alternate warning window.")
            self.alternate_warning_window = QWidget()
            self.alternate_warning_window.setWindowFlags(Qt.WindowType.Window)
            self.alternate_warning_window.setWindowTitle("Visual Warning Display")
            self.alternate_warning_window.setGeometry(200, 200, 300, 150)
            self.alternate_window_original_palette = self.alternate_warning_window.palette()
            # Connect the destroyed signal to our handler
            try: # Ensure connection is made only once
                self.alternate_warning_window.destroyed.disconnect(self._handle_alternate_window_closed)
            except TypeError: pass # Signal not connected
            self.alternate_warning_window.destroyed.connect(self._handle_alternate_window_closed)
            window_valid = True # Assume creation succeeded

        # Ensure it's visible and raised
        if window_valid and self.alternate_warning_window:
             try:
                self.alternate_warning_window.show()
                self.alternate_warning_window.raise_()
                self.alternate_warning_window.activateWindow()
                return True
             except RuntimeError:
                 print("Error showing/raising alternate window (already deleted?).")
                 self.alternate_warning_window = None # Clear ref
                 return False
        return False


    def _flash_widget(self, widget, original_palette_ref, timer):
        """
        Applies the warning color flash to the specified widget.
        Uses the provided original_palette_ref for reset.
        """
        try:
            if not widget or not widget.isWindow():
                 print(f"Warning: Target widget {widget} for flash is invalid or deleted.")
                 if timer.isActive(): timer.stop()
                 if widget == self.targetWidget: self.warningActive = False
                 return

            # Apply warning color to a modifiable copy
            flash_palette = QPalette(original_palette_ref) # Create a copy from the reference
            flash_palette.setColor(QPalette.ColorRole.Window, self.warningColor)
            widget.setPalette(flash_palette)
            widget.setAutoFillBackground(True) # Crucial
            widget.update() # Request repaint

            # Start the timer for resetting this specific widget
            timer.start(self.flashDurationMs)

        except RuntimeError as e:
            print(f"Error flashing widget {widget} (it might have been deleted): {e}")
            if timer.isActive(): timer.stop()
            if widget == self.targetWidget: self.warningActive = False


    def _reset_visual_warning(self):
        """Resets the main target widget background."""
        try:
            if self.targetWidget and self.targetWidget.isWindow():
                self.targetWidget.setPalette(self.originalPalette)
                self.targetWidget.update()
        except RuntimeError:
            print("Error resetting main target widget (already deleted?).")
        finally:
            self.warningActive = False # Always set flag to false


    def _reset_alternate_window_warning(self):
        """Resets the alternate warning window background."""
        try:
            if self.alternate_warning_window and self.alternate_warning_window.isWindow():
                 if self.alternate_window_original_palette:
                    self.alternate_warning_window.setPalette(self.alternate_window_original_palette)
                    self.alternate_warning_window.update()
                 else:
                      print("Warning: Original palette for alternate window missing on reset.")
        except RuntimeError:
            print("Error resetting alternate window (already deleted?).")


    def _destroy_alternate_window(self):
        """Safely closes and cleans up the alternate warning window."""
        if self.alternate_warning_window:
            print("Closing alternate warning window.")
            self.alternate_window_timer.stop()
            try:
                self.alternate_warning_window.destroyed.disconnect(self._handle_alternate_window_closed)
            except (TypeError, RuntimeError): pass
            try:
                if self.alternate_warning_window.isWindow():
                    self.alternate_warning_window.close()
            except RuntimeError:
                 print("Alternate window already deleted when trying to close.")
            self.alternate_warning_window = None
            self.alternate_window_original_palette = None


    def closeEvent(self, event):
        """Ensure alternate window is closed when the tab itself is closed."""
        print("Closing VisualWarningTab, ensuring alternate window is destroyed.")
        self._destroy_alternate_window()
        super().closeEvent(event)


# Example usage (remains the same)
if __name__ == '__main__':
    app = QApplication(sys.argv)

    main_window = QWidget()
    main_window.setWindowTitle("Main Target Window")
    main_window.setGeometry(100, 100, 400, 200)
    main_window.setStyleSheet("background-color: lightblue;")
    main_window.show()

    config = {
        'enableVisualCheck': 'True',
        'flashDurationMs': '750',
        'warningColor': '#ff8c00', # Dark Orange
        'useSeparateWindow': 'False' # Start with it unchecked
        # 'useSeparateWindow': 'True' # Or test starting checked
    }

    visual_tab = VisualWarningTab(main_window, config)
    visual_tab.setWindowTitle("Visual Warning Controls")
    visual_tab.setGeometry(550, 100, 350, 250)
    visual_tab.show()

    # --- How the parent would connect ---
    # Assume 'parent_window' is the window containing the tab and the save button
    # Assume 'save_button' is the QPushButton for saving
    # Assume 'enable_save_button' is a method in the parent window like:
    # def enable_save_button(self):
    #     self.save_button.setEnabled(True)
    #
    # In the parent window's __init__ or setupUi:
    # visual_tab.settingsChanged.connect(self.enable_save_button)
    # ------------------------------------


    # --- Example of triggering ---
    def test_trigger():
        print("Triggering warning...")
        visual_tab.trigger()

    test_button = QPushButton("Trigger Warning", main_window) # Put button on main window
    test_button.move(150, 80)
    test_button.clicked.connect(test_trigger)
    test_button.show() # Show the button itself

    # Clean up on exit
    app.aboutToQuit.connect(visual_tab.close) # Ensure closeEvent is called for the tab

    sys.exit(app.exec())
