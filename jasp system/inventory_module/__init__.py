from .inventory_gui import open_inventory


def __getattr__(name):
    from . import inventory_gui
    return getattr(inventory_gui, name)
