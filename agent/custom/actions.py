import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from .interception_controller import get_controller

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
    
@AgentServer.custom_action("AutoLaunchAct")
class AutoLaunchAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reco_detail = argv.reco_detail
        if reco_detail is not None and reco_detail.hit:
            box = reco_detail.box
            if box:
                x = box[0] + box[2] // 2
                y = box[1] + box[3] // 2
                ctrl = context.tasker.controller
                _update_image_size(ctrl)
                get_controller().click(x, y)
                return True
        return False


@AgentServer.custom_action("FocusEnergyAct")
class FocusEnergyAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        x, y = 62, 633
        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        get_controller().click(x, y)
        return True


@AgentServer.custom_action("AutoReleasePetAct")
class AutoReleasePetAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reco_detail = argv.reco_detail
        results = reco_detail.all_results
        detail = results[0].detail

        next_num = detail.get("next_num")
        key_code = detail.get("key_code")
        if next_num is None:
            return False
        get_controller().click_key(key_code)
        return True


@AgentServer.custom_action("StoneDetectAct")
class StoneDetectAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reco_detail = argv.reco_detail
        if reco_detail is None or not reco_detail.hit:
            print("[StoneDetectAct] no detection result")
            return True
        try:
            detail_str = reco_detail.all_results[0].detail if reco_detail.all_results else "{}"
            if isinstance(detail_str, str):
                detail_data = json.loads(detail_str)
            elif isinstance(detail_str, dict):
                detail_data = detail_str
            else:
                detail_data = {}
        except Exception:
            detail_data = {}

        detections = detail_data.get("detections", [])
        for det in detections:
            print(f"[StoneDetectAct] label={det.get('label')}, box={det.get('box')}, score={det.get('score')}")

        return True


@AgentServer.custom_action("StoneMinePetAct")
class StoneMinePetAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reco_detail = argv.reco_detail
        if reco_detail is None or not reco_detail.hit:
            return True

        detail = reco_detail.all_results[0].detail if reco_detail.all_results else {}

        stone_detected = detail.get("stone_detected", False)

        if stone_detected:
            click_x = detail.get("click_x")
            click_y = detail.get("click_y")
            hold_duration = detail.get("hold_duration", 2)
            mine_key_code = detail.get("mine_key_code")
            switch_key_code = detail.get("switch_key_code")
            if click_x is not None and click_y is not None:
                ctrl = context.tasker.controller
                _update_image_size(ctrl)
                if mine_key_code is not None:
                    get_controller().click_key(mine_key_code)
                    time.sleep(0.2)
                get_controller().touch_down(click_x, click_y)
                time.sleep(hold_duration)
                get_controller().touch_up()
                time.sleep(0.2)
                if switch_key_code is not None:
                    get_controller().click_key(switch_key_code)

        return True


