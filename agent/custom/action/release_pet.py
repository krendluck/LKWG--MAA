from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller


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