import json

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context


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