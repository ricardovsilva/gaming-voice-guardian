import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QColor # Keep QPalette, QColor here for now if needed elsewhere
import os

from visual_warning import VisualWarningHandler
import config_handler


#
#         __o
#       _ \<_
#      (_)/(_)
# ```````

# TODO
# github workflow setup
# custom sound
# GUI aestetich improvement
# bug when closing application DONE
# max value monitoring
# automatic gain
# possibility to run custom script


class micMonitorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.isChangedByUser = False
        self.setWindowTitle("Microphone Guardian")
        self.setGeometry(500, 120, 400, 280) # Adjusted height slightly for tabs

        # --- Instantiate Visual Warning Handler ---
        # Pass self (the main window) as the target widget
        self.visual_warning_handler = VisualWarningHandler(self)

        # --- Device Setup ---
        # Query devices early to populate lists, but selection happens during retrieveConfigs
        try:
            all_devices = sd.query_devices()
            self.inputDevices = [dev for dev in all_devices if dev["max_input_channels"] > 0]
            self.outputDevices = [dev for dev in all_devices if dev["max_output_channels"] > 0]
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            # Handle the error gracefully, maybe show a message?
            QMessageBox.critical(self, "Audio Device Error", f"Could not query audio devices: {e}")
            self.inputDevices = []
            self.outputDevices = []
            # Consider exiting or disabling audio features if devices are crucial

        # --- Main Tab Widgets ---
        configBoxSize = 50

        self.volumeBar = QProgressBar()
        self.volumeBar.setTextVisible(False)
        self.volumeBar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid grey;
                border-radius: 1px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: green; /* Will be updated based on threshold */
            }
        """
        )

        self.thresholdSlider = QSlider(Qt.Orientation.Horizontal)
        # Initial value set during retrieveConfigs
        self.thresholdSlider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                border: 1px solid #bbb; /* Add border for definition */
                background: #ddd; /* Lighter grey background */
                height: 8px; /* Make the groove visible */
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal { /* Style the part before the handle */
                background: #66c2ff; /* Light blue fill */
                border: 1px solid #44a4ee;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal { /* Style the part after the handle */
                 background: #ddd; /* Match groove background */
                 border: 1px solid #bbb;
                 height: 8px;
                 border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc); /* System-like gradient */
                border: 1px solid #777;
                width: 16px; /* Slightly wider handle */
                margin: -4px 0; /* Adjust vertical margin to center on groove */
                border-radius: 8px; /* Rounded handle */
            }
        """
        )

        self.thresholdBox = QLineEdit() # Initial value set during retrieveConfigs
        self.thresholdBox.setMaximumWidth(configBoxSize)
        self.thresholdLabel = QLabel("- Trigger Threshold")

        self.volumeKnob = QDial() # Initial value set during retrieveConfigs

        self.gainBox = QLineEdit() # Initial value set during retrieveConfigs
        self.gainBox.setMaximumWidth(configBoxSize)
        self.gainLabel = QLabel("- Mic Sensitivity (Gain)")

        self.triggerCheck = QCheckBox("Enable Trigger") # Initial state set during retrieveConfigs
        self.muteAudioCheck = QCheckBox("Mute Audio Warning") # Initial state set during retrieveConfigs

        self.saveMainButton = QPushButton("Save Settings")
        self.cancelMainButton = QPushButton("Cancel Changes")

        # --- Options Tab Widgets ---
        self.frequencyLabel = QLabel("- Frequency (Hz)")
        self.frequencyBox = QLineEdit() # Initial value set during retrieveConfigs
        self.frequencyBox.setMaximumWidth(configBoxSize)

        self.durationLabel = QLabel("- Duration (s)")
        self.durationBox = QLineEdit() # Initial value set during retrieveConfigs
        self.durationBox.setMaximumWidth(configBoxSize)

        self.sampleRateLabel = QLabel("- Sample Rate (Hz)")
        self.sampleRateBox = QLineEdit() # Initial value set during retrieveConfigs
        self.sampleRateBox.setMaximumWidth(configBoxSize + 10)

        self.amplitudeLabel = QLabel("- Amplitude (0.0-1.0)")
        self.amplitudeBox = QLineEdit() # Initial value set during retrieveConfigs
        self.amplitudeBox.setMaximumWidth(configBoxSize)

        self.inputSelector = QComboBox()
        self.inputSelector.addItems(
            [f"{dev['index']:02d} {dev['name']}" for dev in self.inputDevices]
        )
        # Initial selection happens during retrieveConfigs

        self.outputSelector = QComboBox()
        self.outputSelector.addItems(
            [f"{dev['index']:02d} {dev['name']}" for dev in self.outputDevices]
        )
        # Initial selection happens during retrieveConfigs

        self.saveOptionsButton = QPushButton("Save Settings")
        self.cancelOptionsButton = QPushButton("Cancel Changes")

        # --- Visual Warning Tab Widgets ---
        self.enableVisualCheck = QCheckBox("Enable Visual Warning (Flash Background)") # Initial state set during retrieveConfigs
        self.flashDurationLabel = QLabel("Flash Duration (ms):")
        self.flashDurationInput = QSpinBox()
        self.flashDurationInput.setRange(50, 5000)  # Set reasonable min/max duration
        self.flashDurationInput.setSingleStep(50)   # Step by 50ms
        self.flashDurationInput.setMaximumWidth(100)  # Control width
        self.saveVisualButton = QPushButton("Save Settings")
        self.cancelVisualButton = QPushButton("Cancel Changes")


        # --- Status Label ---
        self.feedbackLabel = QLabel("Status: Initializing...") # Initial status
        self.feedbackLabel.setFixedHeight(15)


        # --- Layouts ---
        # (Layout setup remains the same as before)

        # Main Tab Layout
        self.mainLayout = QGridLayout() # Renamed from parentGrid for clarity
        gainLayout = QHBoxLayout()
        thresholdLayout = QHBoxLayout()
        triggerControlLayout = QVBoxLayout() # Keep audio controls here

        gainLayout.addWidget(self.gainBox, 0, Qt.AlignmentFlag.AlignLeft)
        gainLayout.addWidget(self.gainLabel, 1, Qt.AlignmentFlag.AlignLeft)

        thresholdLayout.addWidget(self.thresholdBox, 0, Qt.AlignmentFlag.AlignLeft)
        thresholdLayout.addWidget(self.thresholdLabel, 1, Qt.AlignmentFlag.AlignLeft)

        triggerControlLayout.addWidget(self.triggerCheck)
        triggerControlLayout.addWidget(self.muteAudioCheck)
        triggerControlLayout.addStretch() # Push controls to top

        self.mainLayout.addWidget(self.volumeBar, 0, 0, 1, 3)
        self.mainLayout.addWidget(self.thresholdSlider, 1, 0, 1, 3) # Slider is here
        self.mainLayout.addWidget(self.volumeKnob, 2, 0, 2, 1)
        self.mainLayout.addLayout(thresholdLayout, 2, 1)
        self.mainLayout.addLayout(gainLayout, 3, 1)
        self.mainLayout.addLayout(triggerControlLayout, 2, 2, 2, 1)

        mainButtonLayout = QHBoxLayout()
        mainButtonLayout.addWidget(self.saveMainButton)
        mainButtonLayout.addStretch()
        mainButtonLayout.addWidget(self.cancelMainButton)
        self.mainLayout.addLayout(mainButtonLayout, 4, 0, 1, 3)

        # Options Tab Layout
        self.optionsLayout = QGridLayout()
        self.optionsLayout.addWidget(self.frequencyBox, 0, 0)
        self.optionsLayout.addWidget(self.frequencyLabel, 0, 1)
        self.optionsLayout.addWidget(self.sampleRateBox, 0, 2)
        self.optionsLayout.addWidget(self.sampleRateLabel, 0, 3)

        self.optionsLayout.addWidget(self.durationBox, 1, 0)
        self.optionsLayout.addWidget(self.durationLabel, 1, 1)
        self.optionsLayout.addWidget(self.amplitudeBox, 1, 2)
        self.optionsLayout.addWidget(self.amplitudeLabel, 1, 3)

        self.optionsLayout.addWidget(QLabel("Input Device:"), 2, 0, 1, 4)
        self.optionsLayout.addWidget(self.inputSelector, 3, 0, 1, 4)
        self.optionsLayout.addWidget(QLabel("Output Device:"), 4, 0, 1, 4)
        self.optionsLayout.addWidget(self.outputSelector, 5, 0, 1, 4)

        optionsButtonLayout = QHBoxLayout()
        optionsButtonLayout.addWidget(self.saveOptionsButton)
        optionsButtonLayout.addStretch()
        optionsButtonLayout.addWidget(self.cancelOptionsButton)
        self.optionsLayout.addLayout(optionsButtonLayout, 6, 0, 1, 4)
        self.optionsLayout.setRowStretch(7, 1)

        # Visual Warning Tab Layout
        self.visualLayout = QVBoxLayout()
        self.visualLayout.addWidget(self.enableVisualCheck)
        
        # Add duration controls in a horizontal layout
        durationLayout = QHBoxLayout()
        durationLayout.addWidget(self.flashDurationLabel)
        durationLayout.addWidget(self.flashDurationInput)
        durationLayout.addStretch()  # Push controls to the left
        self.visualLayout.addLayout(durationLayout)
        
        self.visualLayout.addStretch()
        visualButtonLayout = QHBoxLayout()
        visualButtonLayout.addWidget(self.saveVisualButton)
        visualButtonLayout.addStretch()
        visualButtonLayout.addWidget(self.cancelVisualButton)
        self.visualLayout.addLayout(visualButtonLayout)


        # --- Tabs ---
        self.tab_widget = QTabWidget()
        self.mainTab = QWidget()
        self.optionsTab = QWidget()
        self.visualTab = QWidget()

        self.mainTab.setLayout(self.mainLayout)
        self.optionsTab.setLayout(self.optionsLayout)
        self.visualTab.setLayout(self.visualLayout)

        self.tab_widget.addTab(self.mainTab, "Main")
        self.tab_widget.addTab(self.optionsTab, "Options")
        self.tab_widget.addTab(self.visualTab, "Visual Warning")

        # Central Layout with Feedback Label
        centralWidget = QWidget()
        centralLayout = QVBoxLayout(centralWidget)
        centralLayout.addWidget(self.tab_widget)
        centralLayout.addWidget(self.feedbackLabel)
        self.setCentralWidget(centralWidget)


        # --- Connections ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.UpdateProgressBar)
        # Timer interval set during retrieveConfigs or default

        # Options Tab Connections
        self.frequencyBox.textEdited.connect(self.options_changed)
        self.durationBox.textEdited.connect(self.options_changed)
        self.sampleRateBox.textEdited.connect(self.options_changed)
        self.amplitudeBox.textEdited.connect(self.options_changed)
        self.inputSelector.currentIndexChanged.connect(self.restartInput)
        self.outputSelector.currentIndexChanged.connect(self.restartOutput)

        # Main Tab Connections
        self.volumeKnob.valueChanged.connect(self.setGainBox)
        self.gainBox.textEdited.connect(self.setVolumeKnob)
        self.thresholdSlider.valueChanged.connect(self.setThresholdBox)
        self.thresholdBox.textEdited.connect(self.setThresholdSlider)
        self.triggerCheck.stateChanged.connect(lambda: self.setChanged(True))
        self.muteAudioCheck.stateChanged.connect(lambda: self.setChanged(True))

        # Visual Warning Tab Connections
        self.enableVisualCheck.stateChanged.connect(self.visual_warning_handler.setEnabled)
        self.enableVisualCheck.stateChanged.connect(lambda: self.setChanged(True))
        # Connect duration input change signal
        self.flashDurationInput.valueChanged.connect(self._visual_duration_changed)


        # Save/Cancel Button Connections
        self.saveMainButton.clicked.connect(self.updateConfigs)
        self.saveOptionsButton.clicked.connect(self.updateConfigs)
        self.saveVisualButton.clicked.connect(self.updateConfigs)

        self.cancelMainButton.clicked.connect(self.retrieveConfigs)
        self.cancelOptionsButton.clicked.connect(self.retrieveConfigs)
        self.cancelVisualButton.clicked.connect(self.retrieveConfigs)


        # --- Initialization ---
        self.volume_level = 0 # Initialize volume level
        self.stream = None

        # *** Load configuration and apply initial state ***
        self.retrieveConfigs()

        # *** Start processes based on loaded config ***
        if not self.UpdateOptions(): # Validate audio options first
             self.feedbackLabel.setText("Status: Warning - Invalid audio options loaded. Please check Options tab.")
             # Decide if stream should start with invalid options or not
             # self.restartInput() # Maybe don't start if options are bad?
        else:
             self.restartInput()    # Start audio stream only if options are valid

        # Start UI update timer regardless of audio stream state
        self.timer.start(50) # Start timer with interval (e.g., 50ms)

        # Mark that setup is complete and future changes are user-driven
        self.isChangedByUser = True
        # Ensure save/cancel buttons reflect the initial loaded state (likely disabled)
        self.setChanged(False)


    def setChanged(self, isChanged):
        # Only enable buttons if the change was user-initiated *after* initial load
        if not self.isChangedByUser and isChanged:
            return
        # Enable/disable buttons on all relevant tabs
        self.saveMainButton.setEnabled(isChanged)
        self.saveOptionsButton.setEnabled(isChanged)
        self.saveVisualButton.setEnabled(isChanged)
        self.cancelMainButton.setEnabled(isChanged)
        self.cancelOptionsButton.setEnabled(isChanged)
        self.cancelVisualButton.setEnabled(isChanged)

    def setThresholdSlider(self):
        """Update slider when threshold text box is edited."""
        try:
            value = int(self.thresholdBox.text())
            if 0 <= value <= 100:
                # Prevent feedback loop if already set
                if self.thresholdSlider.value() != value:
                    self.thresholdSlider.setValue(value)
                self.thresholdBox.setStyleSheet("")
                self.setChanged(True)
            else:
                self.thresholdBox.setStyleSheet("color: red;")
        except ValueError:
            self.thresholdBox.setStyleSheet("color: red;")


    def setThresholdBox(self):
        """Update threshold text box when slider is moved."""
        value = str(self.thresholdSlider.value())
        # Prevent feedback loop if already set
        if self.thresholdBox.text() != value:
             self.thresholdBox.setText(value)
        self.setChanged(True)

    def setVolumeKnob(self):
        """Update knob when gain text box is edited."""
        try:
            value = int(self.gainBox.text())
            if 0 <= value <= 100:
                # Prevent feedback loop if already set
                if self.volumeKnob.value() != value:
                    self.volumeKnob.setValue(value)
                self.gainBox.setStyleSheet("")
                self.setChanged(True)
            else:
                 self.gainBox.setStyleSheet("color: red;")
        except ValueError:
            self.gainBox.setStyleSheet("color: red;")

    def setGainBox(self):
        """Update gain text box when knob is turned."""
        value = str(self.volumeKnob.value())
        # Prevent feedback loop if already set
        if self.gainBox.text() != value:
            self.gainBox.setText(value)
        self.setChanged(True)

    def updateConfigs(self):
        """Save current UI settings using config_handler."""
        print("Gathering UI state for saving...")

        # Create settings dictionary from UI
        current_settings = {
            "main": {
                "gainBox": self.gainBox.text(),
                "thresholdBox": self.thresholdBox.text(),
                "triggerCheck": str(self.triggerCheck.isChecked()),
                "muteAudioCheck": str(self.muteAudioCheck.isChecked())
            },
            "options": {
                "frequencyBox": self.frequencyBox.text(),
                "durationBox": self.durationBox.text(),
                "sampleRateBox": self.sampleRateBox.text(),
                "amplitudeBox": self.amplitudeBox.text()
            },
            "devices": {
                "inputSelector": self.inputSelector.currentText(),
                "outputSelector": self.outputSelector.currentText()
            },
            "visual": {
                "enableVisualCheck": str(self.enableVisualCheck.isChecked()),
                "flashDurationMs": str(self.flashDurationInput.value())
            }
        }

        # Save using config_handler
        success, message = config_handler.save_config(current_settings)
        
        self.feedbackLabel.setText(message)
        if success:
            self.setChanged(False) # Disable buttons after save


    def retrieveConfigs(self):
        """Load settings using config_handler and apply them to the UI."""
        print("Retrieving configuration...")
        self.isChangedByUser = False # IMPORTANT: Prevent setChanged calls during load
        
        # Load configuration using config_handler
        loaded_data = config_handler.load_config()
        settings = loaded_data.get('settings', {})
        self.feedbackLabel.setText(loaded_data.get('message', 'Status: Error loading config.'))
        
        if not settings:
            print("Error: No settings loaded from config_handler. Cannot apply to UI.")
            self.isChangedByUser = True # Re-enable after attempt
            return

        # --- Apply Settings to UI ---
        try:
            # Main Tab
            self.gainBox.setText(settings.get('main', {}).get('gainBox', '100'))
            self.setVolumeKnob() # Update knob from box value
            self.thresholdBox.setText(settings.get('main', {}).get('thresholdBox', '50'))
            self.setThresholdSlider() # Update slider from box value
            self.triggerCheck.setChecked(settings.get('main', {}).get('triggerCheck', 'True').lower() == 'true')
            self.muteAudioCheck.setChecked(settings.get('main', {}).get('muteAudioCheck', 'False').lower() == 'true')

            # Visual Tab
            visual_settings = settings.get('visual', {})
            visual_enabled = visual_settings.get('enableVisualCheck', 'True').lower() == 'true'
            flash_duration_ms = visual_settings.get('flashDurationMs', '300')  # Default 300ms if not specified
            
            self.enableVisualCheck.setChecked(visual_enabled)
            self.visual_warning_handler.setEnabled(visual_enabled) # Ensure handler state matches
            
            # Set flash duration in the handler and UI SpinBox
            try:
                duration_ms = int(flash_duration_ms)
                self.visual_warning_handler.setFlashDuration(duration_ms)
                # Block signals temporarily to avoid triggering changed state during load
                self.flashDurationInput.blockSignals(True)
                self.flashDurationInput.setValue(duration_ms)
                self.flashDurationInput.blockSignals(False)
                print(f"Visual warning flash duration set to {duration_ms}ms")
            except ValueError:
                print(f"Warning: Invalid flash duration '{flash_duration_ms}' in config, using default")
                self.visual_warning_handler.setFlashDuration(300)  # Use default on error
                self.flashDurationInput.blockSignals(True)
                self.flashDurationInput.setValue(300)
                self.flashDurationInput.blockSignals(False)

            # Options Tab
            self.frequencyBox.setText(settings.get('options', {}).get('frequencyBox', '440'))
            self.durationBox.setText(settings.get('options', {}).get('durationBox', '0.5'))
            self.sampleRateBox.setText(settings.get('options', {}).get('sampleRateBox', '44100'))
            self.amplitudeBox.setText(settings.get('options', {}).get('amplitudeBox', '0.5'))

            # Devices Tab - Select based on saved name
            saved_input = settings.get('devices', {}).get('inputSelector', '')
            input_idx = self.inputSelector.findText(saved_input) if saved_input else -1
            if input_idx != -1:
                self.inputSelector.setCurrentIndex(input_idx)
                print(f"Set input device to index {input_idx} ('{saved_input}')")
            elif self.inputDevices: # If saved not found, try default system input
                try:
                    default_idx_sys = sd.default.device[0]
                    default_input_text = next((f"{dev['index']:02d} {dev['name']}" for dev in self.inputDevices if dev['index'] == default_idx_sys), None)
                    input_idx_def = self.inputSelector.findText(default_input_text) if default_input_text else 0
                    if input_idx_def != -1: self.inputSelector.setCurrentIndex(input_idx_def)
                    else: self.inputSelector.setCurrentIndex(0) # Fallback to first
                    print(f"Saved input not found or invalid. Set input device to default/first index {self.inputSelector.currentIndex()}.")
                except Exception as e:
                     print(f"Error setting default input device, using first: {e}")
                     if self.inputDevices: self.inputSelector.setCurrentIndex(0)
            else:
                print("No input devices available.")

            saved_output = settings.get('devices', {}).get('outputSelector', '')
            output_idx = self.outputSelector.findText(saved_output) if saved_output else -1
            if output_idx != -1:
                self.outputSelector.setCurrentIndex(output_idx)
                print(f"Set output device to index {output_idx} ('{saved_output}')")
            elif self.outputDevices: # If saved not found, try default system output
                try:
                    default_idx_sys = sd.default.device[1]
                    default_output_text = next((f"{dev['index']:02d} {dev['name']}" for dev in self.outputDevices if dev['index'] == default_idx_sys), None)
                    output_idx_def = self.outputSelector.findText(default_output_text) if default_output_text else 0
                    if output_idx_def != -1: self.outputSelector.setCurrentIndex(output_idx_def)
                    else: self.outputSelector.setCurrentIndex(0) # Fallback to first
                    print(f"Saved output not found or invalid. Set output device to default/first index {self.outputSelector.currentIndex()}.")
                except Exception as e:
                     print(f"Error setting default output device, using first: {e}")
                     if self.outputDevices: self.outputSelector.setCurrentIndex(0)
            else:
                print("No output devices available.")
                
        except Exception as e:
            print(f"Error applying loaded settings to UI: {e}")
            self.feedbackLabel.setText(f"Status: Error applying settings: {e}")

        # --- Final Steps ---
        # Note: UpdateOptions is called *after* retrieveConfigs in __init__
        # Note: setChanged(False) is called *after* retrieveConfigs in __init__
        # Note: isChangedByUser is set to True *after* retrieveConfigs in __init__
        print("Finished retrieving configuration.")


    def options_changed(self):
         """Called when any option text box is edited."""
         # Validate immediately but don't necessarily restart stream here
         is_valid = self.UpdateOptions()
         # Enable save/cancel buttons if the change was user-initiated
         self.setChanged(True)
         # Optionally update feedback if options become invalid
         if not is_valid:
              self.feedbackLabel.setText("Status: Warning - Invalid audio options entered.")
              
    def _visual_duration_changed(self, value):
         """Called when the flash duration SpinBox value changes."""
         print(f"Visual warning flash duration changed to: {value}ms")
         self.visual_warning_handler.setFlashDuration(value)
         self.setChanged(True)


    def restartInput(self):
        """Stops the current input stream (if running) and starts a new one
           based on the selected device and VALIDATED sample rate."""
        # --- Stop Existing Stream ---
        if self.stream and self.stream.active:
            try:
                self.stream.stop()
                self.stream.close()
                print("Stopped previous audio stream.")
            except Exception as e:
                 self.feedbackLabel.setText(f"Warn: Error stopping stream: {e}")
                 print(f"Warning: Error stopping stream: {e}")
            finally:
                 self.stream = None # Ensure stream is reset

        # --- Validate Prerequisites ---
        if not hasattr(self, 'samplerate') or self.samplerate <= 0:
             self.feedbackLabel.setText("Status: Cannot start stream - Invalid sample rate.")
             print("Error starting input stream: Sample rate not valid or not set.")
             return

        if not self.inputDevices or self.inputSelector.currentIndex() < 0:
            self.feedbackLabel.setText("Status: Cannot start stream - No input device selected or available.")
            print("Error starting input stream: No input device selected or available.")
            return

        # --- Get Selected Device ---
        device_text = self.inputSelector.currentText()
        try:
            device_index = int(device_text[:2]) # Extract index from "NN Name" format
        except (ValueError, IndexError):
             self.feedbackLabel.setText(f"Status: Cannot start stream - Invalid device format '{device_text}'.")
             print(f"Error starting input stream: Invalid device selection format '{device_text}'.")
             return

        # --- Start New Stream ---
        try:
            # Ensure the default output device is preserved when setting default input
            current_output_device_index = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) and len(sd.default.device) > 1 else (sd.query_devices(kind='output')['index'] if self.outputDevices else None)
            if current_output_device_index is not None:
                 sd.default.device = (device_index, current_output_device_index)
                 print(f"Setting default devices: Input={device_index}, Output={current_output_device_index}")
            else:
                 sd.default.device = device_index # Set only input if output fails
                 print(f"Setting default input device to index: {device_index} (Output device unknown/unavailable)")


            print(f"Attempting to start InputStream with device={device_index}, samplerate={self.samplerate}")
            self.stream = sd.InputStream(callback=self.ListenToMic,
                                        samplerate=self.samplerate,
                                        device=device_index,
                                        dtype='float32') # Specify common dtype
            self.stream.start()
            self.feedbackLabel.setText(f"Status: Monitoring '{self.inputSelector.currentText()}'")
            print(f"Input stream started successfully on device {device_index}")
            # No need to call setChanged(True) here, device selection change calls it

        except sd.PortAudioError as pae:
             self.feedbackLabel.setText(f"Status: PortAudio Error - {pae}")
             print(f"PortAudio Error starting input stream: {pae}")
             self.stream = None
        except Exception as e:
            self.feedbackLabel.setText(f"Status: Error starting stream - {e}")
            print(f"Error starting input stream: {e}")
            self.stream = None


    def restartOutput(self):
        """Sets the default output device in sounddevice."""
        # --- Validate Prerequisites ---
        if not self.outputDevices or self.outputSelector.currentIndex() < 0:
             self.feedbackLabel.setText("Status: Cannot set output - No output device selected or available.")
             print("Error setting output device: No output device selected or available.")
             # Don't necessarily mark as changed if nothing can be set
             return

        # --- Get Selected Device ---
        device_text = self.outputSelector.currentText()
        try:
            device_index = int(device_text[:2])
        except (ValueError, IndexError):
             self.feedbackLabel.setText(f"Status: Cannot set output - Invalid device format '{device_text}'.")
             print(f"Error setting output device: Invalid device selection format '{device_text}'.")
             # Don't mark as changed if format is wrong
             return

        # --- Set Output Device ---
        try:
            # Ensure the default input device is preserved
            current_input_device_index = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else (sd.query_devices(kind='input')['index'] if self.inputDevices else None)
            if current_input_device_index is not None:
                 sd.default.device = (current_input_device_index, device_index)
                 print(f"Setting default devices: Input={current_input_device_index}, Output={device_index}")
            else:
                 sd.default.device = device_index # This might cause issues if only output is set
                 print(f"Warning: Setting only default output device to index: {device_index} (Input device unknown/unavailable)")


            self.feedbackLabel.setText(f"Status: Output device set to '{self.outputSelector.currentText()}'")
            print(f"Default output device set to index: {device_index}")
            # Mark config as changed since the user selected a new device
            self.setChanged(True)

        except sd.PortAudioError as pae:
            self.feedbackLabel.setText(f"Status: PortAudio Error setting output - {pae}")
            print(f"PortAudio Error setting output device: {pae}")
        except Exception as e:
            self.feedbackLabel.setText(f"Status: Error setting output - {e}")
            print(f"Error setting output device: {e}")


    def ListenToMic(self, indata, frames, time, status):
        """Callback function for the audio input stream."""
        if status:
            # You might want to handle specific statuses differently
            print("Audio Stream Status:", status, file=sys.stderr)
            if status & sd.CallbackFlags.input_overflow:
                print("Warning: Input overflow detected", file=sys.stderr)
            if status & sd.CallbackFlags.input_underflow:
                 print("Warning: Input underflow detected", file=sys.stderr)
            # Add more checks if needed (output_overflow, output_underflow, priming_output)

        try:
            # Use validated gain value if possible, otherwise a safe default
            gain_text = self.gainBox.text() # Read from UI thread variable (generally safe for reading)
            gain_value = float(gain_text) if gain_text.replace('.', '', 1).isdigit() else 100.0 # Basic validation
            gain_factor = max(0.01, gain_value / 10.0) # Avoid division by zero or negative gain

            # Calculate RMS (Root Mean Square) volume - more representative than peak
            # Use np.fmax to avoid issues with potential negative values if dtype changes
            rms = np.sqrt(np.mean(np.fmax(indata, 0)**2))

            # Scale volume level (adjust multiplier based on typical RMS values and desired range 0-100)
            # RMS of sine wave is amplitude / sqrt(2). Max amplitude is 1. So max RMS ~0.707
            # A multiplier ~140 would map max RMS to 100.
            # Apply gain factor. Maybe scaling needs adjustment.
            # Let's try gain_factor * 140 * rms
            self.volume_level = rms * gain_factor * 140

        except ValueError as ve:
             # This might happen if gainBox has invalid text momentarily
             print(f"ValueError in ListenToMic (likely gainBox): {ve}", file=sys.stderr)
             # Use a default calculation
             rms = np.sqrt(np.mean(np.fmax(indata, 0)**2))
             self.volume_level = rms * 10 * 140 # Default gain factor 10
        except Exception as e:
             # Catch other potential errors in calculation
             print(f"Error in ListenToMic audio processing: {e}", file=sys.stderr)
             self.volume_level = 0 # Reset volume on error


    def UpdateProgressBar(self):
        """Updates the volume progress bar and checks the trigger threshold."""
        try:
            # Clamp volume display between 0 and 100
            display_volume = max(0, min(int(self.volume_level), 100))
            if self.volumeBar.value() != display_volume:
                self.volumeBar.setValue(display_volume)

            threshold_value = self.thresholdSlider.value()

            # Update progress bar color based on threshold - Apply stylesheet only if needed
            new_stylesheet = "QProgressBar::chunk { background-color: %s; }" % ('red' if display_volume > threshold_value else 'green')
            # Avoid reapplying the same stylesheet constantly if possible
            # Note: Directly comparing stylesheets might be unreliable.
            # A simple check if the color *should* change might be sufficient.
            current_is_red = "red" in self.volumeBar.styleSheet()
            should_be_red = display_volume > threshold_value
            if current_is_red != should_be_red:
                self.volumeBar.setStyleSheet(new_stylesheet)

            # Check if the trigger condition is met
            # Use a small buffer/hysteresis? Maybe not needed yet.
            if self.triggerCheck.isChecked() and self.volume_level > threshold_value:
                self.Trigger()
        except Exception as e:
            print(f"Error in UpdateProgressBar: {e}", file=sys.stderr)


    def UpdateOptions(self):
        """Validates audio options from UI fields. Sets internal attributes (freq, duration, etc.)
           Returns True if all options are currently valid, False otherwise."""
        print("Validating options...")
        valid_options = True
        old_samplerate = getattr(self, 'samplerate', None)
        needs_restart = False

        # --- Validate Frequency ---
        try:
            freq_val = int(self.frequencyBox.text())
            if freq_val <= 0: raise ValueError("Frequency must be positive")
            self.freq = freq_val # Store validated value
            self.frequencyBox.setStyleSheet("") # Reset style if valid
            print(f"  - Frequency OK: {self.freq}")
        except ValueError as e:
            self.frequencyBox.setStyleSheet("color: red;")
            valid_options = False
            print(f"  - Frequency INVALID: {e}")

        # --- Validate Duration ---
        try:
            duration_val = float(self.durationBox.text())
            if duration_val <= 0: raise ValueError("Duration must be positive")
            self.duration = duration_val # Store validated value
            self.durationBox.setStyleSheet("")
            print(f"  - Duration OK: {self.duration}")
        except ValueError as e:
            self.durationBox.setStyleSheet("color: red;")
            valid_options = False
            print(f"  - Duration INVALID: {e}")

        # --- Validate Sample Rate ---
        try:
            new_samplerate = int(self.sampleRateBox.text())
            if new_samplerate <= 0: raise ValueError("Sample rate must be positive")
            # Store validated value (even if unchanged, ensures self.samplerate exists)
            self.samplerate = new_samplerate
            self.sampleRateBox.setStyleSheet("")
            print(f"  - Sample Rate OK: {self.samplerate}")
            # Check if changed from previous valid rate
            if old_samplerate is not None and old_samplerate != new_samplerate:
                 needs_restart = True # Mark for stream restart if changed
                 print(f"    (Sample rate changed from {old_samplerate}, input restart needed)")
            elif old_samplerate is None:
                 print("    (Initial sample rate set)")

        except ValueError as e:
            self.sampleRateBox.setStyleSheet("color: red;")
            valid_options = False
            self.samplerate = -1 # Indicate invalid rate internally
            print(f"  - Sample Rate INVALID: {e}")

        # --- Validate Amplitude ---
        try:
            amplitude_val = float(self.amplitudeBox.text())
            if not (0.0 <= amplitude_val <= 1.0): raise ValueError("Amplitude must be between 0.0 and 1.0")
            self.amplitude = amplitude_val # Store validated value
            self.amplitudeBox.setStyleSheet("")
            print(f"  - Amplitude OK: {self.amplitude}")
        except ValueError as e:
            self.amplitudeBox.setStyleSheet("color: red;")
            valid_options = False
            print(f"  - Amplitude INVALID: {e}")

        # --- Handle Stream Restart (only if rate changed AND options are NOW valid) ---
        # This logic is moved to where the change occurs (e.g., textEdited signal handler)
        # or explicitly called after fixing invalid options.
        # For now, this function just validates and sets flags/attributes.

        print(f"Options validation result: {valid_options}")
        return valid_options


    def Trigger(self):
        """Actions to perform when the volume threshold is exceeded."""
        # Quick check: Are triggers enabled at all?
        if not self.triggerCheck.isChecked():
            return

        # Ensure audio options are valid before trying to use them
        # Rely on the latest validation status if possible, or re-validate.
        if not hasattr(self, 'freq') or not hasattr(self, 'duration') or \
           not hasattr(self, 'samplerate') or self.samplerate <= 0 or \
           not hasattr(self, 'amplitude'):
             # If attributes don't exist or sample rate is bad, try validating again
             print("Trigger called with uninitialized/invalid options, attempting re-validation...")
             if not self.UpdateOptions(): # Try to update/validate them now
                  self.feedbackLabel.setText("Status: Trigger skipped - Invalid audio options.")
                  print("Trigger aborted: Invalid audio options detected on re-validation.")
                  return # Don't proceed if options are still invalid

        print("TRIGGERED!") # Log trigger event

        # Play audio warning if not muted
        if not self.muteAudioCheck.isChecked():
            try:
                 # Use the validated internal attributes
                 self.PlayTone(self.freq, self.duration, self.samplerate, self.amplitude)
            except Exception as e:
                 # Log error but don't necessarily stop the app
                 self.feedbackLabel.setText(f"Status: Error playing tone - {e}")
                 print(f"Error playing trigger tone: {e}", file=sys.stderr)

        # Trigger visual warning (the handler checks its own enabled state)
        self.visual_warning_handler.trigger()


    def PlayTone(self, freq=440, duration=0.5, samplerate=44100, amplitude=0.5):
        """
        Play a sine wave tone on the default output device.
        Uses validated internal attributes if called from Trigger.
        """
        if samplerate <= 0:
            print("Error: Cannot play tone with invalid sample rate.", file=sys.stderr)
            return
        try:
             print(f"Playing tone: Freq={freq}, Dur={duration}, SR={samplerate}, Amp={amplitude}")
             # Generate time points
             t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
             # Generate sine wave - ensure float32 for compatibility
             wave = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)

             # Play the sound on the currently selected default output device
             sd.play(wave, samplerate, blocking=False) # Use non-blocking play is crucial for GUI
             # sd.wait() # DO NOT use sd.wait() in GUI applications!
        except sd.PortAudioError as pae:
            # Specific PortAudio errors
            self.feedbackLabel.setText(f"Status: PortAudio Error - {pae}")
            print(f"PortAudio Error in PlayTone: {pae}", file=sys.stderr)
        except Exception as e:
            # Other potential errors (numpy calculation, etc.)
            self.feedbackLabel.setText(f"Status: Error playing tone - {e}")
            print(f"Error in PlayTone: {e}", file=sys.stderr)

    def closeEvent(self, event):
        """Ensure audio stream is stopped and closed when the window is closed."""
        print("Close event triggered. Stopping audio stream...")
        if self.stream: # Check if stream object exists
            try:
                if self.stream.active:
                     self.stream.stop()
                     print("Audio input stream stopped.")
                self.stream.close()
                print("Audio input stream closed.")
            except Exception as e:
                 print(f"Error stopping/closing audio stream: {e}", file=sys.stderr)
                 # Don't prevent closing, just log the error
        else:
            print("Audio stream was not initialized or already closed.")

        # Stop timers explicitly if needed, although Python's GC might handle them
        self.timer.stop()
        print("UI timer stopped.")

        # Accept the close event to allow the window to close
        event.accept()
        print("Application closing.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Optional: Apply a style for a more consistent look
    # app.setStyle('Fusion')
    print("Starting Microphone Guardian...")
    try:
        listenerWindow = micMonitorWindow()
        listenerWindow.show()
        print("Main window displayed.")
        sys.exit(app.exec())
    except Exception as e:
        # Catch unexpected errors during initialization or run
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        # Show a critical message box if possible
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Icon.Critical)
        msgBox.setText("An unexpected error occurred.")
        msgBox.setInformativeText(str(e))
        msgBox.setWindowTitle("Fatal Error")
        msgBox.exec()
        sys.exit(1) # Exit with error code
