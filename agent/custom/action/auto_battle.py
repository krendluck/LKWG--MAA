import re
import time

import numpy as np

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size

_INFINITE_REPEAT = 200

_BACKPACK_ITEM_LABELS = {"1": "进化之力", "2": "能量瓶"}
_CHAR_LABELS = {
    "1": "技能1", "2": "技能2", "3": "技能3", "4": "技能4",
    "x": "聚能", "X": "聚能",
    "q": "打开背包", "Q": "打开背包",
    "r": "关闭背包", "R": "关闭背包",
}

CHAR_TO_VK = {
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "x": 0x58, "X": 0x58,
    "q": 0x51, "Q": 0x51,
    "r": 0x52, "R": 0x52,
}

BACKPACK_ITEMS = {"1": 0x31, "2": 0x32}
MAIN_ACTIONS = {"1", "2", "3", "4", "x", "X"}

_MARK_ICON_POS = (690, 372)
_MARK_COLOR_ROI = [675, 331, 38, 7]
_MARK_COLOR_LOWER = np.array([0, 115, 210], dtype=np.uint8)
_MARK_COLOR_UPPER = np.array([0, 127, 218], dtype=np.uint8)

_MARK_CONFIRM_ROI = [719, 582, 44, 21]


def _expand_skill_order(s):
    s = re.sub(r'\|([^|]+)\|a', lambda m: m.group(1) * _INFINITE_REPEAT, s)
    s = re.sub(r'\|\|([^|]+)', lambda m: m.group(1) * _INFINITE_REPEAT, s)
    s = re.sub(r'\|([^|]+)\|(\d+)', lambda m: m.group(1) * int(m.group(2)), s)
    return s


def _check_mark_color(image):
    bgr = np.asarray(image, dtype=np.uint8)
    x, y, w, h = _MARK_COLOR_ROI
    roi = bgr[y:y + h, x:x + w]
    lower = np.all(roi >= _MARK_COLOR_LOWER, axis=2)
    upper = np.all(roi <= _MARK_COLOR_UPPER, axis=2)
    return np.any(lower & upper)


