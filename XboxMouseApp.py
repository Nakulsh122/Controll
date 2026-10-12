import sys
import ctypes
import time
from ctypes.wintypes import WORD, DWORD
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QComboBox, QPushButton, QSystemTrayIcon, QMenu, QAction,
                             QSlider, QHBoxLayout)
from PyQt5.QtCore import QThread, Qt
from PyQt5.QtGui import QFont

# ==========================================
# 1. WINDOWS API (Ctypes) FOR LOWEST LATENCY
# ==========================================

class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons", WORD),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", DWORD),
        ("Gamepad", XINPUT_GAMEPAD),
    ]

try:
    xinput = ctypes.windll.xinput1_4
except OSError:
    try:
        xinput = ctypes.windll.xinput1_3
    except OSError:
        xinput = None

def get_controller_state(controller_id):
    if not xinput: return None
    state = XINPUT_STATE()
    if xinput.XInputGetState(controller_id, ctypes.byref(state)) == 0:
        return state
    return None

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

def move_mouse(dx, dy):
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)

def scroll_mouse(amount):
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(amount), 0)

def click_mouse(button="left", down=True):
    if button == "left":
        flag = MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP
    else:
        flag = MOUSEEVENTF_RIGHTDOWN if down else MOUSEEVENTF_RIGHTUP
    ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)

# ==========================================
# 2. BACKGROUND WORKER THREAD
# ==========================================
class ControllerWorker(QThread):
    def __init__(self, controller_id):
        super().__init__()
        self.controller_id = controller_id
        self.running = True
        self.active = True
        
        self.cursor_speed = 20
        self.scroll_speed = 30

    def run(self):
        DEADZONE = 6000
        MAX_VAL = 32768.0
        prev_buttons = 0
        
        while self.running:
            if not self.active:
                time.sleep(0.1)
                continue
                
            state = get_controller_state(self.controller_id)
            if state:
                gp = state.Gamepad
                
                lx, ly = gp.sThumbLX, gp.sThumbLY
                dx = (lx / MAX_VAL) * self.cursor_speed if abs(lx) > DEADZONE else 0
                dy = -(ly / MAX_VAL) * self.cursor_speed if abs(ly) > DEADZONE else 0
                
                if dx != 0 or dy != 0:
                    move_mouse(dx, dy)
                    
                ry = gp.sThumbRY
                if abs(ry) > DEADZONE:
                    scroll = (ry / MAX_VAL) * self.scroll_speed
                    scroll_mouse(scroll)
                    
                buttons = gp.wButtons
                if (buttons & 0x1000) and not (prev_buttons & 0x1000): click_mouse("left", True)
                elif not (buttons & 0x1000) and (prev_buttons & 0x1000): click_mouse("left", False)
                    
                if (buttons & 0x2000) and not (prev_buttons & 0x2000): click_mouse("right", True)
                elif not (buttons & 0x2000) and (prev_buttons & 0x2000): click_mouse("right", False)
                    
                prev_buttons = buttons
                
            time.sleep(0.007)

# ==========================================
# 3. MODERN DARK THEME QSS
# ==========================================
DARK_THEME = """
QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 14px;
}

QLabel {
    color: #e0e0e0;
}

QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 20px;
}

QComboBox::drop-down {
    border-left: 1px solid #444;
    width: 25px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #444;
    selection-background-color: #107C10; 
}

QPushButton {
    background-color: #107C10; /* Xbox Green accent */
    color: white;
    border: none;
    border-radius: 4px;
    padding: 10px 15px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #128c12;
}

QPushButton:pressed {
    background-color: #0b580b;
}

QPushButton:disabled {
    background-color: #333333;
    color: #777777;
}

/* Secondary Button Style */
QPushButton#RefreshBtn {
    background-color: #3a3a3a;
    font-weight: normal;
    padding: 6px 10px;
}
QPushButton#RefreshBtn:hover {
    background-color: #4a4a4a;
}
QPushButton#RefreshBtn:pressed {
    background-color: #2a2a2a;
}

QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #333333;
    border-radius: 3px;
    margin: 2px 0;
}

QSlider::sub-page:horizontal {
    background: #107C10;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #107C10;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #e0e0e0;
}

QMenu {
    background-color: #2b2b2b;
    color: #ffffff;
    border: 1px solid #444;
}

QMenu::item:selected {
    background-color: #107C10;
}
"""

