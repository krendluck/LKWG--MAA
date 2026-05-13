from importlib import import_module

ACTION_MODULES = (
    "general",
    "auto_launch",
    "focus_energy",
    "release_pet",
    "stone_detect",
    "stone_mine",
    "map_teleport",
    "interception",
)


def register_all():
    for module_name in ACTION_MODULES:
        import_module(f"custom.action.{module_name}")