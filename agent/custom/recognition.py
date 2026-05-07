from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

import json
import time

_switch_keys = [2, 3, 4, 5, 6]
_switch_key_index = 2


@AgentServer.custom_recognition("AutoLaunch_Check")
class AutoLaunchRecognition(CustomRecognition):

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        try:
            param = json.loads(argv.custom_recognition_param or "{}")
        except Exception:
            param = {}
        if "template" not in param:
            raise ValueError("template 参数缺失")
        if "threshold" not in param:
            raise ValueError("threshold 参数缺失")
        if "roi" not in param:
            raise ValueError("roi 参数缺失")

        template = param["template"]
        threshold = param["threshold"]
        roi = param["roi"]

        reco_detail = context.run_recognition(
            "LauchCheck",
            argv.image,
            pipeline_override={"LauchCheck": {
                "recognition": "TemplateMatch",
                "template": template,
                "roi": roi,
                "threshold": threshold,
            }},
        )
        if reco_detail is not None and reco_detail.hit:
            score = 0.0
            if reco_detail.all_results:
                score = reco_detail.all_results[0].score
            return CustomRecognition.AnalyzeResult(
                box=reco_detail.box,
                detail=json.dumps({"hit": True, "score": score, "roi": roi}),
            )
        else:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail=json.dumps({"hit": False}),
            )


@AgentServer.custom_recognition("AutoReleasePet_recognition")
class AutoReleasePetRecognition(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        global _switch_key_index

        battle_result = context.run_recognition(
            "BattleDetect",
            argv.image,
            pipeline_override={"BattleDetect": {
                "recognition": "TemplateMatch",
                "template": "Battle/ESC.png",
                "roi": [920, 613, 91, 92],
                "threshold": 0.7,
            }},
        )
        if battle_result is not None and battle_result.hit:
            print("检测到进入战斗，执行战斗脱离")
            context.run_task("Battle_RunEntry")
            time.sleep(1)

        node_obj = context.get_node_object("AutoReleasePet_Entry")
        attach = getattr(node_obj, "attach", {}) if node_obj else {}
        polling_interval = attach.get("polling_interval")

        template = "Custom/status.png"
        threshold = 0.7
        slots = [[95,132,23,18],[95,186,23,18],[95,240,23,18],[95,294,23,18],[95,348,23,18]]

        released_nums = set()
        for i, slot in enumerate(slots):
            pet_num = i + 2
            entry = f"pet{pet_num}_check"

            try:
                match_result = context.run_recognition(
                    entry,
                    argv.image,
                    pipeline_override={entry: {
                        "recognition": "TemplateMatch",
                        "template": template,
                        "roi": slot,
                        "threshold": threshold,
                    }},
                )
            except Exception:
                continue

            if match_result is None:
                continue

            if match_result.hit:
                released_nums.add(pet_num)
        if released_nums:
            unreleased = [n for n in range(2, 7) if n not in released_nums]
            if unreleased:
                _switch_key_index = 0
                next_num = min(unreleased)
                key_code = 48 + next_num
            else:
                key_num = _switch_keys[_switch_key_index]
                next_num = key_num
                key_code = 48 + key_num
                _switch_key_index = (_switch_key_index + 1) % len(_switch_keys)
                time.sleep(polling_interval)
                print(polling_interval)
        else:
            print("未检测到放出宠物")
            return CustomRecognition.AnalyzeResult(
                box=(0, 0, 1, 1),
                detail={"next_num": 2, "key_code": 50},
            )
        print("检测到放出宠物")
        return CustomRecognition.AnalyzeResult(
            box=(0, 0, 2, 2),
            detail={"next_num": next_num, "key_code": key_code},
        )

@AgentServer.custom_recognition("StoneRecognition_Entry")
class StoneRecognition(CustomRecognition):

    LABELS = ["black_stone", "blue_coral", "blue_stone", "purple_stone", "red_coral", "yellow_stone"]
    ROI = [288, 8, 704, 704]
    THRESHOLD = 0.7

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        reco_detail = context.run_recognition(
            "StoneDetect_NN",
            argv.image,
            pipeline_override={"StoneDetect_NN": {
                "recognition": "NeuralNetworkDetect",
                "roi": self.ROI,
                "model": "best-704.onnx",
                "labels": self.LABELS,
                "threshold": self.THRESHOLD,
                "order_by": "Score",
            }},
        )
        detections = []
        if reco_detail is not None and reco_detail.hit:
            for result in (reco_detail.all_results or []):
                box = list(result.box) if result.box else []
                score = result.score if result.score is not None else 0.0
                label = result.label

                detections.append({
                    "label": label,
                    "box": box,
                    "score": round(score, 4),
                })

        print(f"[StoneRecognition] detected {len(detections)} stones: {detections}")

        if detections:
            first_box = detections[0]["box"]
            return CustomRecognition.AnalyzeResult(
                box=tuple(first_box) if first_box else (0, 0, 2, 2),
                detail={"detections": detections},
            )

        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={"detections": []},
        )


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
        if battle_result is None or not battle_result.hit:
            return False

        print("[StoneMinePet] 检测到进入战斗，执行战斗脱离")
        for _ in range(5):
            ctrl.post_click(920 + 91 // 2, 613 + 92 // 2).wait()
            time.sleep(0.5)
            ctrl.post_click(*confirm_pos).wait()
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
            global _switch_key_index
            mine_key_code = 48 + _switch_keys[_switch_key_index]
            switch_key_code = 48 + _switch_keys[(_switch_key_index + 1) % len(_switch_keys)]
            _switch_key_index = (_switch_key_index + 1) % len(_switch_keys)

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


__all__ = [
    "AutoLaunchRecognition",
    "AutoReleasePetRecognition",
    "StoneRecognition",
    "StoneMinePetRecognition",
]
