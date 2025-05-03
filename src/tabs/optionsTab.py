import sounddevice as sd # Import sounddevice
import traceback # For error details
from PyQt6.QtWidgets import (QWidget, QGridLayout, QLabel, QComboBox, QLineEdit,
                             QSpinBox, QCheckBox, QPushButton, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt

class OptionsTab(QWidget):
    """
    Manages UI elements and logic for the 'Options' tab, including audio
    parameters (sample rate, frequency, etc.) and device selection.

    Handles output device selection changes internally and emits signals
    for status updates and general option changes.
    """
    # Signal emitted when any potentially savable option changes.
    # The boolean indicates if the current *audio parameters* are valid (True) or not (False).
    # Device changes will emit True, as they are always considered 'valid' changes to save.
    options_changed_signal = pyqtSignal(bool)

    # Signal emitted when the input device selection changes.
    input_device_changed_signal = pyqtSignal()

    # Signal to send status messages back to the main window's feedback label.
    status_update_signal = pyqtSignal(str)

    # REMOVED - Redundant signal
    # output_device_changed_signal = pyqtSignal()

    def __init__(self, inputDevices, outputDevices, configData, parent=None):
        """
        Initializes the OptionsTab.

        Args:
            inputDevices (list): List of available input device dictionaries from sounddevice.
            outputDevices (list): List of available output device dictionaries from sounddevice.
            configData (dict): Dictionary containing initial settings under 'options' and 'devices' keys.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent) 
        self._input_devices = inputDevices
        self._output_devices = outputDevices
        self._is_programmatic_change = False # Flag to block signals during setup

        # --- UI Elements ---
        self.inputSelector = QComboBox()
        self.outputSelector = QComboBox()
        self.sampleRateInput = QSpinBox()
        self.amplitudeInput = QLineEdit()
        self.frequencyInput = QLineEdit()
        self.durationInput = QLineEdit()
        self.autoSaveCheckBox = QCheckBox("Auto Save on Close")

        # Populate device selectors
        self._populate_device_selectors()

        # Configure inputs
        self.sampleRateInput.setRange(8000, 192000)
        self.sampleRateInput.setSuffix(" Hz")
        # Add placeholders or validators for float inputs if desired
        self.amplitudeInput.setPlaceholderText("0.0 to 1.0")
        self.frequencyInput.setPlaceholderText("e.g., 440")
        self.durationInput.setPlaceholderText("e.g., 0.2 (seconds)")

        # --- Layout ---
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Input Device:"), 0, 0)
        layout.addWidget(self.inputSelector, 0, 1, 1, 2)
        layout.addWidget(QLabel("Output Device:"), 1, 0)
        layout.addWidget(self.outputSelector, 1, 1, 1, 2)
        layout.addWidget(QLabel("Sample Rate:"), 2, 0)
        layout.addWidget(self.sampleRateInput, 2, 1)
        layout.addWidget(QLabel("Warning Amplitude:"), 3, 0)
        layout.addWidget(self.amplitudeInput, 3, 1)
        layout.addWidget(QLabel("Warning Frequency:"), 4, 0)
        layout.addWidget(self.frequencyInput, 4, 1)
        layout.addWidget(QLabel("Warning Duration:"), 5, 0)
        layout.addWidget(self.durationInput, 5, 1)
        layout.addWidget(self.autoSaveCheckBox, 6, 0, 1, 2)
        layout.setRowStretch(7, 1) # Add stretch at the bottom

        # --- Apply Initial Config ---
        initial_options = configData.get('options', {})
        initial_devices = configData.get('devices', {})
        self.set_values_from_dict(initial_options, initial_devices)

        # --- Connections ---
        # Connect internal validation first
        self.amplitudeInput.textChanged.connect(self._validate_audio_params)
        self.frequencyInput.textChanged.connect(self._validate_audio_params)
        self.durationInput.textChanged.connect(self._validate_audio_params)
        self.sampleRateInput.valueChanged.connect(self._validate_audio_params)

        # Connect changes to external signals
        self.inputSelector.currentIndexChanged.connect(self._emit_input_device_changed)
        # Connect output selector change to the internal handler
        self.outputSelector.currentIndexChanged.connect(self._handle_output_device_selection_changed)

        # Connect all controls to the general options changed signal emitter
        self.inputSelector.currentIndexChanged.connect(lambda: self.options_changed_signal.emit(True)) # Device change is valid
        self.outputSelector.currentIndexChanged.connect(lambda: self.options_changed_signal.emit(True)) # Device change is valid
        self.sampleRateInput.valueChanged.connect(self._validate_and_emit_options_changed)
        self.amplitudeInput.textChanged.connect(self._validate_and_emit_options_changed)
        self.frequencyInput.textChanged.connect(self._validate_and_emit_options_changed)
        self.durationInput.textChanged.connect(self._validate_and_emit_options_changed)
        self.autoSaveCheckBox.stateChanged.connect(self._validate_and_emit_options_changed) # Auto-save change is valid


    def _populate_device_selectors(self):
        """Fills the input and output device QComboBoxes."""
        self._is_programmatic_change = True
        self.inputSelector.clear()
        self.outputSelector.clear()

        if not self._input_devices:
            self.inputSelector.addItem("No Input Devices Found")
            self.inputSelector.setEnabled(False)
        else:
            for device in self._input_devices:
                # Prepend index for easier parsing later
                self.inputSelector.addItem(f"{device['index']}: {device['name']}")
            self.inputSelector.setEnabled(True)

        if not self._output_devices:
            self.outputSelector.addItem("No Output Devices Found")
            self.outputSelector.setEnabled(False)
        else:
            for device in self._output_devices:
                 # Prepend index for easier parsing later
                self.outputSelector.addItem(f"{device['index']}: {device['name']}")
            self.outputSelector.setEnabled(True)
        self._is_programmatic_change = False

    def _validate_audio_params(self):
        """
        Validates the format and range of audio parameter inputs (amplitude, freq, duration).
        Updates input field styles to indicate errors. Returns True if all are valid, False otherwise.
        """
        valid = True
        # --- Amplitude ---
        try:
            amp = float(self.amplitudeInput.text())
            if 0.0 <= amp <= 1.0:
                self.amplitudeInput.setStyleSheet("")
            else:
                self.amplitudeInput.setStyleSheet("color: red;")
                valid = False
        except ValueError:
            self.amplitudeInput.setStyleSheet("color: red;")
            valid = False

        # --- Frequency ---
        try:
            freq = float(self.frequencyInput.text())
            if freq > 0:
                self.frequencyInput.setStyleSheet("")
            else:
                self.frequencyInput.setStyleSheet("color: red;")
                valid = False
        except ValueError:
            self.frequencyInput.setStyleSheet("color: red;")
            valid = False

        # --- Duration ---
        try:
            dur = float(self.durationInput.text())
            if dur > 0:
                self.durationInput.setStyleSheet("")
            else:
                self.durationInput.setStyleSheet("color: red;")
                valid = False
        except ValueError:
            self.durationInput.setStyleSheet("color: red;")
            valid = False

        # Sample rate is handled by QSpinBox range

        return valid

    def _validate_and_emit_options_changed(self):
        """Validates audio params and emits the options_changed_signal with the validity status."""
        if self._is_programmatic_change:
            return
        is_valid = self._validate_audio_params()
        self.options_changed_signal.emit(is_valid)

    def _emit_input_device_changed(self):
        """Emits the specific signal for input device changes."""
        if self._is_programmatic_change:
            return
        self.input_device_changed_signal.emit()
        # Also emit general options changed signal
        self.options_changed_signal.emit(True)


    def _handle_output_device_selection_changed(self):
        """
        Handles changes in the output device selection QComboBox.
        Updates the sounddevice default output device and emits status updates.
        """
        if self._is_programmatic_change:
            return

        device_text = self.get_selected_output_device_text()
        if not device_text:
            self.status_update_signal.emit("Status: No Output Device selected.")
            return

        try:
            # Extract only the numeric index part
            device_index_str = device_text.split(" ")[0].split("(")[0]
            output_device_index = int(device_index_str)
        except (ValueError, IndexError, TypeError):
            error_msg = f"Status: Error parsing output device index from '{device_text}'."
            self.status_update_signal.emit(error_msg)
            print(f"Output device change aborted: Invalid device text format '{device_text}'. Could not parse index '{device_index_str}'.")
            return

        try:
            # Determine the current default input device index
            current_input_device_index = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else None
            if current_input_device_index is None:
                 try:
                     # Query for the default input device index
                     default_input_info = sd.query_devices(kind='input')
                     if default_input_info and isinstance(default_input_info, dict):
                         current_input_device_index = default_input_info['index']
                     elif isinstance(default_input_info, list) and default_input_info:
                          current_input_device_index = default_input_info[0]['index']
                 except Exception as query_e:
                     print(f"Could not query default input device index: {query_e}")
                     # Proceed without default input index if query fails

            # Set the default device tuple (Input, Output)
            if current_input_device_index is not None:
                sd.default.device = (current_input_device_index, output_device_index)
                print(f"Set sd.default.device to (Input: {current_input_device_index}, Output: {output_device_index})")
            else:
                # Fallback if input couldn't be determined - might cause issues
                sd.default.device = (None, output_device_index)
                print(f"Warning: Set sd.default.device to output only: {output_device_index}. Input device index unknown.")

            self.status_update_signal.emit(f"Status: Output device set to '{device_text}'")
            # Emit general options changed signal (valid change)
            self.options_changed_signal.emit(True)
            print(f"Output device changed to {output_device_index} ('{device_text}')")

        except sd.PortAudioError as pae:
            error_msg = f"Status: PortAudio Error setting output - {pae}"
            self.status_update_signal.emit(error_msg)
            print(f"PortAudioError setting output device: {pae}")
        except ValueError as ve: # Catch specific errors like invalid device index
             error_msg = f"Status: Value Error setting output - {ve}"
             self.status_update_signal.emit(error_msg)
             print(f"ValueError setting output device (invalid index?): {ve}")
        except Exception as e:
            error_msg = f"Status: Error setting output - {e}"
            self.status_update_signal.emit(error_msg)
            print(f"Error setting output device: {e}\n{traceback.format_exc()}")


    def get_selected_input_device_text(self):
        """Returns the text of the currently selected input device."""
        return self.inputSelector.currentText() if self.inputSelector.isEnabled() else None

    def get_selected_output_device_text(self):
        """Returns the text of the currently selected output device."""
        return self.outputSelector.currentText() if self.outputSelector.isEnabled() else None

    def is_auto_save_enabled(self):
        """Returns True if the 'Auto Save on Close' checkbox is checked."""
        return self.autoSaveCheckBox.isChecked()

    def validate_and_get_options(self):
        """
        Validates current audio parameters and returns them if valid.

        Returns:
            tuple: (bool, dict)
                   - bool: True if parameters are valid, False otherwise.
                   - dict: Dictionary of parameter values if valid, empty dict otherwise.
                           Keys: 'samplerate', 'amplitude', 'frequency', 'duration'.
        """
        if not self._validate_audio_params():
            return False, {}

        try:
            options = {
                'samplerate': self.sampleRateInput.value(),
                'amplitude': float(self.amplitudeInput.text()),
                'frequency': float(self.frequencyInput.text()),
                'duration': float(self.durationInput.text())
            }
            return True, options
        except ValueError:
            # This case should theoretically be caught by _validate_audio_params, but added for safety
            return False, {}

    def get_config_values(self):
        """
        Returns the current state of the UI controls as two dictionaries
        suitable for saving to the configuration file.

        Returns:
            tuple: (dict, dict)
                   - dict: Settings related to audio options ('options' section).
                   - dict: Settings related to device selection ('devices' section).
        """
        options_config = {
            "sampleRate": str(self.sampleRateInput.value()),
            "amplitude": self.amplitudeInput.text(),
            "frequency": self.frequencyInput.text(),
            "duration": self.durationInput.text(),
            "autoSave": str(self.autoSaveCheckBox.isChecked())
        }
        devices_config = {
            "inputDevice": self.get_selected_input_device_text() or "", # Use empty string if None
            "outputDevice": self.get_selected_output_device_text() or "" # Use empty string if None
        }
        return options_config, devices_config

    def set_values_from_dict(self, options_settings, devices_settings):
        """
        Applies settings from dictionaries to the UI controls in this tab.

        Args:
            options_settings (dict): Dictionary for the 'options' section.
            devices_settings (dict): Dictionary for the 'devices' section.
        """
        print(f"OptionsTab applying settings: Options={options_settings}, Devices={devices_settings}")
        self._is_programmatic_change = True
        try:
            # --- Apply Device Settings ---
            input_device_text = devices_settings.get('inputDevice')
            output_device_text = devices_settings.get('outputDevice')

            input_index = self.inputSelector.findText(input_device_text, Qt.MatchFlag.MatchStartsWith)
            if input_index != -1:
                self.inputSelector.setCurrentIndex(input_index)
            elif self.inputSelector.count() > 0:
                 self.inputSelector.setCurrentIndex(0) # Default to first if not found or empty

            output_index = self.outputSelector.findText(output_device_text, Qt.MatchFlag.MatchStartsWith)
            if output_index != -1:
                self.outputSelector.setCurrentIndex(output_index)
            elif self.outputSelector.count() > 0:
                 self.outputSelector.setCurrentIndex(0) # Default to first if not found or empty

            # --- Apply Option Settings ---
            try:
                sr = int(options_settings.get('sampleRate', 44100)) # Default 44100
                # Clamp value to spinbox range
                sr = max(self.sampleRateInput.minimum(), min(sr, self.sampleRateInput.maximum()))
                self.sampleRateInput.setValue(sr)
            except (ValueError, TypeError):
                self.sampleRateInput.setValue(44100) # Fallback default

            self.amplitudeInput.setText(options_settings.get('amplitude', '0.5')) # Default 0.5
            self.frequencyInput.setText(options_settings.get('frequency', '440')) # Default 440
            self.durationInput.setText(options_settings.get('duration', '0.2'))   # Default 0.2

            self.autoSaveCheckBox.setChecked(options_settings.get('autoSave', 'True').lower() == 'true') # Default True

            # Validate styles after setting text
            self._validate_audio_params()

        except Exception as e:
            print(f"Error applying settings to OptionsTab: {e}\n{traceback.format_exc()}")
        finally:
            self._is_programmatic_change = False