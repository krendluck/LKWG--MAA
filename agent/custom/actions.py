import json
import time

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
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


__all__ = [
    "AutoLaunchAct",
    "FocusEnergyAct",
    "AutoReleasePetAct",
    "StoneDetectAct",
    "StoneMinePetAct",
]