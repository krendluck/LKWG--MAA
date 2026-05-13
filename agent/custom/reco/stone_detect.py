import json

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context


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

        try:
            reco_detail = context.run_recognition(
                "StoneDetect_NN",
                argv.image,
                pipeline_override={"StoneDetect_NN": {
                    "recognition": "NeuralNetworkDetect",
                    "roi": self.ROI,
                    "model": "best-test.onnx",
                    "labels": self.LABELS,
                    "threshold": self.THRESHOLD,
                    "order_by": "Score",
                }},
            )
        except Exception:
            reco_detail = None
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