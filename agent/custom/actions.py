from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

@AgentServer.custom_action("AutoLaunchAct")
class AutoLaunchAct(CustomAction):
    """自动登录 - 点击识别到的登录按钮中心"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        print(1)
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
    """聚能 - 点击聚能按钮坐标 (62, 633)"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        context.tasker.controller.post_click(62, 633).wait()
        return True


@AgentServer.custom_action("AutoReleasePetAct")
class AutoReleasePetAct(CustomAction):
    """自动放宠 - 读取识别结果中的按键码并发送"""

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

__all__ = [
    "AutoLaunchAct",
    "FocusEnergyAct",
    "AutoReleasePetAct"
]
