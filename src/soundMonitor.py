import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QTabWidget, QPushButton, QMessageBox, QApplication)
from PyQt6.QtCore import pyqtSignal
import traceback

# Import Setup Utilities
from appSetup import discover_audio_devices, load_initial_configuration

# Import Tabs
from tabs.mainTab import MainTab
from tabs.visualWarningTab import VisualWarningTab
from tabs.optionsTab import OptionsTab
import configHandler


class micMonitorWindow(QMainWindow):
    """
    Main application window for the Microphone Guardian.

    Manages the overall UI structure including tabs for different settings,
    handles audio stream setup and processing, coordinates interactions
    between tabs, and manages configuration loading/saving. Delegates device
    change handling to the OptionsTab.
    """
    warning_needed = pyqtSignal()
    volume_level_updated = pyqtSignal(int) # Signal to safely pass volume level

    def __init__(self):
        """
        Initializes the main window, sets up UI components, loads configuration,
        initializes audio devices, connects signals, and starts the audio stream.
        """
        super().__init__()
        self._is_programmatic_change = False
        self.setWindowTitle("Microphone Guardian")
        self.setGeometry(500, 120, 400, 300)

        # --- Internal State ---
        self.stream = None
        self.current_audio_options = {}
        self._current_gain = 100
        self._current_threshold = 50
        self._trigger_enabled = True
        self._mute_enabled = False
        self.samplerate = 0
        self.amplitude = 0
        self.frequency = 0
        self.duration = 0

        # --- Device Discovery ---
        self.inputDevices, self.outputDevices, device_error = discover_audio_devices()
        if device_error:
            QMessageBox.critical(self, "Audio Device Error", device_error)
            self.inputDevices = []
            self.outputDevices = []

        # --- Load Configuration ---
        config_bundle = load_initial_configuration()
        initial_main_settings = config_bundle['main']
        initial_visual_settings = config_bundle['visual']
        initial_options_settings = config_bundle['options']
        initial_devices_settings = config_bundle['devices']
        status_message = config_bundle['status_message']

        # --- Instantiate Tab Widgets ---
        self.mainTab = MainTab(configData=initial_main_settings, parent=self)
        self.visualWarningTab = VisualWarningTab(
            targetWidget=self,
            configData=initial_visual_settings,
            parent=self
        )
        self.optionsTab = OptionsTab(
            inputDevices=self.inputDevices,
            outputDevices=self.outputDevices,
            configData={'options': initial_options_settings, 'devices': initial_devices_settings},
            parent=self
        )

        # --- Status Label ---
        self.feedbackLabel = QLabel(status_message)
        self.feedbackLabel.setFixedHeight(15)

        # --- Tabs Setup ---
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.mainTab, "Main")
        self.tab_widget.addTab(self.optionsTab, "Options")
        self.tab_widget.addTab(self.visualWarningTab, "Visual Warning")

        # --- Main Layout ---
        centralWidget = QWidget()
        centralLayout = QVBoxLayout(centralWidget)
        centralLayout.addWidget(self.tab_widget)
        centralLayout.addWidget(self.feedbackLabel)

        buttonsLayout = QHBoxLayout()
        self.saveButton = QPushButton("Save Settings")
        self.cancelButton = QPushButton("Cancel Changes")
        buttonsLayout.addStretch()
        buttonsLayout.addWidget(self.saveButton)
        buttonsLayout.addWidget(self.cancelButton)
        centralLayout.addLayout(buttonsLayout)

        self.setCentralWidget(centralWidget)

        # --- Connections ---
        self.warning_needed.connect(self.handle_warning_trigger)
        self.volume_level_updated.connect(self._handle_volume_update)

        # Connect signals from tabs
        self.mainTab.settings_changed.connect(lambda: self.setChanged(True))
        self.mainTab.gain_changed.connect(self._update_thread_safe_params)
        self.mainTab.threshold_changed.connect(self._update_thread_safe_params)
        self.mainTab.trigger_enabled_changed.connect(self._update_thread_safe_params)
        self.mainTab.mute_enabled_changed.connect(self._update_thread_safe_params)

        # Connect OptionsTab signals
        self.optionsTab.options_changed_signal.connect(self.handle_options_changed) # Handles validity and setChanged
        self.optionsTab.input_device_changed_signal.connect(self.restartInput)
        # Connect the new status update signal
        self.optionsTab.status_update_signal.connect(self._update_status_label)

        # Connect VisualTab signals
        self.visualWarningTab.enable_check.stateChanged.connect(lambda: self.setChanged(True))
        self.visualWarningTab.flash_duration_input.valueChanged.connect(lambda: self.setChanged(True))

        # Connect Buttons
        self.saveButton.clicked.connect(self.updateConfigs)
        self.cancelButton.clicked.connect(self.retrieveConfigs)

        # --- Final Initialization ---
        self._update_thread_safe_params()

        is_valid, self.current_audio_options = self.optionsTab.validate_and_get_options()
        if not is_valid:
            if config_bundle['load_ok']:
                 self.feedbackLabel.setText(status_message + " Warning: Invalid audio options.")
            else:
                 self.feedbackLabel.setText("Status: Warning - Invalid audio options loaded.")
        else:
            self._update_internal_audio_params()
            # Start stream only if devices were found and options are valid
            if self.inputDevices:
                self.restartInput()
            else:
                self.feedbackLabel.setText("Status: No input devices found. Cannot start monitoring.")


        self._is_programmatic_change = True
        self.setChanged(False)
        self._is_programmatic_change = False

    def _update_status_label(self, message):
        """Slot to update the feedback label text."""
        self.feedbackLabel.setText(message)

    def setChanged(self, isChanged):
        """
        Enables or disables the Save and Cancel buttons based on UI changes.

        Prevents enabling buttons during programmatic changes (e.g., loading config).

        Args:
            isChanged (bool): True if a user change occurred, False otherwise.
        """
        if self._is_programmatic_change and isChanged:
            return
        self.saveButton.setEnabled(isChanged)
        self.cancelButton.setEnabled(isChanged)

    def updateConfigs(self):
        """
        Gathers current settings from all tabs and saves them using configHandler.
        """
        print("Gathering UI state for saving...")
        try:
            main_settings = self.mainTab.get_config_values()
            visual_settings = self.visualWarningTab.get_config_values()
            options_settings, devices_settings = self.optionsTab.get_config_values()

            current_settings = {
                "main": main_settings,
                "options": options_settings,
                "devices": devices_settings,
                "visual": visual_settings
            }
            success, message = configHandler.save_config(current_settings)
            self.feedbackLabel.setText(message)
            if success:
                self.setChanged(False)
        except Exception as e:
            print(f"Error gathering or saving settings: {e}\n{traceback.format_exc()}")
            self.feedbackLabel.setText(f"Status: Error saving settings: {e}")


    def retrieveConfigs(self):
        """
        Loads settings from the configuration file and re-applies them to the UI,
        effectively cancelling any unsaved user changes.
        """
        print("Retrieving configuration (Cancel pressed)...")
        self._is_programmatic_change = True

        config_bundle = load_initial_configuration()
        settings = {
            'main': config_bundle['main'],
            'visual': config_bundle['visual'],
            'options': config_bundle['options'],
            'devices': config_bundle['devices']
        }
        self.feedbackLabel.setText(config_bundle['status_message'])

        if not config_bundle['load_ok'] and not settings['main'] and not settings['options']:
            print("Error: No settings loaded from config_handler. Cannot apply to UI.")
            self._is_programmatic_change = False
            return

        try:
            self.mainTab.set_values_from_dict(config_bundle['main'])
            self.optionsTab.set_values_from_dict(config_bundle['options'], config_bundle['devices'])

            visual_settings = config_bundle['visual']
            self.visualWarningTab.setEnabled(visual_settings.get('enableVisualCheck', 'True').lower() == 'true')
            try:
                duration_ms = int(visual_settings.get('flashDurationMs', '300'))
                self.visualWarningTab.setFlashDuration(duration_ms)
            except (ValueError, TypeError):
                 self.visualWarningTab.setFlashDuration(300)

            is_valid, self.current_audio_options = self.optionsTab.validate_and_get_options()
            if is_valid:
                self._update_internal_audio_params()
                old_samplerate = self.samplerate
                new_samplerate = self.current_audio_options.get('samplerate', 0)
                # Restart stream only if devices are available and sample rate changed
                if self.inputDevices and new_samplerate > 0 and new_samplerate != old_samplerate:
                    print("Sample rate changed during config reload, restarting input stream.")
                    self.restartInput()
                elif not self.inputDevices:
                     self.feedbackLabel.setText("Status: No input devices found. Cannot start monitoring.")

            else:
                if config_bundle['load_ok']:
                     self.feedbackLabel.setText(config_bundle['status_message'] + " Warning: Invalid audio options.")
                else:
                     self.feedbackLabel.setText("Status: Warning - Invalid audio options loaded.")

            self._update_thread_safe_params()

        except Exception as e:
            print(f"Error applying loaded settings (retrieveConfigs): {e}\n{traceback.format_exc()}")
            self.feedbackLabel.setText(f"Status: Error applying settings: {e}")
        finally:
            self.setChanged(False)
            self._is_programmatic_change = False
            print("Finished retrieving configuration (Cancel pressed).")

    def handle_options_changed(self, is_valid):
        """
        Handles the options_changed_signal from the OptionsTab.

        Updates internal audio parameters if the new options are valid and
        restarts the audio stream if the sample rate has changed. Also enables
        Save/Cancel buttons.

        Args:
            is_valid (bool): Indicates whether the audio parameters are valid.
                             Device changes always emit True.
        """
        self.setChanged(True) # Enable Save/Cancel on any change reported by OptionsTab

        if is_valid:
            is_valid_check, new_options = self.optionsTab.validate_and_get_options()
            if is_valid_check: # Double check validity before using options
                 old_samplerate = self.samplerate
                 self.current_audio_options = new_options
                 self._update_internal_audio_params()
                 new_samplerate = self.current_audio_options.get('samplerate', 0)

                 # Restart stream only if sample rate actually changed and devices exist
                 if self.inputDevices and new_samplerate > 0 and new_samplerate != old_samplerate:
                     print("Sample rate changed, restarting input stream.")
                     self.restartInput()
                 elif not self.inputDevices:
                      self.feedbackLabel.setText("Status: No input devices found. Cannot restart stream.")


    def _update_internal_audio_params(self):
        """
        Updates the main window's internal audio parameters (samplerate, amplitude, etc.)
        based on the currently validated options from the OptionsTab.
        """
        if self.current_audio_options:
            self.samplerate = self.current_audio_options.get('samplerate', self.samplerate)
            self.amplitude = self.current_audio_options.get('amplitude', 0)
            self.frequency = self.current_audio_options.get('frequency', 0)
            self.duration = self.current_audio_options.get('duration', 0)
            print(f"Internal audio params updated: SR={self.samplerate}, Amp={self.amplitude}, Freq={self.frequency}, Dur={self.duration}")

    def _update_thread_safe_params(self):
        """
        Updates the internal, thread-safe copies of gain, threshold, trigger enable,
        and mute enable status based on the current state of the MainTab.
        This should be called whenever these values change in the UI.
        """
        self._current_gain = self.mainTab.get_gain()
        self._current_threshold = self.mainTab.get_threshold()
        self._trigger_enabled = self.mainTab.is_trigger_enabled()
        self._mute_enabled = self.mainTab.is_mute_enabled()

    def stop_stream(self):
        """
        Stops and closes the active audio input stream, if it exists.
        """
        if self.stream:
            try:
                if self.stream.active:
                    self.stream.stop()
                self.stream.close()
                print("Audio stream stopped and closed.")
            except Exception as e:
                print(f"Warning: Error stopping/closing stream: {e}")
            finally:
                self.stream = None

    def restartInput(self):
        """
        Stops any existing audio stream and starts a new InputStream
        using the currently selected input device and sample rate.
        Includes robust parsing for the device index.
        """
        self.stop_stream()

        if self.samplerate <= 0:
            self.feedbackLabel.setText("Status: Cannot start stream - Invalid Sample Rate.")
            print("Stream start aborted: Invalid sample rate.")
            return

        device_text = self.optionsTab.get_selected_input_device_text()
        if not device_text:
             self.feedbackLabel.setText("Status: Cannot start stream - No Input Device selected.")
             print("Stream start aborted: No input device selected.")
             return

        # Explicitly check for the placeholder text
        if "No Input Devices Found" in device_text:
            self.feedbackLabel.setText("Status: Cannot start stream - No Input Device selected/available.")
            print("Stream start aborted: 'No Input Devices Found' selected.")
            return

        device_index = -1 # Initialize with invalid index
        try:
            # Split at the first colon and take the part before it
            device_index_str = device_text.split(':', 1)[0].strip()
            device_index = int(device_index_str)
        except (ValueError, IndexError, TypeError):
            # Use the actual device_text in the error message
            error_msg = f"Status: Error parsing input device index from '{device_text}'."
            self.feedbackLabel.setText(error_msg)
            # Log the problematic string and the attempted parse result
            print(f"Stream start aborted: Invalid device text format. Text='{device_text}', Parsed Index String='{device_index_str if 'device_index_str' in locals() else 'N/A'}'")
            return

        # Proceed only if device_index is valid (>= 0)
        if device_index < 0:
             error_msg = f"Status: Invalid device index ({device_index}) parsed from '{device_text}'."
             self.feedbackLabel.setText(error_msg)
             print(f"Stream start aborted: Parsed index {device_index} is invalid.")
             return

        # --- Start Stream Logic (remains the same) ---
        try:
            print(f"Attempting to start input stream on device {device_index} ('{device_text}') with SR={self.samplerate}")
            current_output_device_index = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) and len(sd.default.device) > 1 else None
            if current_output_device_index is None:
                 try:
                     default_output_info = sd.query_devices(kind='output')
                     if default_output_info and isinstance(default_output_info, dict):
                         current_output_device_index = default_output_info['index']
                     elif isinstance(default_output_info, list) and default_output_info:
                         current_output_device_index = default_output_info[0]['index']
                 except Exception as query_e:
                     print(f"Could not query default output device index during restart: {query_e}")

            if current_output_device_index is not None:
                sd.default.device = (device_index, current_output_device_index)
                print(f"Set sd.default.device to (Input: {device_index}, Output: {current_output_device_index})")
            else:
                 sd.default.device = device_index
                 print(f"Set sd.default.device to input only: {device_index} (Output device index unknown)")

            self.stream = sd.InputStream(
                callback=self.ListenToMic,
                samplerate=self.samplerate,
                device=device_index,
                dtype='float32'
            )
            self.stream.start()
            self.feedbackLabel.setText(f"Status: Monitoring '{device_text}'")
            print("Input stream started successfully.")

        except sd.PortAudioError as pae:
            self.feedbackLabel.setText(f"Status: PortAudio Error starting stream - {pae}")
            print(f"PortAudioError starting stream: {pae}")
            self.stream = None
        except ValueError as ve:
             self.feedbackLabel.setText(f"Status: Value Error starting stream - {ve}")
             print(f"ValueError starting stream (invalid device index?): {ve}")
             self.stream = None
        except Exception as e:
            self.feedbackLabel.setText(f"Status: Error starting stream - {e}")
            print(f"Error starting stream: {e}\n{traceback.format_exc()}")
            self.stream = None


    def ListenToMic(self, indata, frames, time, status):
        """
        Audio callback function executed by sounddevice in a separate thread.

        Processes incoming audio data, applies gain, calculates volume level,
        and checks if the trigger threshold is exceeded. Emits `warning_needed`
        signal if the threshold is met and triggering is enabled. Emits
        `volume_level_updated` signal with the calculated level.

        Uses thread-safe copies of gain, threshold, and trigger status
        (`_current_gain`, `_current_threshold`, `_trigger_enabled`).

        Args:
            indata (numpy.ndarray): Input audio buffer.
            frames (int): Number of frames in the buffer.
            time (CData): Timing information.
            status (sounddevice.CallbackFlags): Status flags (e.g., overflow).
        """
        if status:
            if status.input_overflow:
                print("Warning: Input overflow detected", file=sys.stderr)
            if status.input_underflow:
                 print("Warning: Input underflow detected", file=sys.stderr)

        try:
            gain_factor = self._current_gain / 100.0
            threshold_level = self._current_threshold
            is_trigger_on = self._trigger_enabled

            amplified_data = indata * gain_factor
            if np.any(amplified_data):
                volume_rms = np.sqrt(np.mean(amplified_data**2))
            else:
                volume_rms = 0

            scaling_factor = 300
            calculated_level = min(int(volume_rms * scaling_factor), 100)

            self.volume_level_updated.emit(calculated_level)

            if is_trigger_on and calculated_level >= threshold_level:
                self.warning_needed.emit()

        except Exception as e:
            print(f"Error in ListenToMic callback: {e}\n{traceback.format_exc()}", file=sys.stderr)

    def _handle_volume_update(self, level):
        """
        Slot executed in the main GUI thread to update the volume level display.

        Calls the MainTab's update method directly.

        Args:
            level (int): The volume level calculated by the audio callback.
        """
        self.mainTab.update_volume_bar(level, self._current_threshold)


    def handle_warning_trigger(self):
        """
        Slot executed in the main GUI thread when `warning_needed` signal is emitted.

        Plays an audio warning (if not muted and parameters are valid) using the
        selected output device and triggers the visual warning effect. Uses the
        thread-safe `_mute_enabled` flag.
        """
        if not self._mute_enabled:
            if self.amplitude > 0 and self.duration > 0 and self.samplerate > 0 and self.frequency > 0:
                device_text = self.optionsTab.get_selected_output_device_text()
                device_index = None
                if device_text and "No Output Devices Found" not in device_text: # Check placeholder
                    try:
                        # Use robust parsing for output device index as well
                        device_index_str = device_text.split(':', 1)[0].strip()
                        device_index = int(device_index_str)
                    except (ValueError, IndexError, TypeError):
                        print(f"Error: Invalid output device format ('{device_text}') for warning sound. Using default.")
                        device_index = None
                else:
                    # Handle case where "No Output Devices Found" is selected or text is invalid
                    if device_text: print(f"Warning: Cannot play sound on '{device_text}'. Using default output.")
                    device_index = None


                try:
                    t = np.linspace(0., self.duration, int(self.samplerate * self.duration), endpoint=False)
                    waveform = self.amplitude * np.sin(2. * np.pi * self.frequency * t, dtype=np.float32)
                    sd.play(waveform, self.samplerate, device=device_index, blocking=False)
                except sd.PortAudioError as pae:
                    print(f"PortAudioError playing warning: {pae}", file=sys.stderr)
                    self._update_status_label(f"Status: Audio Warning Error - {pae}")
                except ValueError as ve:
                     print(f"ValueError playing warning: {ve}", file=sys.stderr)
                     self._update_status_label(f"Status: Audio Warning Error - {ve}")
                except Exception as e:
                    print(f"Error generating or playing warning sound: {e}", file=sys.stderr)
                    self._update_status_label(f"Status: Audio Warning Error - {e}")
            else:
                pass

        self.visualWarningTab.trigger()


    def closeEvent(self, event):
        """
        Handles the window closing event.

        Stops the audio stream, optionally saves settings if
        auto-save is enabled, and accepts the close event.

        Args:
            event (QCloseEvent): The close event object.
        """
        print("Closing application...")
        self.stop_stream()
        if self.optionsTab.is_auto_save_enabled():
            print("Auto-saving settings on close...")
            self.updateConfigs()
        print("Cleanup finished.")
        event.accept()

# __main__ block remains the same...
if __name__ == "__main__":
    try:
        print("Starting Microphone Guardian...")
        app = QApplication(sys.argv)
        listenerWindow = micMonitorWindow()
        listenerWindow.show()
        exit_code = app.exec()
    except Exception as e:
        print(f"FATAL ERROR during application startup or execution: {e}")
        traceback.print_exc()
        exit_code = 1
    finally:
        sys.exit(exit_code)