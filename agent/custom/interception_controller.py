"""
Interception 驱动输入控制器

使用 Interception 内核驱动发送底层键盘扫描码和鼠标事件，
绕过游戏 RawInput 输入保护。

使用方法:
    1. 确保 Interception 驱动已安装并重启电脑
    2. get_controller() 获取全局单例
    3. 调用各类输入方法
"""

import ctypes
import ctypes.wintypes
import os
import threading
import time
import traceback
from pathlib import Path

# --- Constants ---

INTERCEPTION_MAX_DEVICE = 20

INTERCEPTION_KEY_DOWN = 0x00
INTERCEPTION_KEY_UP = 0x01
INTERCEPTION_KEY_E0 = 0x02
INTERCEPTION_KEY_E1 = 0x04

INTERCEPTION_FILTER_KEY_ALL = 0xFFFF
INTERCEPTION_FILTER_KEY_DOWN = INTERCEPTION_KEY_UP
INTERCEPTION_FILTER_KEY_UP = INTERCEPTION_KEY_UP << 1
INTERCEPTION_FILTER_MOUSE_ALL = 0xFFFF

INTERCEPTION_MOUSE_MOVE_RELATIVE = 0x000
INTERCEPTION_MOUSE_MOVE_ABSOLUTE = 0x001
INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN = 0x001
INTERCEPTION_MOUSE_LEFT_BUTTON_UP = 0x002
INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN = 0x004
INTERCEPTION_MOUSE_RIGHT_BUTTON_UP = 0x008
INTERCEPTION_MOUSE_MIDDLE_BUTTON_DOWN = 0x010
INTERCEPTION_MOUSE_MIDDLE_BUTTON_UP = 0x020

# --- Scan Code Tables ---

SCANCODE_MAP = {
    "ESC": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "Minus": 0x0C, "Equals": 0x0D, "Backspace": 0x0E, "Tab": 0x0F,
    "Q": 0x10, "W": 0x11, "E": 0x12, "R": 0x13, "T": 0x14,
    "Y": 0x15, "U": 0x16, "I": 0x17, "O": 0x18, "P": 0x19,
    "LeftBracket": 0x1A, "RightBracket": 0x1B, "Enter": 0x1C,
    "LeftCtrl": 0x1D, "A": 0x1E, "S": 0x1F, "D": 0x20,
    "F": 0x21, "G": 0x22, "H": 0x23, "J": 0x24, "K": 0x25, "L": 0x26,
    "Semicolon": 0x27, "Apostrophe": 0x28, "Grave": 0x29,
    "LeftShift": 0x2A, "Backslash": 0x2B,
    "Z": 0x2C, "X": 0x2D, "C": 0x2E, "V": 0x2F, "B": 0x30,
    "N": 0x31, "M": 0x32, "Comma": 0x33, "Period": 0x34, "Slash": 0x35,
    "RightShift": 0x36, "LeftAlt": 0x38, "Space": 0x39,
    "CapsLock": 0x3A,
    "F1": 0x3B, "F2": 0x3C, "F3": 0x3D, "F4": 0x3E,
    "F5": 0x3F, "F6": 0x40, "F7": 0x41, "F8": 0x42,
    "F9": 0x43, "F10": 0x44, "F11": 0x57, "F12": 0x58,
    "NumpadAdd": 0x4E,
    "Up": 0x48, "Down": 0x50, "Left": 0x4B, "Right": 0x4D,
    "Insert": 0x52, "Delete": 0x53, "Home": 0x47, "End": 0x4F,
    "PageUp": 0x49, "PageDown": 0x51,
}

EXTENDED_KEYS = {
    "Up", "Down", "Left", "Right",
    "Insert", "Delete", "Home", "End", "PageUp", "PageDown",
    "LeftCtrl", "RightCtrl",
    "LeftAlt", "RightAlt",
    "NumpadAdd",
}

