import json

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context


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

        try:
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
        except Exception:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail=json.dumps({"hit": False}),
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