# Expose the inventory window opener when importing the inventory module package.
from .inventory_gui import open_inventory


def __getattr__(name):
    # Forward dynamic package attributes to the inventory GUI module.
    from . import inventory_gui
    return getattr(inventory_gui, name)
