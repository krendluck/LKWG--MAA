import time

import numpy as np

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

from ..interception_controller import get_controller

_switch_keys_stone = [2, 3, 4, 5, 6]
_switch_key_index_stone = 2


@AgentServer.custom_recognition("StoneMinePet_recognition")
class StoneMinePetRecognition(CustomRecognition):

    LABELS = ["black_stone", "blue_coral", "blue_stone", "purple_stone", "red_coral", "yellow_stone"]
    NN_ROI = [288, 8, 704, 704]
    MIN_BOX_W = 22
    MIN_BOX_H = 35
    THRESHOLD = 0.7

    def _check_battle(self, context, image):
        ctrl = context.tasker.controller
        esc_roi = [920, 613, 91, 92]
        confirm_pos = (743, 594)

        try:
            battle_result = context.run_recognition(
                "BattleDetect",
                image,
                pipeline_override={"BattleDetect": {
                    "recognition": "TemplateMatch",
                    "template": "Battle/ESC.png",
                    "roi": esc_roi,
                    "threshold": 0.7,
                }},
            )
        except Exception:
            return False

        if battle_result is None or not battle_result.hit:
            return False

        print("[StoneMinePet] 检测到进入战斗，执行战斗脱离")
        for _ in range(5):
            if ctrl.cached_image is not None:
                bgr = np.asarray(ctrl.cached_image, dtype=np.uint8)
                h, w = bgr.shape[:2]
                get_controller().update_image_size(w, h)
            get_controller().click(920 + 91 // 2, 613 + 92 // 2)
            time.sleep(0.5)
            get_controller().click(*confirm_pos)
            time.sleep(1)

            ctrl.post_screencap().wait()
            new_image = ctrl.cached_image
            check = context.run_recognition(
                "BattleEscCheck",
                new_image,
                pipeline_override={"BattleEscCheck": {
                    "recognition": "TemplateMatch",
                    "template": "Battle/ESC.png",
                    "roi": esc_roi,
                    "threshold": 0.7,
                }},
            )
            if check is None or not check.hit:
                print("[StoneMinePet] 已脱离战斗")
                return True

        print("[StoneMinePet] 脱离战斗超时")
        return True

    def _detect_stones(self, context, image):
        try:
            reco_detail = context.run_recognition(
                "StoneMinePet_NN",
                image,
                pipeline_override={"StoneMinePet_NN": {
                    "recognition": "NeuralNetworkDetect",
                    "roi": self.NN_ROI,
                    "model": "best-704.onnx",
                    "labels": self.LABELS,
                    "threshold": self.THRESHOLD,
                    "order_by": "Score",
                }},
            )
        except Exception:
            return []
        detections = []
        if reco_detail is not None and reco_detail.hit:
            for result in (reco_detail.all_results or []):
                box = list(result.box) if result.box else []
                score = result.score if result.score is not None else 0.0
                label = result.label
                if box and box[2] >= self.MIN_BOX_W and box[3] >= self.MIN_BOX_H:
                    detections.append({
                        "label": label,
                        "box": box,
                        "score": round(score, 4),
                    })
        return detections

    def _resolve_pet(self, context, image):
        global _switch_key_index_stone
        template = "Custom/status.png"
        threshold = 0.85
        slots = [[95,132,23,18],[95,186,23,18],[95,240,23,18],[95,294,23,18],[95,348,23,18]]

        released_nums = set()
        for i, slot in enumerate(slots):
            pet_num = i + 2
            entry = f"mine_pet{pet_num}_check"
            try:
                match_result = context.run_recognition(
                    entry,
                    image,
                    pipeline_override={entry: {
                        "recognition": "TemplateMatch",
                        "template": template,
                        "roi": slot,
                        "threshold": threshold,
                    }},
                )
            except Exception:
                continue
            if match_result is not None and match_result.hit:
                released_nums.add(pet_num)

        unreleased = [n for n in range(2, 7) if n not in released_nums]

        if unreleased:
            mine_num = min(unreleased)
            remaining = [n for n in unreleased if n != mine_num]
            if remaining:
                switch_num = min(remaining)
            else:
                switch_num = mine_num
            mine_key_code = 48 + mine_num
            switch_key_code = 48 + switch_num
        else:
            mine_key_code = 48 + _switch_keys_stone[_switch_key_index_stone]
            switch_key_code = 48 + _switch_keys_stone[(_switch_key_index_stone + 1) % len(_switch_keys_stone)]
            _switch_key_index_stone = (_switch_key_index_stone + 1) % len(_switch_keys_stone)

        return mine_key_code, switch_key_code

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        node_obj = context.get_node_object("StoneMinePet_Entry")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        hold_duration = attach.get("hold_duration", 2)

        self._check_battle(context, argv.image)

        detections = self._detect_stones(context, argv.image)

        if detections:
            mine_key_code, switch_key_code = self._resolve_pet(context, argv.image)
            first = detections[0]
            box = first["box"]
            click_x = box[0] + box[2] // 2
            click_y = box[1] + box[3] // 2
            print(f"[StoneMinePet] 检测到矿石: {first['label']}, score={first['score']}, 点击({click_x},{click_y}), 放宠{mine_key_code}, 切换{switch_key_code}")
            return CustomRecognition.AnalyzeResult(
                box=tuple(box),
                detail={
                    "stone_detected": True,
                    "click_x": click_x,
                    "click_y": click_y,
                    "label": first["label"],
                    "detections": detections,
                    "mine_key_code": mine_key_code,
                    "switch_key_code": switch_key_code,
                    "hold_duration": hold_duration,
                },
            )

        print("[StoneMinePet] 未检测到矿石，继续等待")
        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={},
        )