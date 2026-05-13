import json

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size


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