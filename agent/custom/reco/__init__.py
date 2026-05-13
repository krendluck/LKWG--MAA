from importlib import import_module

RECO_MODULES = (
    "auto_launch",
    "release_pet",
    "stone_detect",
    "stone_mine",
)


def register_all():
    for module_name in RECO_MODULES:
        import_module(f"custom.reco.{module_name}")