import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

_debug_counter = 0
_DEBUG_SAVE_ENABLED = False


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
@AgentServer.custom_action("AutoLaunchAct")
class AutoLaunchAct(CustomAction):

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

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        context.tasker.controller.post_click(62, 633).wait()
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
        context.tasker.controller.post_click_key(key_code).wait()
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
                if mine_key_code is not None:
                    ctrl.post_click_key(mine_key_code).wait()
                    time.sleep(0.2)
                ctrl.post_touch_down(click_x, click_y, contact=0).wait()
                time.sleep(hold_duration)
                ctrl.post_touch_up(contact=0).wait()
                time.sleep(0.2)
                if switch_key_code is not None:
                    ctrl.post_click_key(switch_key_code).wait()

        return True


@AgentServer.custom_action("MapTeleportAct")
class MapTeleportAct(CustomAction):

    MAP_NAME_ROI = [98, 659, 100, 27]
    MAP_SWITCH_CLICK = (102 + 54, 476 + 15)
    TELEPORT_ICON_ROI = [87, 147, 33, 34]
    SECONDARY_ICON_ROI = [147, 196, 24, 25]
    TRANSPORT_OCR_ROI = [1000, 661, 44, 32]
    ENTER_CHECK_ROI = [68, 696, 30, 12]
    EXPECTED_MAPS = ["卡洛西亚大陆", "魔法学院"]
    MAX_RETRIES = 3
    MAP_OPEN_RETRIES = 3
    MAX_SCROLL_RETRIES = 10
    DIALOG_ROI = [766, 357, 184, 121]
    DIALOG_WHITE_OFFSET_X = 40
    DIALOG_WHITE_THRESHOLD = 220
    SHOP_ROI = [976, 503, 40, 25]
    BUY_ROI = [989, 664, 73, 27]
    SOLD_OUT_TEXTS = "已售罄"
    SWIPE_START_ROI = [679, 439, 19, 38]
    SWIPE_DIST_X = 240
    SWIPE_STEPS = 10
    CONFIRM_CLICK_ROI = [720, 579, 46, 27]
    SCREEN_CENTER = [960, 540]

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
                    detail = all_results[0].detail if hasattr(all_results[0], 'detail') else ""
                    print(f"[MapTeleport] 当前地图匹配: {detail}")
                break

            any_text_result = context.run_recognition(
                "MapTeleport_AnyText",
                image,
                pipeline_override={"MapTeleport_AnyText": {
                    "recognition": "OCR",
                    "roi": self.MAP_NAME_ROI,
                }},
            )

            if any_text_result is not None and any_text_result.hit:
                print(f"[MapTeleport] 地图已打开但不是目标地图，尝试切换 (第{attempt+1}次)")
                roi = self.MAP_NAME_ROI
                ctrl.post_click(roi[0] + roi[2] // 2, roi[1] + roi[3] // 2).wait()
                time.sleep(0.5)
                ctrl.post_click(*self.MAP_SWITCH_CLICK).wait()
                time.sleep(1.0)
            else:
                print(f"[MapTeleport] 地图可能未打开，等待... (第{attempt+1}次)")
                context.run_task("MapTeleport_OpenMap",
                                pipeline_override={"MapTeleport_OpenMap" :{
                                    "next" :[]
                                }})
                time.sleep(1.0)
        else:
            print(f"[MapTeleport] {self.MAP_OPEN_RETRIES}次尝试后仍未检测到目标地图")
            return False

        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        save_debug(ctrl, "teleport_icon")

        icon_result = context.run_recognition(
            "MapTeleport_FindIcon",
            image,
            pipeline_override={"MapTeleport_FindIcon": {
                "recognition": "TemplateMatch",
                "template": "Map/TeleportIcon.png",
                "roi": self.TELEPORT_ICON_ROI,
                "threshold": 0.7,
            }},
        )

        if icon_result is not None and icon_result.hit:
            box = icon_result.box
            x = box[0] + box[2] // 2
            y = box[1] + box[3] // 2
            print(f"[MapTeleport] 找到传送点图标，点击({x},{y})")
            ctrl.post_click(x, y).wait()
        else:
            roi = self.TELEPORT_ICON_ROI
            x = roi[0] + roi[2] // 2
            y = roi[1] + roi[3] // 2
            print(f"[MapTeleport] 未找到传送点图标(模板)，fallback点击({x},{y})")
            ctrl.post_click(x, y).wait()

        time.sleep(0.5)
        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        save_debug(ctrl, "secondary_icon")

        sec_result = context.run_recognition(
            "MapTeleport_Secondary",
            image,
            pipeline_override={"MapTeleport_Secondary": {
                "recognition": "TemplateMatch",
                "template": "Map/SecondaryIcon.png",
                "roi": self.SECONDARY_ICON_ROI,
                "threshold": 0.7,
            }},
        )

        if sec_result is not None and sec_result.hit:
            box = sec_result.box
            x = box[0] + box[2] // 2
            y = box[1] + box[3] // 2
            print(f"[MapTeleport] 确认二级图标，点击({x},{y})")
            ctrl.post_click(x, y).wait()
        else:
            roi = self.SECONDARY_ICON_ROI
            x = roi[0] + roi[2] // 2
            y = roi[1] + roi[3] // 2
            print(f"[MapTeleport] 未确认二级图标，fallback点击({x},{y})")
            ctrl.post_click(x, y).wait()

        time.sleep(0.3)
        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        save_debug(ctrl, "transport_ocr")

        transport_result = context.run_recognition(
            "MapTeleport_Transport",
            image,
            pipeline_override={"MapTeleport_Transport": {
                "recognition": "OCR",
                "roi": self.TRANSPORT_OCR_ROI,
                "expected": ["传送"],
            }},
        )

        if transport_result is not None and transport_result.hit:
            box = transport_result.box
            x = box[0] + box[2] // 2
            y = box[1] + box[3] // 2
            print(f"[MapTeleport] 找到传送按钮，点击({x},{y})")
            ctrl.post_click(x, y).wait()
        else:
            roi = self.TRANSPORT_OCR_ROI
            x = roi[0] + roi[2] // 2
            y = roi[1] + roi[3] // 2
            print(f"[MapTeleport] 未找到传送按钮(OCR)，fallback点击({x},{y})")
            ctrl.post_click(x, y).wait()

        print("[MapTeleport] 传送完成，等待落地...")
        time.sleep(5)
        for enter_attempt in range(15):
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            save_debug(ctrl, f"enter_check_{enter_attempt}")

            enter_result = context.run_recognition(
                "MapTeleport_EnterCheck",
                image,
                pipeline_override={"MapTeleport_EnterCheck": {
                    "recognition": "OCR",
                    "roi": self.ENTER_CHECK_ROI,
                    "expected": ["Enter"],
                }},
            )

            if enter_result is not None and enter_result.hit:
                print(f"[MapTeleport] 检测到Enter文字，传送完成(第{enter_attempt+1}次)")
                break
            print(f"[MapTeleport] 未检测到Enter，等待(第{enter_attempt+1}次)")
            time.sleep(1.0)
        else:
            print("[MapTeleport] 多次检测后未找到Enter，继续执行")

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
                dialog_box = dialog_result.box
                print(f"[MapTeleport] 找到对话选项 box={dialog_box}")
                break
            print(f"[MapTeleport] 未找到对话选项，等待重试 (第{dialog_attempt+1}次)")
            time.sleep(1.0)
        else:
            print("[MapTeleport] 未找到对话选项，按W键往前走")
            context.run_task("MapTeleport_WalkForward_KeyDown")
            dialog_box = None

        if dialog_box is None:
            for retry in range(3):
                ctrl.post_screencap().wait()
                image = ctrl.cached_image
                if image is None:
                    time.sleep(1.0)
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
                    dialog_box = retry_result.box
                    print(f"[MapTeleport] 走动后找到对话选项 box={dialog_box}")
                    break
                print(f"[MapTeleport] 走动后仍未找到对话选项 (重试{retry+1}/3)")
                time.sleep(1.0)
            else:
                print("[MapTeleport] 走动后仍未找到对话选项")
                return False

        for scroll_attempt in range(self.MAX_SCROLL_RETRIES):
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            save_debug(ctrl, f"dialog_selected_{scroll_attempt}")

            bgr = np.asarray(ctrl.cached_image, dtype=np.uint8)
            if dialog_box is None:
                print("[MapTeleport] dialog_box 为空，跳过选中检测")
                break

            check_x = int(dialog_box[0] + dialog_box[2] + self.DIALOG_WHITE_OFFSET_X)
            check_y = int(dialog_box[1] + dialog_box[3] // 2)

            h, w = bgr.shape[:2]
            if 0 <= check_x < w and 0 <= check_y < h:
                b_val = int(bgr[check_y, check_x, 0])
                g_val = int(bgr[check_y, check_x, 1])
                r_val = int(bgr[check_y, check_x, 2])
                print(f"[MapTeleport] 选中色检测 @({check_x},{check_y}): R={r_val} G={g_val} B={b_val})")

                if r_val > self.DIALOG_WHITE_THRESHOLD and g_val > self.DIALOG_WHITE_THRESHOLD and b_val > self.DIALOG_WHITE_THRESHOLD:
                    print(f"[MapTeleport] 对话选项已选中(第{scroll_attempt+1}次检测)")
                    break
            else:
                print(f"[MapTeleport] 检测坐标超出范围 ({check_x},{check_y})")

            print(f"[MapTeleport] 对话未选中，向下滚动(第{scroll_attempt+1}次)")
            context.run_task("MapTeleport_ScrollDown")
            time.sleep(0.5)

            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            re_dialog = context.run_recognition(
                "MapTeleport_DialogOCR_Rescan",
                image,
                pipeline_override={"MapTeleport_DialogOCR_Rescan": {
                    "recognition": "OCR",
                    "roi": self.DIALOG_ROI,
                    "expected": ["对话"],
                }},
            )
            if re_dialog is not None and re_dialog.hit:
                dialog_box = re_dialog.box
        else:
            print("[MapTeleport] 多次滚动后仍未选中对话")
            return False    

        context.run_task("MapTeleport_PressF")
        print("[MapTeleport] 按F键进入商人")

        for shop_attempt in range(3):
            time.sleep(1.0)
            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                continue

            save_debug(ctrl, f"shop_check_{shop_attempt}")

            shop_result = context.run_recognition(
                "MapTeleport_ShopCheck",
                image,
                pipeline_override={"MapTeleport_ShopCheck": {
                    "recognition": "OCR",
                    "roi": self.SHOP_ROI,
                    "expected": ["商店"],
                }},
            )

            if shop_result is not None and shop_result.hit:
                print(f"[MapTeleport] 找到商店选项(第{shop_attempt+1}次)")
                context.run_task("MapTeleport_Press1")
                print("[MapTeleport] 按1键进入商店")
                break
            print(f"[MapTeleport] 未找到商店选项，等待重试 (第{shop_attempt+1}次)")
        else:
            print("[MapTeleport] 未找到商店选项")
            return False

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
                ctrl.post_click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1]).wait()
                return True

            result = buy_result.all_results[0] if buy_result.all_results else []
            if(result.text == self.SOLD_OUT_TEXTS):
                print(f"[MapTeleport] 检测到已售罄，按ESC退出")
                context.run_task("MapTeleport_PressEsc")
                time.sleep(0.5)
                ctrl.post_click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1]).wait()
                print("[MapTeleport] 已售罄，点击屏幕中心退出")
                return True

            box = buy_result.box
            x = box[0] + box[2] // 2
            y = box[1] + box[3] // 2
            print(f"[MapTeleport] 找到购买按钮，点击({x},{y})")
            ctrl.post_click(x, y).wait()
            time.sleep(0.5)

            swipe_roi = self.SWIPE_START_ROI
            start_x = swipe_roi[0] + swipe_roi[2] // 2
            start_y = swipe_roi[1] + swipe_roi[3] // 2
            end_x = start_x + self.SWIPE_DIST_X

            print(f"[MapTeleport] 滑块拖动 ({start_x},{start_y}) -> ({end_x},{start_y})")
            ctrl.post_touch_down(start_x, start_y, contact=0).wait()
            time.sleep(0.3)
            for i in range(1, self.SWIPE_STEPS + 1):
                move_x = start_x + (self.SWIPE_DIST_X * i // self.SWIPE_STEPS)
                ctrl.post_touch_move(move_x, start_y, contact=0).wait()
                time.sleep(0.02)
            ctrl.post_touch_up(contact=0).wait()
            time.sleep(0.5)

            confirm_roi = self.CONFIRM_CLICK_ROI
            confirm_x = confirm_roi[0] + confirm_roi[2] // 2
            confirm_y = confirm_roi[1] + confirm_roi[3] // 2
            print(f"[MapTeleport] 确认购买点击({confirm_x},{confirm_y})")
            ctrl.post_click(confirm_x, confirm_y).wait()
            time.sleep(1.0)
            ctrl.post_click(confirm_x, confirm_y).wait()
            time.sleep(1.0)

        print("[MapTeleport] 购买循环达到上限，退出")
        context.run_task("MapTeleport_PressEsc")
        time.sleep(0.5)
        ctrl.post_click(self.SCREEN_CENTER[0], self.SCREEN_CENTER[1]).wait()
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


__all__ = [
    "AutoLaunchAct",
    "FocusEnergyAct",
    "AutoReleasePetAct",
    "StoneDetectAct",
    "StoneMinePetAct",
    "MapTeleportAct",
    "ScreenshotSave",
]