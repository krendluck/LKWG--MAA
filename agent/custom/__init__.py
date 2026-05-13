# agent/custom/__init__.py
# M9A-style module registration: register_all() triggers @AgentServer decorators
import sys

from . import action
from . import reco

sys.modules.setdefault("custom", sys.modules[__name__])
sys.modules.setdefault("custom.action", action)
sys.modules.setdefault("custom.reco", reco)


def register_all():
    from .action import register_all as reg_action
    from .reco import register_all as reg_reco
    reg_action()
    reg_reco()