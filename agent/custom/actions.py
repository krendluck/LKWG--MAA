import json

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


__all__ = [
    "AutoLaunchAct",
    "FocusEnergyAct",
    "AutoReleasePetAct",
    "StoneDetectAct",
]