# Virtual Key Code -> (scancode, is_extended)
VK_TO_SCANCODE = {
    0x08: (0x0E, False),   # VK_BACK
    0x09: (0x0F, False),   # VK_TAB
    0x0D: (0x1C, False),   # VK_RETURN
    0x10: (0x2A, False),   # VK_SHIFT (left)
    0x11: (0x1D, False),   # VK_CONTROL (left)
    0x12: (0x38, False),   # VK_MENU (left alt)
    0x13: (0x45, False),   # VK_PAUSE
    0x14: (0x3A, False),   # VK_CAPITAL
    0x1B: (0x01, False),   # VK_ESCAPE
    0x20: (0x39, False),   # VK_SPACE
    0x21: (0x49, True),    # VK_PRIOR (PageUp)
    0x22: (0x51, True),    # VK_NEXT (PageDown)
    0x23: (0x4F, True),    # VK_END
    0x24: (0x47, True),    # VK_HOME
    0x25: (0x4B, True),    # VK_LEFT
    0x26: (0x48, True),    # VK_UP
    0x27: (0x4D, True),    # VK_RIGHT
    0x28: (0x50, True),    # VK_DOWN
    0x2C: (0x52, True),    # VK_SNAPSHOT (PrintScreen)
    0x2D: (0x53, True),    # VK_INSERT
    0x2E: (0x53, True),    # VK_DELETE
    # 0-9 (same order as keyboard top row)
    0x30: (0x0B, False),   # 0
    0x31: (0x02, False),   # 1
    0x32: (0x03, False),   # 2
    0x33: (0x04, False),   # 3
    0x34: (0x05, False),   # 4
    0x35: (0x06, False),   # 5
    0x36: (0x07, False),   # 6
    0x37: (0x08, False),   # 7
    0x38: (0x09, False),   # 8
    0x39: (0x0A, False),   # 9
    # A-Z
    0x41: (0x1E, False),   # A
    0x42: (0x30, False),   # B
    0x43: (0x2E, False),   # C
    0x44: (0x20, False),   # D
    0x45: (0x12, False),   # E
    0x46: (0x21, False),   # F
    0x47: (0x22, False),   # G
    0x48: (0x23, False),   # H
    0x49: (0x17, False),   # I
    0x4A: (0x24, False),   # J
    0x4B: (0x25, False),   # K
    0x4C: (0x26, False),   # L
    0x4D: (0x32, False),   # M
    0x4E: (0x31, False),   # N
    0x4F: (0x18, False),   # O
    0x50: (0x19, False),   # P
    0x51: (0x10, False),   # Q
    0x52: (0x13, False),   # R
    0x53: (0x1F, False),   # S
    0x54: (0x14, False),   # T
    0x55: (0x16, False),   # U
    0x56: (0x2F, False),   # V
    0x57: (0x11, False),   # W
    0x58: (0x2D, False),   # X
    0x59: (0x15, False),   # Y
    0x5A: (0x2C, False),   # Z
    # Numpad
    0x60: (0x52, False),   # VK_NUMPAD0
    0x61: (0x4F, False),   # VK_NUMPAD1
    0x62: (0x50, False),   # VK_NUMPAD2
    0x63: (0x51, False),   # VK_NUMPAD3
    0x64: (0x4B, False),   # VK_NUMPAD4
    0x65: (0x4C, False),   # VK_NUMPAD5
    0x66: (0x4D, False),   # VK_NUMPAD6
    0x67: (0x47, False),   # VK_NUMPAD7
    0x68: (0x48, False),   # VK_NUMPAD8
    0x69: (0x49, False),   # VK_NUMPAD9
    0x6A: (0x37, False),   # VK_MULTIPLY
    0x6B: (0x4E, False),   # VK_ADD
    0x6D: (0x4A, False),   # VK_SUBTRACT
    0x6E: (0x53, False),   # VK_DECIMAL
    0x6F: (0x35, True),    # VK_DIVIDE
    # F1-F12
    0x70: (0x3B, False),   # VK_F1
    0x71: (0x3C, False),   # VK_F2
    0x72: (0x3D, False),   # VK_F3
    0x73: (0x3E, False),   # VK_F4
    0x74: (0x3F, False),   # VK_F5
    0x75: (0x40, False),   # VK_F6
    0x76: (0x41, False),   # VK_F7
    0x77: (0x42, False),   # VK_F8
    0x78: (0x43, False),   # VK_F9
    0x79: (0x44, False),   # VK_F10
    0x7A: (0x57, False),   # VK_F11
    0x7B: (0x58, False),   # VK_F12
    # Modifier extended keys
    0xA0: (0x2A, False),   # VK_LSHIFT
    0xA1: (0x36, False),   # VK_RSHIFT
    0xA2: (0x1D, False),   # VK_LCONTROL
    0xA3: (0x1D, True),    # VK_RCONTROL
    0xA4: (0x38, False),   # VK_LMENU
    0xA5: (0x38, True),    # VK_RMENU
    # OEM keys
    0xBA: (0x27, False),   # VK_OEM_1 (;:)
    0xBB: (0x0D, False),   # VK_OEM_PLUS (=+)
    0xBC: (0x33, False),   # VK_OEM_COMMA (,<)
    0xBD: (0x0C, False),   # VK_OEM_MINUS (-_)
    0xBE: (0x34, False),   # VK_OEM_PERIOD (.>)
    0xBF: (0x35, False),   # VK_OEM_2 (/?)
    0xC0: (0x29, False),   # VK_OEM_3 (`~)
    0xDB: (0x1A, False),   # VK_OEM_4 ([{)
    0xDC: (0x2B, False),   # VK_OEM_5 (\|)
    0xDD: (0x1B, False),   # VK_OEM_6 (]})
    0xDE: (0x28, False),   # VK_OEM_7 ('")
}


