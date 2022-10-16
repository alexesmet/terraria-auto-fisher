#!/usr/bin/env python3

from PyQt5.QtGui import QPixmap, QCursor
from PyQt5.QtGui import QImage
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QLayout
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QFormLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QSpinBox
from PyQt5.QtWidgets import QInputDialog
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QStatusBar
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QDialog

from PIL import Image, ImageGrab
from PIL.ImageQt import ImageQt

from pynput.keyboard import Listener

import sys
import cv2
import time
import numpy
import pyautogui
import subprocess
import configparser


__version__ = '0.4'
__author__ = 'Alexei Metlitski'

def mouse_click():
    global mouse
    if sys.platform == 'linux':
        subprocess.call(['xdotool', 'mousedown', '1'])
        time.sleep(0.02)
        subprocess.call(['xdotool', 'mouseup', '1'])
    elif sys.platform == 'win32':
        pyautogui.mouseDown()
        time.sleep(0.02)
        pyautogui.mouseUp()
    else:
        raise Error("This system is not supported yet: {0}".format(sys.platform))

class InitializationFisherState():
    def __init__(self):
        self.code = "INIT"
        self.description = "Waiting for user..."

    def update(self, sense):
        if sense > 1:
            return CastingFisherState(cast = False)
        else: return None

class CastingFisherState():
    def __init__(self, cast = True):
        self.code = "CAST"
        self.description = "Casting the line"
        self.created_at = time.time()
        if cast: mouse_click()

    def update(self, sense):
        if (time.time() - self.created_at) > 1 and sense < 1:
            return WaitingFisherState()
        else: return None

class WaitingFisherState():
    def __init__(self):
        self.code = "WAIT"
        self.description = "Waiting for movement"
        self.created_at = time.time()

    def update(self, sense):
        if (time.time() - self.created_at) > 1 and sense > 1:
            return ReelingInFisherState()
        else: return None

class ReelingInFisherState():
    def __init__(self):
        self.code = "REEL"
        self.description = "Hooked - reeling in"
        self.created_at = time.time()
        mouse_click()

    def update(self, sense):
        if (time.time() - self.created_at) > 0.5 and sense < 1:
            return CastingFisherState()
        else: return None


class FisherStateMachine():
    def __init__(self):
        self.state = InitializationFisherState()

    def update(self, sense):
        result = self.state.update(sense)
        if result:
            self.state = result


class MovementTracker():
    def __init__(self, n):
        self.change_buffer = None
        self.size = n
        self.counter = 0

    def get_diff(self, img, trsh):
        if not self.change_buffer:
            self.change_buffer = [img for i in range(self.size)]
        self.change_buffer[self.counter] = img
        self.counter = ( self.counter + 1 ) % self.size
        buff = self.change_buffer[self.counter:] + self.change_buffer[:self.counter]
        return self.diff_3_img(buff[:3], trsh)

    def diff_3_img(self, buff, trsh):
        t0, t1, t2 = buff
        d1 = cv2.absdiff(t2, t1)
        d2 = cv2.absdiff(t1, t0)
        res = cv2.bitwise_or(d1, d2)
        t, res = cv2.threshold(res, trsh, 255, cv2.THRESH_BINARY)
        return res


shift = 50

