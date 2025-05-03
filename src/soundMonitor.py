import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPalette, QColor
from configparser import ConfigParser
import os


#
#         __o
#       _ \<_
#      (_)/(_)
# ```````

# TODO
# github workflow setup
# select input/ouput devices DONE
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
        self.setGeometry(500, 120, 400, 250) # Increased height slightly for new checkboxes

        # Store original palette for visual warning reset
        self.original_palette = self.palette()
        self.visual_warning_active = False
        self.visual_warning_timer = QTimer(self)
        self.visual_warning_timer.setSingleShot(True)
        self.visual_warning_timer.timeout.connect(self.reset_visual_warning)

        # --- Device Setup ---
        self.inputDevices = [
            device
            for device in sd.query_devices()
            if (device["max_input_channels"] > 0)
        ]
        self.outputDevices = [
            device
            for device in sd.query_devices()
            if (device["max_output_channels"] > 0)
        ]

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
                background-color: green;
            }
        """
        )

        self.thresholdSlider = QSlider(Qt.Orientation.Horizontal)
        self.thresholdSlider.setValue(50)
        self.thresholdSlider.setStyleSheet(
            """
            QSlider::groove:horizontal {
                height: 0px;
                background: lightgrey; /* Added background */
            }
            QSlider::handle:horizontal {
                background-color: blue;
                border: 1px solid black;
                width: 10px;
                margin: -5px 0;
            }
        """
        )

        self.thresholdBox = QLineEdit("50")
        self.thresholdBox.setMaximumWidth(configBoxSize)
        self.thresholdLabel = QLabel("- Trigger Threshold")

        self.volumeKnob = QDial()
        self.volumeKnob.setValue(100)

        self.gainBox = QLineEdit("100")
        self.gainBox.setMaximumWidth(configBoxSize)
        self.gainLabel = QLabel("- Mic Sensitivity (Gain)")

        self.triggerCheck = QCheckBox("Enable Trigger")
        self.triggerCheck.setChecked(True)

        self.muteAudioCheck = QCheckBox("Mute Audio Warning")
        self.muteAudioCheck.setChecked(False)

        self.enableVisualCheck = QCheckBox("Enable Visual Warning")
        self.enableVisualCheck.setChecked(True)

        self.saveMainButton = QPushButton("Save Settings")
        self.cancelMainButton = QPushButton("Cancel Changes")

        self.frequencyLabel = QLabel("- Frequency (Hz)")
        self.frequencyBox = QLineEdit("440")
        self.frequencyBox.setMaximumWidth(configBoxSize)

        self.durationLabel = QLabel("- Duration (s)")
        self.durationBox = QLineEdit("0.5")
        self.durationBox.setMaximumWidth(configBoxSize)

        self.sampleRateLabel = QLabel("- Sample Rate (Hz)")
        self.sampleRateBox = QLineEdit("44100")
        self.sampleRateBox.setMaximumWidth(configBoxSize + 10)

        self.amplitudeLabel = QLabel("- Amplitude (0.0-1.0)")
        self.amplitudeBox = QLineEdit("0.5")
        self.amplitudeBox.setMaximumWidth(configBoxSize)

        self.inputSelector = QComboBox()
        self.inputSelector.addItems(
            [f"{dev['index']:02d} {dev['name']}" for dev in self.inputDevices]
        )
        try:
            default_input_idx = [i for i, dev in enumerate(self.inputDevices) if dev['index'] == sd.default.device[0]][0]
            self.inputSelector.setCurrentIndex(default_input_idx)
        except (IndexError, ValueError):
            if self.inputDevices:
                 self.inputSelector.setCurrentIndex(0)

        self.outputSelector = QComboBox()
        self.outputSelector.addItems(
            [f"{dev['index']:02d} {dev['name']}" for dev in self.outputDevices]
        )
        try:
            default_output_idx = [i for i, dev in enumerate(self.outputDevices) if dev['index'] == sd.default.device[1]][0]
            self.outputSelector.setCurrentIndex(default_output_idx)
        except (IndexError, ValueError):
             if self.outputDevices:
                 self.outputSelector.setCurrentIndex(0)


        self.saveOptionsButton = QPushButton("Save Settings")
        self.cancelOptionsButton = QPushButton("Cancel Changes")
        self.feedbackLabel = QLabel("Status: OK")
        self.feedbackLabel.setFixedHeight(15)


        self.parentGrid = QGridLayout()
        gainLayout = QHBoxLayout()
        thresholdLayout = QHBoxLayout()
        triggerControlLayout = QVBoxLayout()
        self.configLayout = QGridLayout()

        gainLayout.addWidget(self.gainBox, 0, Qt.AlignmentFlag.AlignLeft)
        gainLayout.addWidget(self.gainLabel, 1, Qt.AlignmentFlag.AlignLeft)

        thresholdLayout.addWidget(self.thresholdBox, 0, Qt.AlignmentFlag.AlignLeft)
        thresholdLayout.addWidget(self.thresholdLabel, 1, Qt.AlignmentFlag.AlignLeft)

        triggerControlLayout.addWidget(self.triggerCheck)
        triggerControlLayout.addWidget(self.muteAudioCheck)
        triggerControlLayout.addWidget(self.enableVisualCheck)
        triggerControlLayout.addStretch() # Push controls to top

        # (widget, row, column, rowSpan, columnSpan, alignment)
        self.parentGrid.addWidget(self.volumeBar, 0, 0, 1, 3)
        self.parentGrid.addWidget(self.thresholdSlider, 1, 0, 1, 3)
        self.parentGrid.addWidget(self.volumeKnob, 2, 0, 2, 1)
        self.parentGrid.addLayout(thresholdLayout, 2, 1)
        self.parentGrid.addLayout(gainLayout, 3, 1)
        self.parentGrid.addLayout(triggerControlLayout, 2, 2, 2, 1)

        mainButtonLayout = QHBoxLayout()
        mainButtonLayout.addWidget(self.saveMainButton)
        mainButtonLayout.addStretch()
        mainButtonLayout.addWidget(self.cancelMainButton)
        self.parentGrid.addLayout(mainButtonLayout, 4, 0, 1, 3) # Span across bottom

        self.configLayout.addWidget(self.frequencyBox, 0, 0)
        self.configLayout.addWidget(self.frequencyLabel, 0, 1)
        self.configLayout.addWidget(self.sampleRateBox, 0, 2)
        self.configLayout.addWidget(self.sampleRateLabel, 0, 3)

        self.configLayout.addWidget(self.durationBox, 1, 0)
        self.configLayout.addWidget(self.durationLabel, 1, 1)
        self.configLayout.addWidget(self.amplitudeBox, 1, 2)
        self.configLayout.addWidget(self.amplitudeLabel, 1, 3)

        self.configLayout.addWidget(QLabel("Input Device:"), 2, 0, 1, 4)
        self.configLayout.addWidget(self.inputSelector, 3, 0, 1, 4)
        self.configLayout.addWidget(QLabel("Output Device:"), 4, 0, 1, 4)
        self.configLayout.addWidget(self.outputSelector, 5, 0, 1, 4)

        optionsButtonLayout = QHBoxLayout()
        optionsButtonLayout.addWidget(self.saveOptionsButton)
        optionsButtonLayout.addStretch()
        optionsButtonLayout.addWidget(self.cancelOptionsButton)
        self.configLayout.addLayout(optionsButtonLayout, 6, 0, 1, 4)
        self.configLayout.setRowStretch(7, 1) # Push content up

        # --- Tabs ---
        self.tab_widget = QTabWidget()
        self.mainTab = QWidget()
        self.optionsTab = QWidget()

        self.mainTab.setLayout(self.parentGrid)
        self.optionsTab.setLayout(self.configLayout)

        self.tab_widget.addTab(self.mainTab, "Main")
        self.tab_widget.addTab(self.optionsTab, "Options")

        # Central Layout with Feedback Label
        centralWidget = QWidget()
        centralLayout = QVBoxLayout(centralWidget)
        centralLayout.addWidget(self.tab_widget)
        centralLayout.addWidget(self.feedbackLabel)
        self.setCentralWidget(centralWidget)


        # --- Connections ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.UpdateProgressBar)
        self.timer.setInterval(50) # ~20 FPS update

        self.frequencyBox.textEdited.connect(self.options_changed)
        self.durationBox.textEdited.connect(self.options_changed)
        self.sampleRateBox.textEdited.connect(self.options_changed)
        self.amplitudeBox.textEdited.connect(self.options_changed)

        self.volumeKnob.valueChanged.connect(self.setGainBox)
        self.gainBox.textEdited.connect(self.setVolumeKnob)
        self.thresholdSlider.valueChanged.connect(self.setThresholdBox)
        self.thresholdBox.textEdited.connect(self.setThresholdSlider)

        # Connect new checkboxes to setChanged
        self.triggerCheck.stateChanged.connect(lambda: self.setChanged(True))
        self.muteAudioCheck.stateChanged.connect(lambda: self.setChanged(True))
        self.enableVisualCheck.stateChanged.connect(lambda: self.setChanged(True))

        self.saveMainButton.clicked.connect(self.updateConfigs)
        self.saveOptionsButton.clicked.connect(self.updateConfigs)

        self.cancelMainButton.clicked.connect(self.retrieveConfigs)
        self.cancelOptionsButton.clicked.connect(self.retrieveConfigs)

        self.inputSelector.currentIndexChanged.connect(self.restartInput)
        self.outputSelector.currentIndexChanged.connect(self.restartOutput)

        # --- Initialization ---
        self.volume_level = 0 # Initialize volume level
        self.iniPath = "config.ini"
        self.stream = None
        self.retrieveConfigs()
        self.UpdateOptions()
        self.restartInput()
        self.timer.start()

        self.isChangedByUser = True # Any future changes are user-initiated
        self.setChanged(False) # Start with buttons disabled


    def setChanged(self, isChanged):
        if not self.isChangedByUser and isChanged:
            return
        self.saveMainButton.setEnabled(isChanged)
        self.saveOptionsButton.setEnabled(isChanged)
        self.cancelMainButton.setEnabled(isChanged)
        self.cancelOptionsButton.setEnabled(isChanged)

    def setThresholdSlider(self):
        """Update slider when threshold text box is edited."""
        try:
            value = int(self.thresholdBox.text())
            if 0 <= value <= 100:
                self.thresholdSlider.setValue(value)
                self.thresholdBox.setStyleSheet("")
                self.setChanged(True)
            else:
                self.thresholdBox.setStyleSheet("color: red;")
        except ValueError:
            self.thresholdBox.setStyleSheet("color: red;")


    def setThresholdBox(self):
        self.thresholdBox.setText(str(self.thresholdSlider.value()))
        self.setChanged(True)

    def setVolumeKnob(self):
        try:
            value = int(self.gainBox.text())
            if 0 <= value <= 100:
                self.volumeKnob.setValue(value)
                self.gainBox.setStyleSheet("")
                self.setChanged(True)
            else:
                 self.gainBox.setStyleSheet("color: red;")
        except ValueError:
            self.gainBox.setStyleSheet("color: red;")

    def setGainBox(self):
        self.gainBox.setText(str(self.volumeKnob.value()))
        self.setChanged(True)

    def updateConfigs(self):
        config = ConfigParser()
        if os.path.exists(self.iniPath):
             config.read(self.iniPath)

        if not config.has_section("main"):
            config.add_section("main")
        if not config.has_section("options"):
            config.add_section("options")
        if not config.has_section("devices"):
            config.add_section("devices")

        config.set("main", "gainBox", self.gainBox.text())
        config.set("main", "thresholdBox", self.thresholdBox.text())
        config.set("main", "triggerCheck", str(self.triggerCheck.isChecked()))
        config.set("main", "muteAudioCheck", str(self.muteAudioCheck.isChecked()))
        config.set("main", "enableVisualCheck", str(self.enableVisualCheck.isChecked()))

        try:
            int(self.frequencyBox.text())
            config.set("options", "frequencyBox", self.frequencyBox.text())
        except ValueError: pass
        try:
            float(self.durationBox.text())
            config.set("options", "durationBox", self.durationBox.text())
        except ValueError: pass
        try:
            int(self.sampleRateBox.text())
            config.set("options", "sampleRateBox", self.sampleRateBox.text())
        except ValueError: pass
        try:
            amp = float(self.amplitudeBox.text())
            if 0.0 <= amp <= 1.0:
                 config.set("options", "amplitudeBox", self.amplitudeBox.text())
        except ValueError: pass


        config.set("devices", "inputSelector", self.inputSelector.currentText())
        config.set("devices", "outputSelector", self.outputSelector.currentText())

        try:
            with open(self.iniPath, "w") as f:
                config.write(f)
            self.feedbackLabel.setText("Status: Settings saved.")
            self.setChanged(False)
        except IOError as e:
            self.feedbackLabel.setText(f"Error saving config: {e}")


    def retrieveConfigs(self):
        """Load settings from config.ini into the UI."""
        self.isChangedByUser = False # Prevent triggering setChanged during load
        config = ConfigParser()

        if not os.path.exists(self.iniPath):
             self.feedbackLabel.setText("Status: config.ini not found, using defaults.")
             self.volumeKnob.setValue(100)
             self.thresholdSlider.setValue(50)
             self.gainBox.setText("100")
             self.thresholdBox.setText("50")
             self.triggerCheck.setChecked(True)
             self.muteAudioCheck.setChecked(False)
             self.enableVisualCheck.setChecked(True)
             self.frequencyBox.setText("440")
             self.durationBox.setText("0.5")
             self.sampleRateBox.setText("44100")
             self.amplitudeBox.setText("0.5")
        else:
            config.read(self.iniPath)
            self.feedbackLabel.setText("Status: Settings loaded.")

            def get_bool(section, option, fallback=False):
                val = config.get(section, option, fallback=str(fallback))
                return val.lower() == 'true'

            self.gainBox.setText(config.get("main", "gainBox", fallback="100"))
            self.setVolumeKnob()
            self.thresholdBox.setText(config.get("main", "thresholdBox", fallback="50"))
            self.setThresholdSlider()
            self.triggerCheck.setChecked(get_bool("main", "triggerCheck", fallback=True))
            self.muteAudioCheck.setChecked(get_bool("main", "muteAudioCheck", fallback=False))
            self.enableVisualCheck.setChecked(get_bool("main", "enableVisualCheck", fallback=True))

            self.frequencyBox.setText(config.get("options", "frequencyBox", fallback="440"))
            self.durationBox.setText(config.get("options", "durationBox", fallback="0.5"))
            self.sampleRateBox.setText(config.get("options", "sampleRateBox", fallback="44100"))
            self.amplitudeBox.setText(config.get("options", "amplitudeBox", fallback="0.5"))

            saved_input = config.get("devices", "inputSelector", fallback="")
            input_idx = next((i for i, item in enumerate(self.inputSelector.model().stringList()) if item == saved_input), 0)
            self.inputSelector.setCurrentIndex(input_idx)

            saved_output = config.get("devices", "outputSelector", fallback="")
            output_idx = next((i for i, item in enumerate(self.outputSelector.model().stringList()) if item == saved_output), 0)
            self.outputSelector.setCurrentIndex(output_idx)

        self.UpdateOptions() 
        self.setChanged(False) 
        self.isChangedByUser = True 

    def options_changed(self):
         """Called when any option text box is edited."""
         self.UpdateOptions()
         self.setChanged(True)


    def restartInput(self):
        if self.stream and self.stream.active:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                 self.feedbackLabel.setText(f"Error stopping stream: {e}")
                 print(f"Error stopping stream: {e}")

        try:
            if self.inputSelector.count() == 0:
                self.feedbackLabel.setText("Error: No input devices available.")
                print("Error starting input stream: No input devices available.")
                self.stream = None
                return

            device_text = self.inputSelector.currentText()
            if not device_text or len(device_text) < 2 or not device_text[:2].isdigit():
                 self.feedbackLabel.setText(f"Error: Invalid device selection '{device_text}'.")
                 print(f"Error starting input stream: Invalid device selection '{device_text}'.")
                 self.stream = None
                 return

            device_index = int(device_text[:2])

            device_index = int(self.inputSelector.currentText()[:2])
            sd.default.device = (device_index, sd.default.device[1])

            self.stream = sd.InputStream(callback=self.ListenToMic,
                                        samplerate=self.samplerate,
                                        device=device_index)
            self.stream.start()
            self.feedbackLabel.setText(f"Status: Input stream started on '{self.inputSelector.currentText()}'")
            if self.isChangedByUser: self.setChanged(True)

        except Exception as e:
            self.feedbackLabel.setText(f"Error starting input stream: {e}")
            print(f"Error starting input stream: {e}")
            self.stream = None


    def restartOutput(self):
        try:
            device_index = int(self.outputSelector.currentText()[:2])
            sd.default.device = (sd.default.device[0], device_index)
            self.feedbackLabel.setText(f"Status: Output device set to '{self.outputSelector.currentText()}'")
            if self.isChangedByUser: self.setChanged(True) 

        except Exception as e:
            self.feedbackLabel.setText(f"Error setting output device: {e}")
            print(f"Error setting output device: {e}")


    def ListenToMic(self, indata, frames, time, status):
        if status:
            print("Stream status:", status, file=sys.stderr)
        gain_factor = float(self.gainBox.text()) / 10.0
        gain_factor = max(0.1, gain_factor)

        rms = np.sqrt(np.mean(indata**2))
        self.volume_level = rms * gain_factor * 100

    def UpdateProgressBar(self):
        display_volume = max(0, min(int(self.volume_level), 100))
        self.volumeBar.setValue(display_volume)

        threshold_value = self.thresholdSlider.value()
        if display_volume > threshold_value:
             self.volumeBar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
             self.volumeBar.setStyleSheet("QProgressBar::chunk { background-color: green; }")


        if self.triggerCheck.isChecked() and self.volume_level > threshold_value:
            self.Trigger()


    def UpdateOptions(self):
        valid_options = True
        try:
            self.freq = int(self.frequencyBox.text())
            self.frequencyBox.setStyleSheet("") 
        except ValueError:
            self.frequencyBox.setStyleSheet("color: red;")
            valid_options = False

        try:
            self.duration = float(self.durationBox.text())
            if self.duration <= 0: raise ValueError("Duration must be positive")
            self.durationBox.setStyleSheet("")
        except ValueError:
            self.durationBox.setStyleSheet("color: red;")
            valid_options = False

        try:
            new_samplerate = int(self.sampleRateBox.text())
            if new_samplerate <= 0: raise ValueError("Sample rate must be positive")
            if hasattr(self, 'samplerate') and self.samplerate != new_samplerate:
                 self.samplerate = new_samplerate
                 self.sampleRateBox.setStyleSheet("")
                 self.restartInput()
            elif not hasattr(self, 'samplerate'):
                 self.samplerate = new_samplerate
                 self.sampleRateBox.setStyleSheet("")
            else:
                 self.sampleRateBox.setStyleSheet("")
        except ValueError:
            self.sampleRateBox.setStyleSheet("color: red;")
            valid_options = False

        try:
            self.amplitude = float(self.amplitudeBox.text())
            if not (0.0 <= self.amplitude <= 1.0): raise ValueError("Amplitude must be between 0.0 and 1.0")
            self.amplitudeBox.setStyleSheet("")
        except ValueError:
            self.amplitudeBox.setStyleSheet("color: red;")
            valid_options = False

        return valid_options


    def Trigger(self):
        if not hasattr(self, 'freq'):
             if not self.UpdateOptions():
                  self.feedbackLabel.setText("Error: Invalid audio options for trigger.")
                  return

        if not self.muteAudioCheck.isChecked():
            try:
                 self.PlayTone(self.freq, self.duration, self.samplerate, self.amplitude)
            except Exception as e:
                 self.feedbackLabel.setText(f"Error playing tone: {e}")
                 print(f"Error playing tone: {e}")

        if self.enableVisualCheck.isChecked():
            self.ShowVisualWarning()

    
    def ShowVisualWarning(self):
        """Flashes the window background red temporarily."""
        if not self.visual_warning_active:
            self.visual_warning_active = True
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor('red'))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

            self.visual_warning_timer.start(300)

    def reset_visual_warning(self):
        """Resets the window background to its original color."""
        self.setPalette(self.original_palette)
        self.setAutoFillBackground(False)
        self.visual_warning_active = False


    def PlayTone(self, freq=440, duration=0.5, samplerate=44100, amplitude=0.5):
        """
        Play a sine wave tone. (by GPT)

        Parameters:
        - freq: Frequency of the sine wave in Hz (default: 440 Hz, which is A4 note).
        - duration: Duration of the tone in seconds (default: 1 second).
        - samplerate: Sampling rate in samples per second (default: 44100 Hz).
        - amplitude: Amplitude of the wave (default: 0.5, range: 0.0 to 1.0).
        """

        try:
             # Generate time points
             t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
             # Generate sine wave
             wave = amplitude * np.sin(2 * np.pi * freq * t)
             # Play the sound on the selected output device
             sd.play(wave, samplerate, blocking=False) # Use non-blocking play
             # sd.wait() # Don't wait here, allows GUI to remain responsive
        except Exception as e:
            self.feedbackLabel.setText(f"Error in PlayTone: {e}")
            print(f"Error in PlayTone: {e}")

    def closeEvent(self, event):
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
            print("Audio stream closed.")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    listenerWindow = micMonitorWindow()
    listenerWindow.show()
    sys.exit(app.exec())