def vk_to_scancode(vk_code):
    entry = VK_TO_SCANCODE.get(vk_code)
    if entry is None:
        return None, False
    return entry[0], entry[1]


# --- CTypes Structures ---

class KeyStroke(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("state", ctypes.c_ushort),
        ("information", ctypes.c_uint),
    ]


class MouseStroke(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_ushort),
        ("flags", ctypes.c_ushort),
        ("rolling", ctypes.c_short),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("information", ctypes.c_uint),
    ]


# --- DLL Resolution ---

def _find_interception_dll():
    base = Path(__file__).parent.parent.parent
    candidates = [
        base / "assets" / "resource" / "base" / "Dll" / "interception.dll",
        Path.cwd() / "assets" / "resource" / "base" / "Dll" / "interception.dll",
        Path.cwd() / "resource" / "base" / "Dll" / "interception.dll",
        Path.cwd() / "interception.dll",
    ]
    for p in candidates:
        if p.exists():
            return str(p.resolve())

    for p in base.rglob("interception.dll"):
        return str(p.resolve())

    raise FileNotFoundError(
        "Cannot find interception.dll. Searched:\n" +
        "\n".join(f"  {p}" for p in candidates)
    )


# --- InterceptionController ---

class InterceptionController:
    """Manages the Interception driver context and provides input methods."""

    def __init__(self, dll_path=None):
        if dll_path is None:
            dll_path = _find_interception_dll()
        self.dll_path = dll_path
        self.dll = None
        self.context = None
        self.keyboard_device = None
        self.mouse_device = None
        self._passthrough_thread = None
        self._running = False
        self._initialized = False
        self._screen_width = 0
        self._screen_height = 0
        self.image_width = 1280
        self.image_height = 720
        self._window_hwnd = None
        self._window_rect = None

    def _setup_api(self):
        dll = self.dll

        dll.interception_create_context.restype = ctypes.c_void_p
        dll.interception_create_context.argtypes = []

        dll.interception_destroy_context.restype = None
        dll.interception_destroy_context.argtypes = [ctypes.c_void_p]

        self._is_keyboard_cb = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)(
            dll.interception_is_keyboard
        )
        self._is_mouse_cb = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)(
            dll.interception_is_mouse
        )

        dll.interception_set_filter.restype = None
        dll.interception_set_filter.argtypes = [
            ctypes.c_void_p, ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int), ctypes.c_ushort
        ]

        dll.interception_wait.restype = ctypes.c_int
        dll.interception_wait.argtypes = [ctypes.c_void_p]

        dll.interception_wait_with_timeout.restype = ctypes.c_int
        dll.interception_wait_with_timeout.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong
        ]

        dll.interception_send.restype = ctypes.c_int
        dll.interception_send.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint
        ]

        dll.interception_receive.restype = ctypes.c_int
        dll.interception_receive.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint
        ]

        dll.interception_is_keyboard.restype = ctypes.c_int
        dll.interception_is_keyboard.argtypes = [ctypes.c_int]

        dll.interception_is_mouse.restype = ctypes.c_int
        dll.interception_is_mouse.argtypes = [ctypes.c_int]

        dll.interception_is_invalid.restype = ctypes.c_int
        dll.interception_is_invalid.argtypes = [ctypes.c_int]

        dll.interception_get_hardware_id.restype = ctypes.c_uint
        dll.interception_get_hardware_id.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint
        ]

    def initialize(self):
        if self._initialized:
            return

        self.dll = ctypes.CDLL(self.dll_path)
        self._setup_api()

        self.context = self.dll.interception_create_context()
        if not self.context:
            raise RuntimeError(
                "Failed to create Interception context. "
                "Ensure the driver is installed and the system has been rebooted."
            )

        user32 = ctypes.windll.user32
        self._screen_width = user32.GetSystemMetrics(0)
        self._screen_height = user32.GetSystemMetrics(1)

        self._initialized = True
        print(f"[Interception] Context created: 0x{self.context:X}")
        print(f"[Interception] Screen: {self._screen_width}x{self._screen_height}")
        print(f"[Interception] DLL: {self.dll_path}")

    def create_context(self):
        self.initialize()

    def destroy_context(self):
        self.stop_passthrough()
        if self.context:
            self.dll.interception_destroy_context(self.context)
            self.context = None
        self._initialized = False

    # --- Device Discovery ---

    def set_keyboard_filter(self, filter_mode=INTERCEPTION_FILTER_KEY_ALL):
        self.dll.interception_set_filter(
            self.context, self._is_keyboard_cb, filter_mode
        )

    def set_mouse_filter(self, filter_mode=INTERCEPTION_FILTER_MOUSE_ALL):
        self.dll.interception_set_filter(
            self.context, self._is_mouse_cb, filter_mode
        )

    def _send_key_stroke(self, device, stroke):
        ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
        return self.dll.interception_send(self.context, device, ptr, 1)

    def _send_mouse_stroke(self, device, stroke):
        ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
        return self.dll.interception_send(self.context, device, ptr, 1)

    def _receive_stroke(self, device):
        stroke = KeyStroke()
        ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
        result = self.dll.interception_receive(self.context, device, ptr, 1)
        return stroke, result

    def _receive_mouse_stroke(self, device):
        stroke = MouseStroke()
        ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
        result = self.dll.interception_receive(self.context, device, ptr, 1)
        return stroke, result

    def is_keyboard(self, device):
        return self.dll.interception_is_keyboard(device) > 0

    def is_mouse(self, device):
        return self.dll.interception_is_mouse(device) > 0

    def is_invalid(self, device):
        return self.dll.interception_is_invalid(device) > 0

    def get_hardware_id(self, device, size=512):
        buf = ctypes.create_string_buffer(size)
        self.dll.interception_get_hardware_id(self.context, device, buf, size)
        return buf.value.decode("utf-8", errors="replace")

    def discover_keyboard_device(self, timeout_ms=20000):
        if self.keyboard_device is not None:
            return True

        for i in range(1, INTERCEPTION_MAX_DEVICE + 1):
            if self.is_keyboard(i):
                self.keyboard_device = i
                try:
                    hw_id = self.get_hardware_id(i)
                except Exception:
                    hw_id = "(unknown)"
                print(f"[Interception] Keyboard (enum): device={i}, hwid=\"{hw_id}\"")
                return True

        # Enumeration failed — need at least one real keystroke
        self.set_keyboard_filter(INTERCEPTION_FILTER_KEY_ALL)
        print(f"[Interception] Enumerating keyboard… "
              f"Waiting {timeout_ms / 1000:.0f}s for any keypress (passthrough enabled)")

        start_time = time.time()
        while True:
            elapsed = (time.time() - start_time) * 1000
            remaining = int(timeout_ms - elapsed)
            if remaining <= 0:
                break

            device = self.dll.interception_wait_with_timeout(
                self.context, min(remaining, 3000)
            )
            if self.is_invalid(device):
                continue

            if self.is_keyboard(device):
                self.keyboard_device = device
                try:
                    hw_id = self.get_hardware_id(device)
                except Exception:
                    hw_id = "(unknown)"
                print(f"[Interception] Keyboard: device={device}, hwid=\"{hw_id}\"")

                stroke, _ = self._receive_stroke(device)
                self._send_key_stroke(device, stroke)
                return True
            else:
                stroke, _ = self._receive_stroke(device)
                self._send_key_stroke(device, stroke)

        print("[Interception] Keyboard not discovered (no input in timeout window)")
        return False

    def discover_mouse_device(self):
        self.set_mouse_filter(INTERCEPTION_FILTER_MOUSE_ALL)
        for i in range(1, INTERCEPTION_MAX_DEVICE + 1):
            if self.is_mouse(i):
                self.mouse_device = i
                try:
                    hw_id = self.get_hardware_id(i)
                except Exception:
                    hw_id = "(unknown)"
                print(f"[Interception] Mouse: device={i}, hwid=\"{hw_id}\"")
                return True

        print("[Interception] No mouse device found via enumeration")
        return False

    # --- Window / Coordinate Handling ---

    def set_window_hwnd(self, hwnd):
        self._window_hwnd = hwnd
        self._update_window_rect()

    def _update_window_rect(self):
        if self._window_hwnd is None:
            self._window_rect = None
            return
        user32 = ctypes.windll.user32
        rect = ctypes.wintypes.RECT()
        if user32.GetWindowRect(self._window_hwnd, ctypes.byref(rect)):
            self._window_rect = (rect.left, rect.top, rect.right, rect.bottom)

    def _image_to_screen(self, img_x, img_y):
        if self._window_rect:
            wx, wy, wr, wb = self._window_rect
        else:
            wx, wy = 0, 0
            wr, wb = self._screen_width, self._screen_height

        scale_x = (wr - wx) / max(self.image_width, 1)
        scale_y = (wb - wy) / max(self.image_height, 1)
        sx = int(wx + img_x * scale_x)
        sy = int(wy + img_y * scale_y)
        return sx, sy

    def _screen_to_interception(self, sx, sy):
        ix = int(sx * 65535 / max(self._screen_width, 1))
        iy = int(sy * 65535 / max(self._screen_height, 1))
        return ix, iy

    # --- Passthrough ---

    def _passthrough_loop(self):
        while self._running:
            try:
                device = self.dll.interception_wait_with_timeout(self.context, 200)
                if self.is_invalid(device):
                    continue

                if self.is_keyboard(device):
                    stroke = KeyStroke()
                    ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
                    result = self.dll.interception_receive(
                        self.context, device, ptr, 1
                    )
                    if result > 0:
                        self.dll.interception_send(
                            self.context, device, ptr, 1
                        )
                elif self.is_mouse(device):
                    stroke = MouseStroke()
                    ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
                    result = self.dll.interception_receive(
                        self.context, device, ptr, 1
                    )
                    if result > 0:
                        self.dll.interception_send(
                            self.context, device, ptr, 1
                        )
                else:
                    # Other device type - still forward
                    stroke = KeyStroke()
                    ptr = ctypes.cast(ctypes.pointer(stroke), ctypes.c_void_p)
                    result = self.dll.interception_receive(
                        self.context, device, ptr, 1
                    )
                    if result > 0:
                        self.dll.interception_send(
                            self.context, device, ptr, 1
                        )
            except Exception:
                if self._running:
                    traceback.print_exc()
                break

    def start_passthrough(self):
        if self._passthrough_thread and self._passthrough_thread.is_alive():
            return
        self.set_keyboard_filter(INTERCEPTION_FILTER_KEY_ALL)
        if self.mouse_device is not None:
            self.set_mouse_filter(INTERCEPTION_FILTER_MOUSE_ALL)
        self._running = True
        self._passthrough_thread = threading.Thread(
            target=self._passthrough_loop, daemon=True
        )
        self._passthrough_thread.start()
        print("[Interception] Passthrough thread started")

    def stop_passthrough(self):
        self._running = False
        if self._passthrough_thread and self._passthrough_thread.is_alive():
            self._passthrough_thread.join(timeout=3)
            self._passthrough_thread = None

    # --- High-Level Input Methods ---

    def _send_key_event(self, scancode, state):
        stroke = KeyStroke()
        stroke.code = scancode
        stroke.state = state
        stroke.information = 0
        return self._send_key_stroke(self.keyboard_device, stroke)

    def _send_mouse_event(self, state, flags, x=0, y=0, rolling=0):
        stroke = MouseStroke()
        stroke.state = state
        stroke.flags = flags
        stroke.rolling = rolling
        stroke.x = x
        stroke.y = y
        stroke.information = 0
        return self._send_mouse_stroke(self.mouse_device, stroke)

    def click_key(self, vk_code, delay=0.05):
        scancode, extended = vk_to_scancode(vk_code)
        if scancode is None:
            print(f"[Interception] Unknown VK: 0x{vk_code:02X} ({vk_code})")
            return False
        if self.keyboard_device is None:
            print("[Interception] No keyboard device")
            return False

        e0 = INTERCEPTION_KEY_E0 if extended else 0
        self._send_key_event(scancode, INTERCEPTION_KEY_DOWN | e0)
        time.sleep(delay)
        self._send_key_event(scancode, INTERCEPTION_KEY_UP | e0)
        time.sleep(delay)
        return True

    def long_press_key(self, vk_code, duration_ms=500, delay=0.05):
        scancode, extended = vk_to_scancode(vk_code)
        if scancode is None:
            print(f"[Interception] Unknown VK: 0x{vk_code:02X} ({vk_code})")
            return False
        if self.keyboard_device is None:
            return False

        e0 = INTERCEPTION_KEY_E0 if extended else 0
        self._send_key_event(scancode, INTERCEPTION_KEY_DOWN | e0)
        time.sleep(duration_ms / 1000.0)
        self._send_key_event(scancode, INTERCEPTION_KEY_UP | e0)
        time.sleep(delay)
        return True

    def key_down(self, vk_code):
        scancode, extended = vk_to_scancode(vk_code)
        if scancode is None:
            return False
        if self.keyboard_device is None:
            return False
        e0 = INTERCEPTION_KEY_E0 if extended else 0
        self._send_key_event(scancode, INTERCEPTION_KEY_DOWN | e0)
        return True

    def key_up(self, vk_code):
        scancode, extended = vk_to_scancode(vk_code)
        if scancode is None:
            return False
        if self.keyboard_device is None:
            return False
        e0 = INTERCEPTION_KEY_E0 if extended else 0
        self._send_key_event(scancode, INTERCEPTION_KEY_UP | e0)
        return True

    def _coord_to_interception(self, img_x, img_y):
        sx, sy = self._image_to_screen(img_x, img_y)
        return self._screen_to_interception(sx, sy)

    def click(self, x, y, delay=0.05):
        if self.mouse_device is None:
            print("[Interception] No mouse device")
            return False

        ix, iy = self._coord_to_interception(x, y)
        self._send_mouse_event(
            INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN,
            INTERCEPTION_MOUSE_MOVE_ABSOLUTE,
            x=ix, y=iy
        )
        time.sleep(delay)
        self._send_mouse_event(
            INTERCEPTION_MOUSE_LEFT_BUTTON_UP,
            INTERCEPTION_MOUSE_MOVE_ABSOLUTE,
            x=ix, y=iy
        )
        time.sleep(delay)
        return True

    def touch_down(self, x, y, delay=0.05):
        if self.mouse_device is None:
            return False

        ix, iy = self._coord_to_interception(x, y)
        self._send_mouse_event(
            INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN,
            INTERCEPTION_MOUSE_MOVE_ABSOLUTE,
            x=ix, y=iy
        )
        time.sleep(delay)
        return True

    def touch_move(self, x, y, delay=0.02):
        if self.mouse_device is None:
            return False

        ix, iy = self._coord_to_interception(x, y)
        self._send_mouse_event(
            0,
            INTERCEPTION_MOUSE_MOVE_ABSOLUTE,
            x=ix, y=iy
        )
        time.sleep(delay)
        return True

    def touch_up(self, delay=0.05):
        if self.mouse_device is None:
            return False

        self._send_mouse_event(
            INTERCEPTION_MOUSE_LEFT_BUTTON_UP,
            INTERCEPTION_MOUSE_MOVE_ABSOLUTE
        )
        time.sleep(delay)
        return True

    def update_image_size(self, width, height):
        self.image_width = width
        self.image_height = height

    def shutdown(self):
        self.stop_passthrough()
        self.destroy_context()
        print("[Interception] Shutdown complete")


# --- Module-Level Singleton ---

_controller_instance = None


def get_controller(dll_path=None):
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = InterceptionController(dll_path)
    return _controller_instance
