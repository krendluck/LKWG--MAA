import time

import numpy as np

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from ..interception_controller import get_controller
from .general import _update_image_size

_DOT_ROI = [310, 180, 9, 9]
_DOT_COLOR_LOWER = np.array([55, 57, 168], dtype=np.uint8)
_DOT_COLOR_UPPER = np.array([62, 62, 181], dtype=np.uint8)
_DOT_CLICK_POS = (314, 184)


@AgentServer.custom_action("DailyClaimRedDotAct")
class DailyClaimRedDotAct(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        ctrl = context.tasker.controller
        _update_image_size(ctrl)
        ic = get_controller()

        ctrl.post_screencap().wait()
        image = ctrl.cached_image
        if image is None:
            print("[DailyClaim] 截图失败")
            return True

        bgr = np.asarray(image, dtype=np.uint8)
        x, y, w, h = _DOT_ROI
        roi = bgr[y:y + h, x:x + w]
        lower = np.all(roi >= _DOT_COLOR_LOWER, axis=2)
        upper = np.all(roi <= _DOT_COLOR_UPPER, axis=2)

        if np.any(lower & upper):
            print("[DailyClaim] 检测到红点，点击领取")
            ic.click(*_DOT_CLICK_POS)
            time.sleep(0.5)
        else:
            print("[DailyClaim] 未检测到红点，跳过领取")

        return True