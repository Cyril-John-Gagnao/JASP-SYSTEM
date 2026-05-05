import os
import tkinter as tk


DASHBOARD_HEADER_BG = "#072a4e"
DASHBOARD_HEADER_BORDER = "#041d36"
DASHBOARD_CONTENT_BG = "#fff3e6"
DASHBOARD_HEADER_FG = "white"
DASHBOARD_HEADER_SUBTLE_FG = "#eff6ff"


def logo_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "images", "logo1.png"))


def load_logo_image(size=48):
    path = logo_path()
    try:
        from PIL import Image, ImageDraw, ImageTk

        logo_source = Image.open(path).convert("RGBA")
        logo_source.thumbnail((size, size), Image.LANCZOS)
        rounded_logo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        x_pos = (size - logo_source.width) // 2
        y_pos = (size - logo_source.height) // 2
        rounded_logo.paste(logo_source, (x_pos, y_pos), logo_source)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        rounded_logo.putalpha(mask)
        return ImageTk.PhotoImage(rounded_logo)
    except (ImportError, tk.TclError, OSError, AttributeError):
        try:
            image = tk.PhotoImage(file=path)
            return image.subsample(max(1, image.width() // size), max(1, image.height() // size))
        except tk.TclError:
            return None


def add_header_logo(parent, bg, size=52):
    logo_image = load_logo_image(size)
    if logo_image:
        parent.logo_image = logo_image
        tk.Label(parent, image=logo_image, bg=bg).pack(side="left", padx=(0, 12))
        return

    tk.Label(
        parent,
        text="JASP",
        bg=bg,
        fg=DASHBOARD_HEADER_FG,
        font=("Arial", 13, "bold"),
    ).pack(side="left", padx=(0, 12))