# ==========================================
# 4. GUI AND SYSTEM TRAY
# ==========================================
class XboxMouseApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xbox Mouse Controller")
        self.setFixedSize(320, 360)
        self.worker = None

        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        # Title
        title = QLabel("Xbox Mouse")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #107C10; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Device Selection
        self.combo = QComboBox()
        layout.addWidget(self.combo)
        
        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.setObjectName("RefreshBtn")
        layout.addWidget(self.refresh_btn)

        # --- Speed Sliders ---
        # Cursor
        cursor_layout = QHBoxLayout()
        self.cursor_label = QLabel("Cursor Speed: 20")
        cursor_layout.addWidget(self.cursor_label)
        cursor_layout.addStretch()
        layout.addLayout(cursor_layout)

        self.cursor_slider = QSlider(Qt.Horizontal)
        self.cursor_slider.setMinimum(1)
        self.cursor_slider.setMaximum(100)
        self.cursor_slider.setValue(20)
        self.cursor_slider.valueChanged.connect(self.update_speeds)
        layout.addWidget(self.cursor_slider)

        # Scroll
        scroll_layout = QHBoxLayout()
        self.scroll_label = QLabel("Scroll Speed: 30")
        scroll_layout.addWidget(self.scroll_label)
        scroll_layout.addStretch()
        layout.addLayout(scroll_layout)

        self.scroll_slider = QSlider(Qt.Horizontal)
        self.scroll_slider.setMinimum(1)
        self.scroll_slider.setMaximum(100)
        self.scroll_slider.setValue(30)
        self.scroll_slider.valueChanged.connect(self.update_speeds)
        layout.addWidget(self.scroll_slider)

        layout.addStretch() # Push everything up slightly

        # --- Start Button ---
        self.start_btn = QPushButton("Start && Hide to Tray")
        self.start_btn.clicked.connect(self.start_app)
        layout.addWidget(self.start_btn)

        self.setLayout(layout)

        # Setup System Tray
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        
        self.tray_menu = QMenu()
        
        self.toggle_action = QAction("Stop Translation", self)
        self.toggle_action.triggered.connect(self.toggle_translation)
        self.tray_menu.addAction(self.toggle_action)
        
        self.show_action = QAction("Show GUI", self)
        self.show_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(self.show_action)
        
        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.exit_app)
        self.tray_menu.addAction(self.exit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        # Handle left click (Trigger) and double click to show window
        self.tray_icon.activated.connect(self.tray_icon_clicked)

        self.detect_controllers()

    def update_speeds(self):
        c_speed = self.cursor_slider.value()
        s_speed = self.scroll_slider.value()
        self.cursor_label.setText(f"Cursor Speed: {c_speed}")
        self.scroll_label.setText(f"Scroll Speed: {s_speed}")
        
        if self.worker:
            self.worker.cursor_speed = c_speed
            self.worker.scroll_speed = s_speed

    def detect_controllers(self):
        self.combo.clear()
        found = False
        for i in range(4):
            if get_controller_state(i):
                self.combo.addItem(f"Controller {i+1} (Connected)", i)
                found = True
                
        if not found:
            self.combo.addItem("No controllers found", -1)
            self.start_btn.setEnabled(False)
        else:
            self.start_btn.setEnabled(True)

    def start_app(self):
        selected_data = self.combo.currentData()
        if selected_data == -1: return

        if self.worker is None:
            self.worker = ControllerWorker(selected_data)
            self.update_speeds()
            self.worker.start()

        self.hide()
        self.tray_icon.show()
        self.tray_icon.showMessage("Xbox Mouse", "Running in background. Left click tray icon to show GUI.", QSystemTrayIcon.Information, 2000)

    def toggle_translation(self):
        if self.worker:
            self.worker.active = not self.worker.active
            new_text = "Stop Translation" if self.worker.active else "Resume Translation"
            self.toggle_action.setText(new_text)

    def show_window(self):
        self.show()
        self.tray_icon.hide()
        if self.worker:
            self.cursor_slider.setValue(self.worker.cursor_speed)
            self.scroll_slider.setValue(self.worker.scroll_speed)

    def tray_icon_clicked(self, reason):
        # Trigger = Left click. DoubleClick = Left double click.
        if reason == QSystemTrayIcon.Trigger or reason == QSystemTrayIcon.DoubleClick:
            self.show_window()

    def exit_app(self):
        if self.worker:
            self.worker.running = False
            self.worker.wait()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)
    QApplication.setQuitOnLastWindowClosed(False) 
    window = XboxMouseApp()
    window.show()
    sys.exit(app.exec_())