@AgentServer.custom_action("MapTeleportVerifyAct")
class MapTeleportVerifyAct(CustomAction):

    MAP_NAME_ROI = [98, 659, 100, 27]
    MAP_SWITCH_CLICK = (102 + 54, 476 + 15)
    EXPECTED_MAPS = ["卡洛西亚大陆", "魔法学院"]
    VALID_MAP_NAMES = ["家园室内", "家园种植园"]
    MAP_OPEN_RETRIES = 3

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller

        for attempt in range(self.MAP_OPEN_RETRIES):
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                print("[MapTeleport] 截图失败")
                time.sleep(1.0)
                continue

            save_debug(ctrl, f"name_check_{attempt}")

            name_result = context.run_recognition(
                "MapTeleport_CheckName",
                image,
                pipeline_override={"MapTeleport_CheckName": {
                    "recognition": "OCR",
                    "roi": self.MAP_NAME_ROI,
                    "expected": self.EXPECTED_MAPS,
                }},
            )
            if name_result is not None and name_result.hit:
                all_results = name_result.all_results if name_result.all_results else []
                if all_results:
                    map_name = all_results[0].text if hasattr(all_results[0], 'text') else ""
                    print(f"[MapTeleport] 当前地图匹配: {map_name}")
                return True

            any_text_result = context.run_recognition(
                "MapTeleport_AnyText",
                image,
                pipeline_override={"MapTeleport_AnyText": {
                    "recognition": "OCR",
                    "roi": self.MAP_NAME_ROI,
                    "expected": self.VALID_MAP_NAMES,
                }},
            )

            if any_text_result is not None and any_text_result.hit:
                print(any_text_result)
                print(f"[MapTeleport] 地图已打开但不是目标地图，尝试切换 (第{attempt+1}次)")
                roi = self.MAP_NAME_ROI
                _update_image_size(ctrl)
                get_controller().click(roi[0] + roi[2] // 2, roi[1] + roi[3] // 2)
                time.sleep(0.5)
                get_controller().click(*self.MAP_SWITCH_CLICK)
                time.sleep(0.5)
            else:
                print(f"[MapTeleport] 地图可能未打开，等待... (第{attempt+1}次)")
                context.run_task("MapTeleport_MainLoop",
                                pipeline_override={"MapTeleport_MainLoop": {
                                    "next": []
                                }})
                time.sleep(1.0)

        print(f"[MapTeleport] {self.MAP_OPEN_RETRIES}次尝试后仍未检测到目标地图")
        return False


@AgentServer.custom_action("MapTeleportFindDialogAct")
class MapTeleportFindDialogAct(CustomAction):

    DIALOG_ROI = [766, 357, 184, 121]

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller

        for dialog_attempt in range(3):
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                time.sleep(1.0)
                continue

            save_debug(ctrl, f"dialog_detect_{dialog_attempt}")

            dialog_result = context.run_recognition(
                "MapTeleport_DialogOCR",
                image,
                pipeline_override={"MapTeleport_DialogOCR": {
                    "recognition": "OCR",
                    "roi": self.DIALOG_ROI,
                    "expected": ["对话"],
                }},
            )

            if dialog_result is not None and dialog_result.hit:
                print(f"[MapTeleport] 找到对话选项 box={dialog_result.box}")
                return True

            print(f"[MapTeleport] 未找到对话选项，等待重试 (第{dialog_attempt+1}次)")
            time.sleep(1.0)

        print("[MapTeleport] 未找到对话选项，按W键往前走")
        context.run_task("MapTeleport_WalkForward_KeyDown")

        for retry in range(3):
            time.sleep(0.5)
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            save_debug(ctrl, f"dialog_retry_{retry}")

            retry_result = context.run_recognition(
                "MapTeleport_DialogOCR",
                image,
                pipeline_override={"MapTeleport_DialogOCR": {
                    "recognition": "OCR",
                    "roi": self.DIALOG_ROI,
                    "expected": ["对话"],
                }},
            )

            if retry_result is not None and retry_result.hit:
                print(f"[MapTeleport] 走动后找到对话选项 box={retry_result.box}")
                return True

            print(f"[MapTeleport] 走动后仍未找到对话选项 (重试{retry+1}/3)")
            time.sleep(0.5)

        print("[MapTeleport] 走动后仍未找到对话选项")
        return False


@AgentServer.custom_action("MapTeleportCheckSelectedAct")
class MapTeleportCheckSelectedAct(CustomAction):

    DIALOG_ROI = [766, 357, 184, 121]
    DIALOG_WHITE_OFFSET_X = 40
    DIALOG_WHITE_THRESHOLD = 220

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller

        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        if image is None:
            return False

        dialog_result = context.run_recognition(
            "MapTeleport_DialogOCR",
            image,
            pipeline_override={"MapTeleport_DialogOCR": {
                "recognition": "OCR",
                "roi": self.DIALOG_ROI,
                "expected": ["对话"],
            }},
        )

        if dialog_result is None or not dialog_result.hit:
            print("[MapTeleport] 未找到对话选项文字，无法检测选中状态")
            return False

        dialog_box = dialog_result.box
        bgr = np.asarray(image, dtype=np.uint8)

        check_x = int(dialog_box[0] + dialog_box[2] + self.DIALOG_WHITE_OFFSET_X)
        check_y = int(dialog_box[1] + dialog_box[3] // 2)

        h, w = bgr.shape[:2]
        if 0 <= check_x < w and 0 <= check_y < h:
            r_val = int(bgr[check_y, check_x, 2])
            g_val = int(bgr[check_y, check_x, 1])
            b_val = int(bgr[check_y, check_x, 0])
            print(f"[MapTeleport] 选中色检测 @({check_x},{check_y}): R={r_val} G={g_val} B={b_val}")

            if r_val > self.DIALOG_WHITE_THRESHOLD and g_val > self.DIALOG_WHITE_THRESHOLD and b_val > self.DIALOG_WHITE_THRESHOLD:
                print("[MapTeleport] 对话选项已选中")
                return True
        else:
            print(f"[MapTeleport] 检测坐标超出范围 ({check_x},{check_y})")

        print("[MapTeleport] 对话未选中")
        return False


@AgentServer.custom_action("MapTeleportBuyLoopAct")
class MapTeleportBuyLoopAct(CustomAction):

    ITEM_LIST_ROI = [64, 70, 391, 648]
    BUY_ROI = [989, 664, 73, 27]
    SOLD_OUT_TEXTS = "已售罄"
    SWIPE_START_ROI = [679, 439, 19, 38]
    SWIPE_DIST_X = 240
    SWIPE_STEPS = 10
    CONFIRM_CLICK_ROI = [720, 579, 46, 27]
    SCREEN_CENTER = [960, 540]

    def _get_wishlist(self, context):
        node_obj = context.get_node_object("MapTeleport_BuyLoop")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        raw = [k[5:] for k, v in attach.items() if k.startswith("_buy_") and v]
        expanded = []
        for item in raw:
            if item == "矿石":
                expanded.extend(["黑", "蓝", "紫", "黄"])
            else:
                expanded.append(item)
        return sorted(expanded)

    def _swipe_and_confirm(self, ctrl):
        swipe_roi = self.SWIPE_START_ROI
        start_x = swipe_roi[0] + swipe_roi[2] // 2
        start_y = swipe_roi[1] + swipe_roi[3] // 2
        end_x = start_x + self.SWIPE_DIST_X

        _update_image_size(ctrl)
        print(f"[MapTeleport] 滑块拖动 ({start_x},{start_y}) -> ({end_x},{start_y})")
        get_controller().touch_down(start_x, start_y)
        time.sleep(0.3)
        for i in range(1, self.SWIPE_STEPS + 1):
            move_x = start_x + (self.SWIPE_DIST_X * i // self.SWIPE_STEPS)
            get_controller().touch_move(move_x, start_y)
            time.sleep(0.02)
        get_controller().touch_up()
        time.sleep(0.5)

        confirm_roi = self.CONFIRM_CLICK_ROI
        confirm_x = confirm_roi[0] + confirm_roi[2] // 2
        confirm_y = confirm_roi[1] + confirm_roi[3] // 2
        print(f"[MapTeleport] 确认购买点击({confirm_x},{confirm_y})")
        get_controller().click(confirm_x, confirm_y)
        time.sleep(1.0)
        get_controller().click(confirm_x, confirm_y)
        time.sleep(1.0)

    def _buy_all(self, ctrl, context):
        for buy_loop in range(5):
            time.sleep(1.0)
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            save_debug(ctrl, f"buy_loop_{buy_loop}")

            buy_result = context.run_recognition(
                "MapTeleport_BuyCheck",
                image,
                pipeline_override={"MapTeleport_BuyCheck": {
                    "recognition": "OCR",
                    "roi": self.BUY_ROI,
                    "expected": ["购买", "已售罄"],
                    "order_by": "Horizontal",
                }},
            )

            if buy_result is None or not buy_result.hit:
                if buy_loop < 3:
                    print(f"[MapTeleport] 未检测到购买区域文字，等待重试 (第{buy_loop+1}次)")
                    continue
                print("[MapTeleport] 多次未检测到购买区域文字")
                context.run_task("MapTeleport_PressEsc")
                time.sleep(0.5)
                _update_image_size(ctrl)
                get_controller().click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1])
                return True

            result = buy_result.all_results[0] if buy_result.all_results else []
            if result.text == self.SOLD_OUT_TEXTS:
                print("[MapTeleport] 检测到已售罄，按ESC退出")
                context.run_task("MapTeleport_PressEsc")
                time.sleep(0.5)
                _update_image_size(ctrl)
                get_controller().click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1])
                return True

            box = buy_result.box
            x = box[0] + box[2] // 2
            y = box[1] + box[3] // 2
            print(f"[MapTeleport] 找到购买按钮，点击({x},{y})")
            _update_image_size(ctrl)
            get_controller().click(x, y)
            time.sleep(0.5)
            self._swipe_and_confirm(ctrl)

        print("[MapTeleport] 购买循环达到上限，退出")
        context.run_task("MapTeleport_PressEsc")
        time.sleep(0.5)
        _update_image_size(ctrl)
        get_controller().click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1])
        return True

    def _match_item(self, item, text):
        return item in text

    def _buy_filtered(self, ctrl, context, wishlist):
        bought = set()

        for item in wishlist:
            if item in bought:
                continue

            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            save_debug(ctrl, f"item_scan_{item}")

            scan_result = context.run_recognition(
                "MapTeleport_ItemScan",
                image,
                pipeline_override={"MapTeleport_ItemScan": {
                    "recognition": "OCR",
                    "roi": self.ITEM_LIST_ROI,
                }},
            )

            if scan_result is None or not scan_result.hit:
                print(f"[MapTeleport] 未在列表中检测到任何物品文字，跳过 {item}")
                continue

            found = False
            for result in (scan_result.all_results or []):
                text = result.text or ""
                if self._match_item(item, text):
                    box = result.box
                    x = box[0] + box[2] // 2
                    y = box[1] + box[3] // 2
                    print(f"[MapTeleport] 找到 {item}(\"{text}\") @({x},{y})，点击")
                    _update_image_size(ctrl)
                    get_controller().click(x, y)
                    time.sleep(0.5)
                    found = True
                    break

            if not found:
                print(f"[MapTeleport] 列表中未找到 {item}，跳过")
                continue

            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            buy_result = context.run_recognition(
                "MapTeleport_BuyCheck",
                image,
                pipeline_override={"MapTeleport_BuyCheck": {
                    "recognition": "OCR",
                    "roi": self.BUY_ROI,
                    "expected": ["购买", "已售罄"],
                    "order_by": "Horizontal",
                }},
            )

            if buy_result is None or not buy_result.hit:
                print(f"[MapTeleport] 未检测到 购买/已售罄，跳过 {item}")
                continue

            result = buy_result.all_results[0] if buy_result.all_results else []
            if result.text == self.SOLD_OUT_TEXTS:
                print(f"[MapTeleport] {item} 已售罄，跳过")
                continue

            box = buy_result.box
            x = box[0] + box[2] // 2
            y = box[1] + box[3] // 2
            print(f"[MapTeleport] 购买 {item}，点击({x},{y})")
            _update_image_size(ctrl)
            get_controller().click(x, y)
            time.sleep(0.5)

            self._swipe_and_confirm(ctrl)
            bought.add(item)
            print(f"[MapTeleport] {item} 购买完成")

        print(f"[MapTeleport] 愿望清单处理完毕，已购买: {bought}")
        context.run_task("MapTeleport_PressEsc")
        time.sleep(0.5)
        _update_image_size(ctrl)
        get_controller().click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1])
        return True

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller
        wishlist = self._get_wishlist(context)

        if not wishlist:
            return self._buy_all(ctrl, context)

        print(f"[MapTeleport] 愿望清单: {wishlist}")
        return self._buy_filtered(ctrl, context, wishlist)


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


