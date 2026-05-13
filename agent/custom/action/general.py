import json
from pathlib import Path

import numpy as np
from PIL import Image

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller

_debug_counter = 0
_DEBUG_SAVE_ENABLED = False


def _update_image_size(ctrl):
    if ctrl.cached_image is not None:
        bgr = np.asarray(ctrl.cached_image, dtype=np.uint8)
        h, w = bgr.shape[:2]
        get_controller().update_image_size(w, h)


def save_debug(ctrl, name, prefix="debug"):
    global _debug_counter
    if not _DEBUG_SAVE_ENABLED:
        return
    if ctrl.cached_image is None:
        return
    try:
        _debug_counter += 1
        bgr = np.asarray(ctrl.cached_image, dtype=np.uint8)
        rgb = bgr[:, :, ::-1].copy()
        img = Image.fromarray(rgb)
        save_dir = Path("debug/screenshots")
        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / f"{prefix}_{_debug_counter}_{name}.png"
        img.save(str(filepath))
        print(f"[Debug] saved: {filepath}")
    except Exception as e:
        print(f"[Debug] save error: {e}")


@AgentServer.custom_action("TestAct")
class TestAct(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        get_controller().click_key(78)
        return True


@AgentServer.custom_action("ScreenshotSave")
class ScreenshotSave(CustomAction):

    DEFAULT_SAVE_DIR = "debug/screenshots"
    DEFAULT_PREFIX = "screenshot"
    _counter = {}

    def _next_seq(self, key):
        seq = self._counter.get(key, 0) + 1
        self._counter[key] = seq
        return seq

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        node_obj = context.get_node_object("ScreenshotSave")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}

        save_dir = Path(attach.get("save_dir", self.DEFAULT_SAVE_DIR))
        prefix = attach.get("prefix", self.DEFAULT_PREFIX)

        ctrl = context.tasker.controller
        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        if image is None:
            print("[ScreenshotSave] failed: cached_image is None")
            return True

        key = f"{save_dir}/{prefix}"
        seq = self._next_seq(key)

        try:
            bgr = np.asarray(image, dtype=np.uint8)
            rgb = bgr[:, :, ::-1].copy()
            img = Image.fromarray(rgb)
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{prefix}_{seq:03d}.png"
            filepath = save_dir / filename
            img.save(str(filepath))
            print(f"[ScreenshotSave] saved: {filepath}")
        except Exception as e:
            print(f"[ScreenshotSave] error: {e}")

        return True