class AppUi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.tracker = MovementTracker(3)
        self.state_machine = None
        self.potion_drink_time = None
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.setWindowTitle('AutoFisher')
        self.setMouseTracking(True)
        self._init_layout()

    def _init_layout(self):
        self.mainLayout = QHBoxLayout()
        self._centralWidget = QWidget(self)
        self.setCentralWidget(self._centralWidget)
        self._centralWidget.setLayout(self.mainLayout)

        self.generalLayout = QVBoxLayout()
        self.mainLayout.addLayout(self.generalLayout)
        self.rightLayout = QVBoxLayout()
        self.mainLayout.addLayout(self.rightLayout)


        previews = QHBoxLayout()
        self.label1 = QLabel(self)
        self.label1.setFrameShape(QFrame.Panel)
        self.label1.setFrameShadow(QFrame.Sunken)
        self.label1.setLineWidth(2)
        self.label1.resize(shift*2, shift*2)
        self.label1.setFixedSize(shift*2, shift*2)
        previews.addWidget(self.label1)
        self.label2 = QLabel(self)
        self.label2.setFrameShape(QFrame.Panel)
        self.label2.setFrameShadow(QFrame.Sunken)
        self.label2.setLineWidth(2)
        self.label2.setFixedSize(shift*2, shift*2)
        previews.addWidget(self.label2)
        self.generalLayout.addLayout(previews)

        self.progress = QProgressBar(self)
        self.mouse_status = QLabel(self)
        self.state_status = QLabel(self)
        self.potion_status = QLabel(self)
        self.generalLayout.addWidget(self.progress)
        self.generalLayout.addWidget(self.mouse_status)
        self.generalLayout.addWidget(self.state_status)
        self.generalLayout.addWidget(self.potion_status)

        flo = QFormLayout()
        self.input_screen_x = QSpinBox()
        self.input_screen_y = QSpinBox()
        self._update_pos_hotkey = 'v'
        self.input_screen_xy_key = QPushButton()
        self.input_treshold = QSpinBox()
        self.input_sensivity = QSpinBox()
        self.input_drink_potions = QCheckBox()
        self.input_drink_delay = QSpinBox()
        self.input_screen_x.setMaximum( QApplication.primaryScreen().size().width() )
        self.input_screen_y.setMaximum( QApplication.primaryScreen().size().height() )
        self.input_screen_xy_key.clicked.connect(self._change_pos_hotkey)
        self.input_treshold.setMaximum( 255 )
        self.input_sensivity.setMaximum( 999 )
        self.input_drink_delay.setMaximum( 3600 )
        flo.addRow("Coordinate X", self.input_screen_x)
        flo.addRow("Coordinate Y", self.input_screen_y)
        self.input_screen_xy_key.setText('Change hotkey ({})'.format(self._update_pos_hotkey))
        flo.addRow("Coordinates to MousePos", self.input_screen_xy_key)
        flo.addRow("Mov. Treshold", self.input_treshold)
        flo.addRow("Sensivity", self.input_sensivity)
        flo.addRow("Drink potions", self.input_drink_potions)
        flo.addRow("Drink delay", self.input_drink_delay)
        self.generalLayout.addLayout(flo)

        self.start = QPushButton(self)
        self.start.setText("Start fishing")
        self.start.clicked.connect(self._on_push_button)
        self.generalLayout.addWidget(self.start)

        self._hotkey = 'f'
        self._hotkey_listener = Listener(on_press=self._keypress_event)
        self._hotkey_listener.start()

        self.select_hotkey = QPushButton(self)
        self.select_hotkey.setText('Change fishing hotkey ({})'.format(self._hotkey))
        self.select_hotkey.clicked.connect(self._change_hotkey)
        self.generalLayout.addWidget(self.select_hotkey)

        self.save = QPushButton(self)
        self.save.setText("Save this preset")
        self.save.clicked.connect(self._save_config)
        self.generalLayout.addWidget(self.save)

        list_controls = QHBoxLayout()
        self.b_create_preset = QPushButton(self)
        self.b_create_preset.setText("Add preset")
        self.b_create_preset.clicked.connect(self._add_preset)
        list_controls.addWidget(self.b_create_preset)

        self.b_delete_preset = QPushButton(self)
        self.b_delete_preset.setText("Delete preset")
        self.b_delete_preset.clicked.connect(self._del_preset)
        list_controls.addWidget(self.b_delete_preset)
        self.rightLayout.addLayout(list_controls)

        self.list = QListWidget()
        self.rightLayout.addWidget(self.list)
        self._update_list_from_config()

        self._load_config()
        self.list.itemSelectionChanged.connect(self._load_config)

        self.timer=QTimer()
        self.timer.timeout.connect(self._update_display)
        self.timer.setInterval(66)
        self.timer.start()

    def _keypress_event(self, key):
        try:
            if self._hotkey == key.char:
                self._on_push_button()
            elif self._update_pos_hotkey == key.char:
                self._xy_pos_update()
        except AttributeError:
            return
    def _change_hotkey(self):
        if self._hotkey_listener.running:
            self._hotkey_listener.stop()
        
        self.hotkey_dialog = QDialog(self)
        self.hotkey_dialog.keyPressEvent = lambda key: self.assign_hotkey(key)
        self.hotkey_dialog.setWindowTitle('Press your desired hotkey.')
        self.hotkey_dialog.exec()

        self._hotkey_listener = Listener(on_press=self._keypress_event)
        self._hotkey_listener.start()

    def assign_hotkey(self, key):
        if key.text() != '' and key.text() != self._update_pos_hotkey:
            self._hotkey = key.text()
        self.hotkey_dialog.close()
        self.select_hotkey.setText('Change fishing hotkey ({})'.format(self._hotkey))
    
    def assign_pos_hotkey(self, key):
        if key.text() != '' and key.text() != self._hotkey:
            self._update_pos_hotkey = key.text()
        self.pos_hotkey_dialog.close()
        self.input_screen_xy_key.setText('Change hotkey ({})'.format(self._update_pos_hotkey))

    def _change_pos_hotkey(self):
        if self._hotkey_listener.running:
            self._hotkey_listener.stop()
        
        self.pos_hotkey_dialog = QDialog(self)
        self.pos_hotkey_dialog.keyPressEvent = lambda key: self.assign_pos_hotkey(key)
        self.pos_hotkey_dialog.setWindowTitle('Press your desired hotkey.')
        self.pos_hotkey_dialog.exec()

        self._hotkey_listener = Listener(on_press=self._keypress_event)
        self._hotkey_listener.start()

    def _xy_pos_update(self):
        pos = pyautogui.position()
        self.input_screen_x.setValue(pos.x)
        self.input_screen_y.setValue(pos.y)

    def _update_list_from_config(self):
        self.list.clear() # HAS SIDE EFFECTS ON CONFIG ??
        for each in self.config.keys():
            self.list.addItem((each + '.')[:-1])
        self.list.setCurrentRow(0)

    def _add_preset(self):
        text, ok = QInputDialog.getText(self, 'Create preset', 'Choose preset name:')
        if ok:
            self.list.addItem(text)
            self.list.setCurrentRow(self.list.count()-1)
            self._save_config()

    def _del_preset(self):
        if self.list.count() <= 1:
            QMessageBox.warning(self, "Warning", "Can't delete last item")
            return
        preset = self._get_current_preset()
        if preset == 'DEFAULT':
            QMessageBox.critical(self, "Heat death of the universe", \
                    "DEFAULT is superior, it can't be deteled")
            return
        reply = QMessageBox.question(self, 'Delete preset', 'Delete {}?'.format(preset), \
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.list.takeItem(self.list.currentRow())
            self.config.remove_section(preset)
            self._update_list_from_config()
            self._save_config()

    def _load_config(self):
        name = self._get_current_preset()
        if name not in self.config:
            self.config[name] = {}
        self.input_screen_x.setValue( int(self.config[name].get('screen_x', 850)))
        self.input_screen_y.setValue( int(self.config[name].get('screen_y', 850)))
        self.input_treshold.setValue( int(self.config[name].get('treshold', 6)))
        self.input_sensivity.setValue(int(self.config[name].get('sensivity', 55)))
        self.input_drink_potions.setChecked(self.config[name].get('drink_potions', 'False') == 'True')
        self.input_drink_delay.setValue(int(self.config[name].get('drink_delay', 185)))

    def _save_config(self):
        name = self._get_current_preset()
        if name not in self.config:
            self.config[name] = {}
        self.config[name]['screen_x'] = str(self.input_screen_x.value())
        self.config[name]['screen_y'] = str(self.input_screen_y.value())
        self.config[name]['treshold'] = str(self.input_treshold.value())
        self.config[name]['sensivity'] = str(self.input_sensivity.value())
        self.config[name]['drink_potions'] = str(self.input_drink_potions.isChecked())
        self.config[name]['drink_delay'] = str(self.input_drink_delay.value())
        self.config[name]['button_to_drink'] = 'b'

        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def _on_push_button(self):
        if self.state_machine:
            self.state_machine = None
            self.potion_drink_time = None
            self.start.setText("Start fishing again")
            self._set_enabled(True)
        else:
            self.state_machine = FisherStateMachine()
            self.potion_drink_time = time.time()
            self.start.setText("Stop fishing")
            self.mouse_status.setText("Mouse position is not tracked")
            self._set_enabled(False)

    def _set_enabled(self, state):
        """Changes enableness of all UI controls"""
        self.mouse_status.setEnabled(state)
        self.save.setEnabled(state)
        self.input_screen_x.setEnabled(state)
        self.input_screen_y.setEnabled(state)
        self.input_treshold.setEnabled(state)
        self.input_sensivity.setEnabled(state)
        self.input_drink_potions.setEnabled(state)
        self.input_drink_delay.setEnabled(state)
        self.b_create_preset.setEnabled(state)
        self.b_delete_preset.setEnabled(state)
        self.list.setEnabled(state)

    def _get_current_preset(self):
        item = self.list.currentItem()
        return item.text() if item else None


    def _update_display(self):
        # Take screenshot
        x = int(self.input_screen_x.value())
        y = int(self.input_screen_y.value())
        t = int(self.input_treshold.value())
        im = ImageGrab.grab((x-shift, y-shift, x+shift, y+shift))

        # Convert to opencv
        frame = cv2.cvtColor(numpy.array(im), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Process, prepare preview
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        preview = self.tracker.get_diff(gray, t)
        count = cv2.countNonZero(preview)
        sense = count * int(self.input_sensivity.value()) / ((shift*2)**2)
        if self.state_machine:
            self.state_machine.update(sense)

        # Update first preview
        pixmap1 = QPixmap.fromImage(ImageQt(im))
        self.label1.setPixmap(pixmap1)

        # Update second preview
        height, width = preview.shape
        cv2qimg = QImage(preview.data, width, height, width * 1, QImage.Format_Grayscale8)
        pixmap2 = QPixmap.fromImage(cv2qimg)
        self.label2.setPixmap(pixmap2)

        self.progress.setValue(min(100, int(sense * 100)))

        # Update status
        if self.state_machine:
            self.state_status.setText(self.state_machine.state.description)
        else:
            # Mouse cursor only update when machine is inactive
            coords = QCursor.pos()
            self.mouse_status.setText("Mouse at ({0}, {1});".format(coords.x(), coords.y()))
            self.state_status.setText("Preset: " + str(self._get_current_preset()))

        if self.input_drink_potions.isChecked():
            if self.potion_drink_time:
                drinking_in = int(self.potion_drink_time + self.input_drink_delay.value() - time.time())
                self.potion_status.setText("Drink all in {} seconds".format(drinking_in))
                if drinking_in <= 0:
                    button_to_drink = self.config[self._get_current_preset()].get('button_to_drink', 'b')
                    self.potion_drink_time = time.time()
                    pyautogui.keyDown(button_to_drink)
                    time.sleep(0.02)
                    pyautogui.keyUp(button_to_drink)
            else:
                self.potion_status.setText("Drink potions every {} seconds".format(self.input_drink_delay.value()))
        else:
            self.potion_status.setText("No potion drinking")



# Client code
def main():
    """Main function."""
    app = QApplication(sys.argv)
    app.setStyle('Windows')
    view = AppUi()
    view.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