@AgentServer.custom_action("InterceptionInput")
class InterceptionInputAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            param = json.loads(argv.custom_action_param or "{}")
        except Exception:
            param = {}

        if isinstance(argv.custom_action_param, dict):
            param = argv.custom_action_param
        elif isinstance(argv.custom_action_param, str):
            try:
                param = json.loads(argv.custom_action_param)
            except Exception:
                param = {}

        action_type = param.get("type", "")
        key = param.get("key")
        target = param.get("target")
        duration = param.get("duration", 500)
        ctrl = get_controller()

        if action_type == "click_key":
            if key is not None:
                ctrl.click_key(key)
                return True

        elif action_type == "long_press_key":
            if key is not None:
                ctrl.long_press_key(key, duration_ms=duration)
                return True

        elif action_type == "key_down":
            if key is not None:
                ctrl.key_down(key)
                return True

        elif action_type == "key_up":
            if key is not None:
                ctrl.key_up(key)
                return True

        elif action_type == "click":
            if target is not None and isinstance(target, list) and len(target) >= 2:
                _update_image_size(context.tasker.controller)
                ctrl.click(target[0], target[1])
                return True

        elif action_type == "click_target":
            reco_detail = argv.reco_detail
            if reco_detail is not None and reco_detail.hit:
                box = reco_detail.box
                if box:
                    x = box[0] + box[2] // 2
                    y = box[1] + box[3] // 2
                    _update_image_size(context.tasker.controller)
                    ctrl.click(x, y)
                    return True

        return False


__all__ = [
    "AutoLaunchAct",
    "FocusEnergyAct",
    "AutoReleasePetAct",
    "StoneDetectAct",
    "StoneMinePetAct",
    "MapTeleportVerifyAct",
    "MapTeleportFindDialogAct",
    "MapTeleportCheckSelectedAct",
    "MapTeleportBuyLoopAct",
    "ScreenshotSave",
    "InterceptionInputAct",
]