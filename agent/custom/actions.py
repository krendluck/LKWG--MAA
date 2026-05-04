"""
游戏基础动作模块

包含自动登录、聚能、自动放宠、鼠标长按映射四个 CustomAction。
"""

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
import json
import time
import random

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.VkKeyScanW.restype = ctypes.c_short
user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]

SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)
class MouseInput(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("mi", MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD),
                ("ii", Input_I)]

def hardware_mouse_press():
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, 0x0002, 0, ctypes.pointer(extra)) # MOUSEEVENTF_LEFTDOWN
    x = Input(0, ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

def hardware_mouse_release():
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, 0x0004, 0, ctypes.pointer(extra)) # MOUSEEVENTF_LEFTUP
    x = Input(0, ii_)
    SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))


@AgentServer.custom_action("AutoLaunchAct")
class AutoLaunchAct(CustomAction):
    """自动登录 - 点击识别到的登录按钮中心"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reco_detail = argv.reco_detail
        if reco_detail is not None and reco_detail.hit:
            box = reco_detail.box
            if box:
                x = box[0] + box[2] // 2
                y = box[1] + box[3] // 2
                context.tasker.controller.post_click(x, y).wait()
                return True
        return False


@AgentServer.custom_action("FocusEnergyAct")
class FocusEnergyAct(CustomAction):
    """聚能 - 点击聚能按钮坐标 (62, 633)"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        context.tasker.controller.post_click(62, 633).wait()
        return True


@AgentServer.custom_action("AutoReleasePetAct")
class AutoReleasePetAct(CustomAction):
    """自动放宠 - 读取识别结果中的按键码并发送"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        
        reco_detail = argv.reco_detail
        results = reco_detail.all_results
        detail = results[0].detail

        next_num = detail.get("next_num")
        key_code = detail.get("key_code")
        if next_num is None:
            return False
        context.tasker.controller.post_click_key(key_code).wait()
        return True

@AgentServer.custom_action("MouseLongPress")
class MouseLongPressAction(CustomAction):

    @staticmethod
    def _key_to_vk(key_str):
        key_str = str(key_str).lower()
        if len(key_str) == 1:
            if key_str == ' ':
                return 0x20
            if key_str.isalnum():
                return user32.VkKeyScanW(key_str) & 0xFF
        return None

    def _is_key_pressed(self, vk_code):
        return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)

    def kb_listen_loop(self, hotkey):
        vk_code = self._key_to_vk(hotkey)
        if vk_code is None:
            print(f"[MouseLongPress] 无法识别按键 '{hotkey}'")
            self.kb_running = False
            return

        print(f"[MouseLongPress] 监听线程启动, 按键='{hotkey}' VK=0x{vk_code:02X}")
        try:
            while self.kb_running:
                if self._is_key_pressed(vk_code):
                    if not self.is_mouse_held:
                        time.sleep(random.uniform(0.01, 0.04))
                        hardware_mouse_press()
                        self.is_mouse_held = True
                        print(f"[MouseLongPress] 按下 '{hotkey}' -> 鼠标按下")
                else:
                    if self.is_mouse_held:
                        time.sleep(random.uniform(0.01, 0.04))
                        hardware_mouse_release()
                        self.is_mouse_held = False
                        print(f"[MouseLongPress] 释放 '{hotkey}' -> 鼠标释放")
                time.sleep(0.01)
        except Exception as e:
            print(f"[MouseLongPress] 监听线程异常: {e}")
            self.kb_running = False
            if self.is_mouse_held:
                hardware_mouse_release()
                self.is_mouse_held = False

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:

        node_obj = context.get_node_object("MouseLongPressEntry")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        key = attach.get("key")
        if not key:
            print("[MouseLongPress] 未配置映射按键，跳过")
            return False

        print(f"[MouseLongPress] 启动监听, 映射按键={key}")

        self.kb_running = True
        self.is_mouse_held = False

        import threading
        kb_listener_thread = threading.Thread(target=self.kb_listen_loop, args=(key,), daemon=True)
        kb_listener_thread.start()
        print("[MouseLongPress] 监听已启动")

        while not context.tasker.stopping:
            time.sleep(0.01)

        self.kb_running = False
        if self.is_mouse_held:
            hardware_mouse_release()
            self.is_mouse_held = False

        print("[MouseLongPress] 监听已停止")
        return True


__all__ = [
    "AutoLaunchAct",
    "FocusEnergyAct",
    "AutoReleasePetAct",
    "MouseLongPressAction",
]
