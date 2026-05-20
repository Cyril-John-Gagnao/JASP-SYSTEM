import tkinter as tk


_CENTERING_ENABLED = False
_OriginalToplevel = tk.Toplevel


class _CenteredToplevel(_OriginalToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._centered_once = False
        self.bind("<Map>", self._center_on_map, add="+")

    def _center_on_map(self, _event=None):
        if self._centered_once or not self.winfo_exists():
            return
        self._centered_once = True
        self.after_idle(self._center)

    def _center(self):
        if not self.winfo_exists():
            return
        try:
            state = self.state()
        except tk.TclError:
            return
        if state != "normal":
            return
        self.update_idletasks()
        width = max(self.winfo_width(), self.winfo_reqwidth())
        height = max(self.winfo_height(), self.winfo_reqheight())
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")


def enable_centered_toplevels():
    global _CENTERING_ENABLED
    if _CENTERING_ENABLED:
        return
    tk.Toplevel = _CenteredToplevel
    _CENTERING_ENABLED = True


def close_window_and_focus_parent(window, parent=None):
    parent_window = parent
    if parent_window is None:
        try:
            parent_window = window.master
        except tk.TclError:
            parent_window = None

    try:
        if window.grab_current() is window:
            window.grab_release()
    except tk.TclError:
        pass

    if window and window.winfo_exists():
        try:
            window.destroy()
        except tk.TclError:
            pass

    if parent_window and parent_window.winfo_exists():
        try:
            parent_window.deiconify()
            parent_window.lift()
            parent_window.focus_force()
        except tk.TclError:
            pass

