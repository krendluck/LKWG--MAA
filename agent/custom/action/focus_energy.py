from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size


@AgentServer.custom_action("FocusEnergyAct")
class FocusEnergyAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        x, y = 62, 633
        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        get_controller().click(x, y)
        return True