@AgentServer.custom_action("AutoBattleReset")
class AutoBattleReset(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        AutoBattleAct._skill_index = 0
        AutoBattleAct._round_count = 0
        print("[AutoBattle] 状态重置")
        return True


@AgentServer.custom_action("AutoBattleUseMarkAct")
class AutoBattleUseMarkAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        node_obj = context.get_node_object("AutoBattle_UseMark")
        print(node_obj.attach)
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        use_mark = str(attach.get("use_mark", "false")).lower() == "true"
        if not use_mark:
            print("[AutoBattle] 未启用印记，跳过")
            return True

        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        ic = get_controller()

        for attempt in range(2):
            print(f"[AutoBattle] >>> 点击印记图标 (尝试 {attempt + 1}/2)")
            ic.click(*_MARK_ICON_POS)
            time.sleep(0.5)

            ctrl.post_screencap().wait()
            image = ctrl.cached_image
            if image is None:
                print("[AutoBattle] 截图失败，跳过印记")
                return True

            if _check_mark_color(image):
                print("[AutoBattle] 印记颜色检测通过")
                break
            print(f"[AutoBattle] 印记颜色检测未通过 (尝试 {attempt + 1}/2)")
        else:
            print("[AutoBattle] 印记颜色检测未通过，跳过印记流程")
            return True

        confirm_result = context.run_recognition(
            "MarkConfirmDetect",
            image,
            pipeline_override={"MarkConfirmDetect": {
                "recognition": "OCR",
                "roi": _MARK_CONFIRM_ROI,
                "expected": ["确认"],
            }},
        )
        if confirm_result is None or not confirm_result.hit:
            print("[AutoBattle] 未检测到确认按钮，跳过印记流程")
            return True

        box = confirm_result.box
        if box:
            cx = box[0] + box[2] // 2
            cy = box[1] + box[3] // 2
            print(f"[AutoBattle] >>> 点击确认 ({cx}, {cy})")
            ic.click(cx, cy)
        time.sleep(0.5)

        print("[AutoBattle] >>> 选择目标 (按1)")
        ic.click_key(CHAR_TO_VK["1"])
        time.sleep(0.3)

        print("[AutoBattle] >>> 确认选择 (空格)")
        ic.click_key(0x20)
        time.sleep(5)

        print("[AutoBattle] >>> 关闭结算 (ESC)")
        ic.click_key(0x1B)
        time.sleep(0.5)

        return True


@AgentServer.custom_action("AutoBattleAct")
class AutoBattleAct(CustomAction):

    _skill_index = 0
    _round_count = 0

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        ic = get_controller()

        node_obj = context.get_node_object("AutoBattle_WaitSkill1")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        skill_order = attach.get("skill_order", "||1x")
        skill_order = _expand_skill_order(skill_order.strip())
        if not skill_order:
            return False

        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        if image is not None:
            r_result = context.run_recognition(
                "BattleRCheck", image,
                pipeline_override={"BattleRCheck": {
                    "recognition": "OCR",
                    "roi": [1234, 673, 9, 11],
                    "expected": ["R"],
                }},
            )
            if r_result is None or not r_result.hit:
                print("[AutoBattle] R 不在屏幕上，战斗可能已结束")
                AutoBattleAct._skill_index = 0
                return False

        idx = AutoBattleAct._skill_index
        if idx >= len(skill_order):
            AutoBattleAct._skill_index = 0
            idx = 0
        AutoBattleAct._round_count += 1

        print(f"[AutoBattle] 回合{AutoBattleAct._round_count}, 技能序列: {skill_order}, 当前位置: {idx}")

        while idx < len(skill_order):
            ch = skill_order[idx]
            if ch in ("q", "Q"):
                idx = self._exec_backpack(context, ic, skill_order, idx)
                continue
            if ch in MAIN_ACTIONS:
                label = _CHAR_LABELS.get(ch, ch)
                print(f"[AutoBattle] >>> {label} ({ch})")
                vk = CHAR_TO_VK.get(ch)
                if vk is not None:
                    ic.click_key(vk)
                    time.sleep(0.3)
                idx += 1
                AutoBattleAct._skill_index = idx
                return True
            print(f"[AutoBattle] 跳过未知字符: {ch}")
            idx += 1
            AutoBattleAct._skill_index = idx

        AutoBattleAct._skill_index = 0
        return False

    def _exec_backpack(self, context, ic, skill_order, start_idx):
        print("[AutoBattle] >>> 打开背包 (q)")
        ic.click_key(CHAR_TO_VK["q"])
        time.sleep(0.8)

        idx = start_idx + 1
        while idx < len(skill_order):
            ch = skill_order[idx]
            if ch in BACKPACK_ITEMS:
                label = _BACKPACK_ITEM_LABELS.get(ch, ch)
                print(f"[AutoBattle] >>> 使用{label} ({ch})")
                vk = BACKPACK_ITEMS[ch]
                ic.click_key(vk)
                time.sleep(0.8)
                idx += 1
            elif ch in ("r", "R"):
                idx += 1
                AutoBattleAct._skill_index = idx
                print("[AutoBattle] >>> 等待R出现并关闭背包 (r)")
                context.run_task("AutoBattle_WaitBackpackR")
                context.run_task("AutoBattle_WaitSkill1")
                return idx
            elif ch in ("q", "Q"):
                AutoBattleAct._skill_index = idx
                print("[AutoBattle] >>> 关闭背包后重新打开 (未匹配r，自动关闭)")
                context.run_task("AutoBattle_WaitBackpackR")
                context.run_task("AutoBattle_WaitSkill1")
                return idx
            else:
                print(f"[AutoBattle] 背包内遇到非物品字符: {ch}，自动关闭背包")
                AutoBattleAct._skill_index = idx
                context.run_task("AutoBattle_WaitBackpackR")
                context.run_task("AutoBattle_WaitSkill1")
                return idx

        AutoBattleAct._skill_index = idx
        print("[AutoBattle] >>> 等待R出现并关闭背包 (r)")
        context.run_task("AutoBattle_WaitBackpackR")
        context.run_task("AutoBattle_WaitSkill1")
        return idx