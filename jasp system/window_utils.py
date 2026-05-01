import tkinter as tk


_CENTERED_TOPOLEVELS_ENABLED = False
_OriginalToplevel = tk.Toplevel


class _CenteredToplevel(_OriginalToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._window_utils_centered = False
        self.bind("<Map>", self._window_utils_center_once, add="+")

    def _window_utils_center_once(self, _event=None):
        if self._window_utils_centered or not self.winfo_exists():
            return
        self._window_utils_centered = True
        self.after_idle(self._window_utils_center)

    def _window_utils_center(self):
        if not self.winfo_exists():
            return
        if self.winfo_state() != "normal":
            return
        self.update_idletasks()
        width = max(self.winfo_width(), self.winfo_reqwidth())
        height = max(self.winfo_height(), self.winfo_reqheight())
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")


def enable_centered_toplevels():
    global _CENTERED_TOPOLEVELS_ENABLED
    if _CENTERED_TOPOLEVELS_ENABLED:
        return
    tk.Toplevel = _CenteredToplevel
    _CENTERED_TOPOLEVELS_ENABLED = True
