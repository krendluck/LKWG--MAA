import time

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size


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