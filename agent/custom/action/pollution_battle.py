import time

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size
from .auto_battle import _expand_skill_order, CHAR_TO_VK, MAIN_ACTIONS

_R_ROI = [1234, 673, 9, 11]
_SKILL1_ROI = [152, 259, 10, 13]

_MAIN_ACTION_LABELS = {
    "1": "\u6280\u80fd1", "2": "\u6280\u80fd2", "3": "\u6280\u80fd3", "4": "\u6280\u80fd4",
    "x": "\u805a\u80fd", "X": "\u805a\u80fd",
}


@AgentServer.custom_action("PollutionBattleCycleAct")
class PollutionBattleCycleAct(CustomAction):

    _skill_index = 0
    _in_battle = False

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        ic = get_controller()

        node_obj = context.get_node_object("PollutionBattle_Cycle")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        skill_order = attach.get("skill_order", "|1x|a")
        skill_order = _expand_skill_order(skill_order.strip())

        time.sleep(0.3)

        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        if image is None:
            return True

        r_result = context.run_recognition(
            "PollutionBattleRDetect",
            image,
            pipeline_override={
                "PollutionBattleRDetect": {
                    "recognition": "OCR",
                    "roi": _R_ROI,
                    "expected": ["R"],
                }
            },
        )

        if r_result is None or not r_result.hit:
            if PollutionBattleCycleAct._in_battle:
                print("[PollutionBattle] R \u6d88\u5931\uff0c\u6218\u6597\u7ed3\u675f")
                PollutionBattleCycleAct._in_battle = False
                PollutionBattleCycleAct._skill_index = 0
            return True

        PollutionBattleCycleAct._in_battle = True

        if not skill_order:
            return True

        skill1_result = context.run_recognition(
            "PollutionBattleSkill1Detect",
            image,
            pipeline_override={
                "PollutionBattleSkill1Detect": {
                    "recognition": "OCR",
                    "roi": _SKILL1_ROI,
                    "expected": ["1"],
                }
            },
        )

        if skill1_result is None or not skill1_result.hit:
            return True

        idx = PollutionBattleCycleAct._skill_index
        if idx >= len(skill_order):
            PollutionBattleCycleAct._skill_index = 0
            idx = 0

        ch = skill_order[idx]
        if ch in MAIN_ACTIONS:
            label = _MAIN_ACTION_LABELS.get(ch, ch)
            print(f"[PollutionBattle] >>> {label} ({ch})")
            vk = CHAR_TO_VK.get(ch)
            if vk is not None:
                ic.click_key(vk)
                time.sleep(0.3)
        else:
            print(f"[PollutionBattle] \u8df3\u8fc7\u975e\u6280\u80fd\u5b57\u7b26: {ch}")

        PollutionBattleCycleAct._skill_index = idx + 1
        if PollutionBattleCycleAct._skill_index >= len(skill_order):
            PollutionBattleCycleAct._skill_index = 0

        return True