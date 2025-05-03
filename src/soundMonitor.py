import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor
import os

from visualWarning import VisualWarningTab # Now inherits QWidget
import configHandler
import traceback

class micMonitorWindow(QMainWindow):
    # Define a signal that will be emitted from the audio thread
    warning_needed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.isChangedByUser = False
        self.setWindowTitle("Microphone Guardian")
        self.setGeometry(500, 120, 400, 280)

        # --- Device Setup (Before Handler) ---
        try:
            all_devices = sd.query_devices()
            self.inputDevices = [dev for dev in all_devices if dev["max_input_channels"] > 0]
            self.outputDevices = [dev for dev in all_devices if dev["max_output_channels"] > 0]
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            QMessageBox.critical(self, "Audio Device Error", f"Could not query audio devices: {e}")
            self.inputDevices = []
            self.outputDevices = []

        # --- Load Config FIRST (to pass to handler) ---
        loaded_data = configHandler.load_config()
        initial_settings = loaded_data.get('settings', {})
        initial_visual_settings = initial_settings.get('visual', {})

        self.visualWarningTab = VisualWarningTab(
            targetWidget=self,
            configData=initial_visual_settings,
            parent=self
        )

        # --- Main Tab Widgets ---
        configBoxSize = 50
        self.volumeBar = QProgressBar()
        self.volumeBar.setTextVisible(False)
        self.volumeBar.setStyleSheet(
            """
            QProgressBar { border: 1px solid grey; border-radius: 1px; text-align: center; }
            QProgressBar::chunk { background-color: green; }
            """
        )
        self.thresholdSlider = QSlider(Qt.Orientation.Horizontal)
        self.thresholdSlider.setStyleSheet(
            """
            QSlider::groove:horizontal { border: 1px solid #bbb; background: #ddd; height: 8px; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: #66c2ff; border: 1px solid #44a4ee; height: 8px; border-radius: 4px; }
            QSlider::add-page:horizontal { background: #ddd; border: 1px solid #bbb; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #eee, stop:1 #ccc); border: 1px solid #777; width: 16px; margin: -4px 0; border-radius: 8px; }
            """
        )
        self.thresholdBox = QLineEdit()
        self.thresholdBox.setMaximumWidth(configBoxSize)
        self.thresholdLabel = QLabel("- Trigger Threshold")
        self.volumeKnob = QDial()
        self.gainBox = QLineEdit()
        self.gainBox.setMaximumWidth(configBoxSize)
        self.gainLabel = QLabel("- Mic Sensitivity (Gain)")
        self.triggerCheck = QCheckBox("Enable Trigger")
        self.muteAudioCheck = QCheckBox("Mute Audio Warning")

        # --- Options Tab Widgets ---
        # ... (Options Tab Widget setup remains the same) ...
        self.frequencyLabel = QLabel("- Frequency (Hz)")
        self.frequencyBox = QLineEdit()
        self.frequencyBox.setMaximumWidth(configBoxSize)
        self.durationLabel = QLabel("- Duration (s)")
        self.durationBox = QLineEdit()
        self.durationBox.setMaximumWidth(configBoxSize)
        self.sampleRateLabel = QLabel("- Sample Rate (Hz)")
        self.sampleRateBox = QLineEdit()
        self.sampleRateBox.setMaximumWidth(configBoxSize + 10)
        self.amplitudeLabel = QLabel("- Amplitude (0.0-1.0)")
        self.amplitudeBox = QLineEdit()
        self.amplitudeBox.setMaximumWidth(configBoxSize)
        self.inputSelector = QComboBox()
        self.inputSelector.addItems([f"{dev['index']:02d} {dev['name']}" for dev in self.inputDevices])
        self.outputSelector = QComboBox()
        self.outputSelector.addItems([f"{dev['index']:02d} {dev['name']}" for dev in self.outputDevices])

        # --- Status Label ---
        self.feedbackLabel = QLabel(loaded_data.get('message', 'Status: Error loading config.')) # Use initial load message
        self.feedbackLabel.setFixedHeight(15)

        # --- Layouts ---
        # Main Tab Layout
        self.mainLayout = QGridLayout()
        # ... (Main layout setup remains the same) ...
        gainLayout = QHBoxLayout()
        thresholdLayout = QHBoxLayout()
        triggerControlLayout = QVBoxLayout()
        gainLayout.addWidget(self.gainBox, 0, Qt.AlignmentFlag.AlignLeft)
        gainLayout.addWidget(self.gainLabel, 1, Qt.AlignmentFlag.AlignLeft)
        thresholdLayout.addWidget(self.thresholdBox, 0, Qt.AlignmentFlag.AlignLeft)
        thresholdLayout.addWidget(self.thresholdLabel, 1, Qt.AlignmentFlag.AlignLeft)
        triggerControlLayout.addWidget(self.triggerCheck)
        triggerControlLayout.addWidget(self.muteAudioCheck)
        triggerControlLayout.addStretch()
        self.mainLayout.addWidget(self.volumeBar, 0, 0, 1, 3)
        self.mainLayout.addWidget(self.thresholdSlider, 1, 0, 1, 3)
        self.mainLayout.addWidget(self.volumeKnob, 2, 0, 2, 1)
        self.mainLayout.addLayout(thresholdLayout, 2, 1)
        self.mainLayout.addLayout(gainLayout, 3, 1)
        self.mainLayout.addLayout(triggerControlLayout, 2, 2, 2, 1)

        # Options Tab Layout
        self.optionsLayout = QGridLayout()
        # ... (Options layout setup remains the same) ...
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
        self.optionsLayout.setRowStretch(7, 1)


        # --- Tabs ---
        self.tab_widget = QTabWidget()
        self.mainTab = QWidget()
        self.optionsTab = QWidget()

        self.mainTab.setLayout(self.mainLayout)
        self.optionsTab.setLayout(self.optionsLayout)

        self.tab_widget.addTab(self.mainTab, "Main")
        self.tab_widget.addTab(self.optionsTab, "Options")
        # Add the handler instance directly (it's a QWidget now)
        self.tab_widget.addTab(self.visualWarningTab, "Visual Warning")

        # Central Layout
        centralWidget = QWidget()
        centralLayout = QVBoxLayout(centralWidget)
        centralLayout.addWidget(self.tab_widget)
        centralLayout.addWidget(self.feedbackLabel)
        self.setCentralWidget(centralWidget)

        buttonsLayout = QHBoxLayout()
        self.saveButton = QPushButton("Save Settings")
        buttonsLayout.addStretch()
        self.cancelButton = QPushButton("Cancel Changes")
        buttonsLayout.addWidget(self.saveButton)
        buttonsLayout.addWidget(self.cancelButton)
        centralLayout.addLayout(buttonsLayout)

        # --- Connections ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.UpdateProgressBar)
        
        # Connect the cross-thread signal to the main thread slot
        self.warning_needed.connect(self.handle_warning_trigger)

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
        # Connect UI changes within the handler to trigger setChanged in the main window
        self.visualWarningTab.enable_check.stateChanged.connect(lambda: self.setChanged(True))
        self.visualWarningTab.flash_duration_input.valueChanged.connect(lambda: self.setChanged(True)) # Simple trigger

        # Save/Cancel Button Connections (Main and Options)
        self.saveButton.clicked.connect(self.updateConfigs)
        self.cancelButton.clicked.connect(self.retrieveConfigs)

        # --- Final Initialization Steps ---
        self.volume_level = 0
        self.stream = None

        self._apply_initial_settings(initial_settings)

        # Start audio stream if options are valid
        if not self.UpdateOptions():
            self.feedbackLabel.setText("Status: Warning - Invalid audio options loaded. Check Options.")
        else:
            self.restartInput()

        # Start UI update timer
        self.timer.start(50)
        self.isChangedByUser = True # Allow user changes now
        self.setChanged(False) # Start with buttons disabled

    def _apply_initial_settings(self, settings):
        """Applies loaded settings to the UI elements (excluding visual handler)."""
        print("Applying initial settings...")
        self.isChangedByUser = False # Prevent setChanged during initial apply
        try:
            # Main Tab
            self.gainBox.setText(settings.get('main', {}).get('gainBox', '100'))
            self.setVolumeKnob()
            self.thresholdBox.setText(settings.get('main', {}).get('thresholdBox', '50'))
            self.setThresholdSlider()
            self.triggerCheck.setChecked(settings.get('main', {}).get('triggerCheck', 'True').lower() == 'true')
            self.muteAudioCheck.setChecked(settings.get('main', {}).get('muteAudioCheck', 'False').lower() == 'true')

            # Options Tab
            self.frequencyBox.setText(settings.get('options', {}).get('frequencyBox', '440'))
            self.durationBox.setText(settings.get('options', {}).get('durationBox', '0.5'))
            self.sampleRateBox.setText(settings.get('options', {}).get('sampleRateBox', '44100'))
            self.amplitudeBox.setText(settings.get('options', {}).get('amplitudeBox', '0.5'))


            # Devices Tab
            # ... (apply device selections as before) ...
            saved_input = settings.get('devices', {}).get('inputSelector', '')
            input_idx = self.inputSelector.findText(saved_input) if saved_input else -1
            if input_idx != -1: self.inputSelector.setCurrentIndex(input_idx)
            elif self.inputDevices:
                try:
                    default_idx_sys = sd.default.device[0]; default_input_text = next((f"{dev['index']:02d} {dev['name']}" for dev in self.inputDevices if dev['index'] == default_idx_sys), None); input_idx_def = self.inputSelector.findText(default_input_text) if default_input_text else 0
                    if input_idx_def != -1: self.inputSelector.setCurrentIndex(input_idx_def)
                    else: self.inputSelector.setCurrentIndex(0)
                except Exception: pass
                if input_idx == -1 and self.inputSelector.currentIndex() == -1 : self.inputSelector.setCurrentIndex(0)
            saved_output = settings.get('devices', {}).get('outputSelector', '')
            output_idx = self.outputSelector.findText(saved_output) if saved_output else -1
            if output_idx != -1: self.outputSelector.setCurrentIndex(output_idx)
            elif self.outputDevices:
                try:
                    default_idx_sys = sd.default.device[1]; default_output_text = next((f"{dev['index']:02d} {dev['name']}" for dev in self.outputDevices if dev['index'] == default_idx_sys), None); output_idx_def = self.outputSelector.findText(default_output_text) if default_output_text else 0
                    if output_idx_def != -1: self.outputSelector.setCurrentIndex(output_idx_def)
                    else: self.outputSelector.setCurrentIndex(0)
                except Exception: pass
                if output_idx == -1 and self.outputSelector.currentIndex() == -1 : self.outputSelector.setCurrentIndex(0)


            # Visual settings are applied in the handler's __init__ now

        except Exception as e:
            print(f"Error applying initial settings: {e}\n{traceback.format_exc()}")
            self.feedbackLabel.setText(f"Status: Error applying settings: {e}")
        finally:
             self.isChangedByUser = True # Re-enable after applying
        print("Finished applying initial settings.")


    def setChanged(self, isChanged):
        if not self.isChangedByUser and isChanged:
            return
        self.saveButton.setEnabled(isChanged)
        self.cancelButton.setEnabled(isChanged)


    def updateConfigs(self):
        """Save current UI settings using config_handler."""
        print("Gathering UI state for saving...")

        # Get visual settings directly from the handler
        visual_settings = self.visualWarningTab.get_config_values()

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
            "visual": visual_settings # Use the dictionary from the handler
        }
        success, message = configHandler.save_config(current_settings)
        self.feedbackLabel.setText(message)
        if success:
            self.setChanged(False)


    def retrieveConfigs(self):
        """Load settings using config_handler and re-apply them to the UI."""
        print("Retrieving configuration (Cancel pressed)...")
        self.isChangedByUser = False # Prevent setChanged during load

        # Load configuration using config_handler
        loaded_data = configHandler.load_config()
        settings = loaded_data.get('settings', {})
        self.feedbackLabel.setText(loaded_data.get('message', 'Status: Error loading config.'))

        if not settings:
            print("Error: No settings loaded from config_handler. Cannot apply to UI.")
            self.isChangedByUser = True
            return

        # --- Apply Settings to UI ---
        try:
            # Apply Main, Options, Devices settings
            self._apply_initial_settings(settings)

            # Apply Visual settings by updating the handler
            visual_settings = settings.get('visual', {})
            self.visualWarningTab.setEnabled(visual_settings.get('enableVisualCheck', 'True').lower() == 'true')
            try:
                duration_ms = int(visual_settings.get('flashDurationMs', '300'))
                self.visualWarningTab.setFlashDuration(duration_ms)
            except (ValueError, TypeError):
                 self.visualWarningTab.setFlashDuration(300) # Fallback

        except Exception as e:
            print(f"Error applying loaded settings (retrieveConfigs): {e}\n{traceback.format_exc()}")
            self.feedbackLabel.setText(f"Status: Error applying settings: {e}")
        finally:
            # Ensure buttons reflect loaded state (disabled) AFTER loading
            self.setChanged(False)
            self.isChangedByUser = True # Re-enable tracking user changes
            print("Finished retrieving configuration (Cancel pressed).")


    def options_changed(self):
         is_valid = self.UpdateOptions()
         self.setChanged(True)
         if not is_valid:
              self.feedbackLabel.setText("Status: Warning - Invalid audio options entered.")

    def setThresholdSlider(self):
        try:
            value = int(self.thresholdBox.text());
            if 0 <= value <= 100:
                if self.thresholdSlider.value() != value: self.thresholdSlider.setValue(value)
                self.thresholdBox.setStyleSheet(""); self.setChanged(True)
            else: self.thresholdBox.setStyleSheet("color: red;")
        except ValueError: self.thresholdBox.setStyleSheet("color: red;")
    def setThresholdBox(self):
        value = str(self.thresholdSlider.value());
        if self.thresholdBox.text() != value: self.thresholdBox.setText(value)
        self.setChanged(True)
    def setVolumeKnob(self):
        try:
            value = int(self.gainBox.text());
            if 0 <= value <= 100:
                if self.volumeKnob.value() != value: self.volumeKnob.setValue(value)
                self.gainBox.setStyleSheet(""); self.setChanged(True)
            else: self.gainBox.setStyleSheet("color: red;")
        except ValueError: self.gainBox.setStyleSheet("color: red;")
    def setGainBox(self):
        value = str(self.volumeKnob.value());
        if self.gainBox.text() != value: self.gainBox.setText(value)
        self.setChanged(True)
    def restartInput(self):
        if self.stream and self.stream.active:
            try: self.stream.stop(); self.stream.close()
            except Exception as e: print(f"Warning: Error stopping stream: {e}")
            finally: self.stream = None
        if not hasattr(self, 'samplerate') or self.samplerate <= 0: return
        if not self.inputDevices or self.inputSelector.currentIndex() < 0: return
        device_text = self.inputSelector.currentText();
        try: device_index = int(device_text[:2])
        except (ValueError, IndexError): return
        try:
            current_output_device_index = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) and len(sd.default.device) > 1 else (sd.query_devices(kind='output')['index'] if self.outputDevices else None)
            if current_output_device_index is not None: sd.default.device = (device_index, current_output_device_index)
            else: sd.default.device = device_index
            self.stream = sd.InputStream(callback=self.ListenToMic, samplerate=self.samplerate, device=device_index, dtype='float32')
            self.stream.start(); self.feedbackLabel.setText(f"Status: Monitoring '{self.inputSelector.currentText()}'")
        except sd.PortAudioError as pae: self.feedbackLabel.setText(f"Status: PortAudio Error - {pae}"); self.stream = None
        except Exception as e: self.feedbackLabel.setText(f"Status: Error starting stream - {e}"); self.stream = None
    def restartOutput(self):
        if not self.outputDevices or self.outputSelector.currentIndex() < 0: return
        device_text = self.outputSelector.currentText();
        try: device_index = int(device_text[:2])
        except (ValueError, IndexError): return
        try:
            current_input_device_index = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else (sd.query_devices(kind='input')['index'] if self.inputDevices else None)
            if current_input_device_index is not None: sd.default.device = (current_input_device_index, device_index)
            else: sd.default.device = device_index
            self.feedbackLabel.setText(f"Status: Output device set to '{self.outputSelector.currentText()}'"); self.setChanged(True)
        except sd.PortAudioError as pae: self.feedbackLabel.setText(f"Status: PortAudio Error setting output - {pae}")
        except Exception as e: self.feedbackLabel.setText(f"Status: Error setting output - {e}")
    def ListenToMic(self, indata, frames, time, status):
        """Callback executed by sounddevice in a background thread."""
        if status: print(status, file=sys.stderr)
        try:
            gain_factor = self.volumeKnob.value() / 100.0; amplified_data = indata * gain_factor
            volume_norm = np.linalg.norm(amplified_data) * 10; self.volume_level = min(int(volume_norm), 100)
            # Check trigger condition
            if self.triggerCheck.isChecked() and self.volume_level >= self.thresholdSlider.value():
                # Emit the signal INSTEAD of calling TriggerWarning directly
                self.warning_needed.emit()
        except Exception as e: print(f"Error in ListenToMic: {e}\n{traceback.format_exc()}", file=sys.stderr)
    
    # Slot connected to the warning_needed signal
    def handle_warning_trigger(self):
        """This method executes in the main GUI thread."""
        print("Trigger Received (Main Thread)!")
        
        # Play audio warning if not muted
        if not self.muteAudioCheck.isChecked():
            try:
                device_text = self.outputSelector.currentText(); device_index = int(device_text[:2]) if device_text else None
                if self.amplitude > 0 and self.duration > 0 and self.samplerate > 0:
                    t = np.linspace(0., self.duration, int(self.samplerate * self.duration), endpoint=False)
                    waveform = self.amplitude * np.sin(2. * np.pi * self.frequency * t)
                    sd.play(waveform, self.samplerate, device=device_index, blocking=False)
                else: print("Warning: Invalid audio parameters for warning sound.")
            except ValueError: print(f"Error: Invalid output device format ('{device_text}').")
            except sd.PortAudioError as pae: print(f"PortAudioError playing warning: {pae}")
            except Exception as e: print(f"Error playing warning: {e}")
        
        # Trigger visual warning (Now safe to call from main thread)
        self.visualWarningTab.trigger()
    # TriggerWarning method removed as its functionality is now in handle_warning_trigger
    def UpdateOptions(self):
        is_valid = True; style_error = "color: red;"; style_ok = ""
        try: self.frequency = float(self.frequencyBox.text()); self.frequencyBox.setStyleSheet(style_ok)
        except ValueError: is_valid = False; self.frequencyBox.setStyleSheet(style_error)
        try: self.duration = float(self.durationBox.text()); self.durationBox.setStyleSheet(style_ok)
        except ValueError: is_valid = False; self.durationBox.setStyleSheet(style_error)
        try:
            sr = int(self.sampleRateBox.text());
            if sr > 0: self.samplerate = sr; self.sampleRateBox.setStyleSheet(style_ok)
            else: raise ValueError("Sample rate must be positive")
        except ValueError: is_valid = False; self.samplerate = 0; self.sampleRateBox.setStyleSheet(style_error)
        try:
            amp = float(self.amplitudeBox.text());
            if 0.0 <= amp <= 1.0: self.amplitude = amp; self.amplitudeBox.setStyleSheet(style_ok)
            else: raise ValueError("Amplitude must be 0.0-1.0")
        except ValueError: is_valid = False; self.amplitude = 0; self.amplitudeBox.setStyleSheet(style_error)
        if not is_valid: print("Invalid options entered.")
        return is_valid
    def UpdateProgressBar(self):
        self.volumeBar.setValue(self.volume_level); threshold = self.thresholdSlider.value()
        if self.volume_level >= threshold: self.volumeBar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else: self.volumeBar.setStyleSheet("QProgressBar::chunk { background-color: green; }")
    def closeEvent(self, event):
        print("Closing application..."); self.timer.stop()
        if self.stream:
            try:
                if self.stream.active: self.stream.stop()
                self.stream.close(); print("Audio stream stopped and closed.")
            except Exception as e: print(f"Error closing audio stream: {e}")
        event.accept()

# Main Execution
if __name__ == "__main__":
    try:
        print("Starting Microphone Guardian...")
        app = QApplication(sys.argv)
        listenerWindow = micMonitorWindow()
        listenerWindow.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
