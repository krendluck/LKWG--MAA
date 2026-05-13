import re
import time

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size


def _expand_skill_order(s):
    return re.sub(r'\|([^|]+)\|(\d+)', lambda m: m.group(1) * int(m.group(2)), s)

CHAR_TO_VK = {
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "x": 0x58, "X": 0x58,
    "q": 0x51, "Q": 0x51,
    "r": 0x52, "R": 0x52,
}

BACKPACK_ITEMS = {"1": 0x31, "2": 0x32}
MAIN_ACTIONS = {"1", "2", "3", "4", "x", "X"}


@AgentServer.custom_action("AutoBattleAct")
class AutoBattleAct(CustomAction):

    _skill_index = 0

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        ic = get_controller()

        node_obj = context.get_node_object("AutoBattle_WaitSkill1")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        skill_order = attach.get("skill_order", "1x2x3x4x")
        skill_order = _expand_skill_order(skill_order.strip())
        if not skill_order:
            return False

        idx = AutoBattleAct._skill_index % len(skill_order)

        while idx < len(skill_order):
            ch = skill_order[idx]
            if ch in BACKPACK_ITEMS:
                ch = "q"
            if ch in ("q", "Q"):
                idx = self._exec_backpack(ic, skill_order, idx)
                continue
            if ch in MAIN_ACTIONS:
                vk = CHAR_TO_VK.get(ch)
                if vk is not None:
                    ic.click_key(vk)
                    time.sleep(0.3)
                idx += 1
                AutoBattleAct._skill_index = idx % len(skill_order)
                return True
            idx += 1
            AutoBattleAct._skill_index = idx % len(skill_order)

        AutoBattleAct._skill_index = 0
        return True

    def _exec_backpack(self, ic, skill_order, start_idx):
        ic.click_key(CHAR_TO_VK["q"])
        time.sleep(0.8)

        idx = start_idx + 1
        while idx < len(skill_order):
            ch = skill_order[idx]
            if ch in BACKPACK_ITEMS:
                vk = BACKPACK_ITEMS[ch]
                ic.click_key(vk)
                time.sleep(0.5)
                idx += 1
            elif ch in ("r", "R"):
                ic.click_key(CHAR_TO_VK["r"])
                time.sleep(0.3)
                idx += 1
                AutoBattleAct._skill_index = idx % len(skill_order)
                return idx
            else:
                break

        ic.click_key(CHAR_TO_VK["r"])
        time.sleep(0.3)
        AutoBattleAct._skill_index = idx % len(skill_order)
        return idx