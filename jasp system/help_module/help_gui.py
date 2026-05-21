import tkinter as tk
from tkinter import ttk

from main_dashboard.main_functions import BG_CARD, PRIMARY, TEXT_MUTED, TEXT_PRIMARY


def render_help_dashboard(parent):
    # Render the help dashboard with guide and contact support options.
    selected_help_view = tk.StringVar(value="guide")

    intro = tk.Frame(parent, bg=BG_CARD, highlightthickness=1, highlightbackground="black")
    intro.pack(fill="x", pady=(0, 14))
    tk.Label(
        intro,
        text="Help Dashboard",
        bg=PRIMARY,
        fg="white",
        font=("Arial", 18, "bold"),
    ).pack(fill="x", anchor="w", ipady=10)
    tk.Label(
        intro,
        text="Choose System Guide for workflow instructions or Contact Support when you encounter a problem.",
        bg=BG_CARD,
        fg=TEXT_PRIMARY,
        font=("Arial", 13, "bold"),
        anchor="w",
        justify="left",
        wraplength=900,
    ).pack(fill="x", padx=18, pady=14)

    # Build the two help option buttons.
    option_bar = tk.Frame(parent, bg=parent["bg"])
    option_bar.pack(fill="x", pady=(0, 14))
    content_shell = tk.Frame(parent, bg=parent["bg"])
    content_shell.pack(fill="both", expand=True)

    def set_help_view(view_name):
        # Switch between the system guide and contact support views.
        selected_help_view.set(view_name)
        guide_button.config(
            bg=PRIMARY if view_name == "guide" else BG_CARD,
            fg="white" if view_name == "guide" else TEXT_PRIMARY,
            activebackground=PRIMARY if view_name == "guide" else "#e5e7eb",
            activeforeground="white" if view_name == "guide" else TEXT_PRIMARY,
        )
        contact_button.config(
            bg=PRIMARY if view_name == "contact" else BG_CARD,
            fg="white" if view_name == "contact" else TEXT_PRIMARY,
            activebackground=PRIMARY if view_name == "contact" else "#e5e7eb",
            activeforeground="white" if view_name == "contact" else TEXT_PRIMARY,
        )
        for child in content_shell.winfo_children():
            child.destroy()
        if view_name == "guide":
            render_system_guide(content_shell)
        else:
            render_contact_support(content_shell)

    guide_button = tk.Button(
        option_bar,
        text="System Guide",
        command=lambda: set_help_view("guide"),
        font=("Arial", 14, "bold"),
        bd=2,
        relief="solid",
        padx=20,
        pady=10,
        cursor="hand2",
    )
    guide_button.pack(side="left", padx=(0, 10))
    contact_button = tk.Button(
        option_bar,
        text="Contact Support",
        command=lambda: set_help_view("contact"),
        font=("Arial", 14, "bold"),
        bd=2,
        relief="solid",
        padx=20,
        pady=10,
        cursor="hand2",
    )
    contact_button.pack(side="left")

    def render_system_guide(container):
        # Render the scrollable workflow guide inside the help dashboard.
        shell = tk.Frame(container, bg=container["bg"])
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, bg=container["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=container["bg"])
        content_id = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def sync_scroll_region(_event=None):
            # Keep the canvas scroll region matched to its content.
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_content_width(event):
            # Stretch the help content to match the canvas width.
            canvas.itemconfigure(content_id, width=event.width)

        content.bind("<Configure>", sync_scroll_region)
        canvas.bind("<Configure>", sync_content_width)

        def on_mousewheel(event):
            # Scroll the help canvas from mouse wheel events.
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_mousewheel(_event=None):
            # Bind wheel scrolling while the pointer is over the help area.
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_mousewheel)
            canvas.bind_all("<Button-5>", on_mousewheel)

        def unbind_mousewheel(_event=None):
            # Unbind global wheel handlers when leaving the help area.
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)
        content.bind("<Enter>", bind_mousewheel)
        content.bind("<Leave>", unbind_mousewheel)

        # Define help guide sections and workflow steps.
        sections = [
            (
                "Point of Sale (POS)",
                [
                    "Open Point of Sale from the left menu.",
                    "Search or browse the inventory list, then click Add on the item you want to sell.",
                    "Enter the quantity, review the cart, then click Pay / Checkout to finish the sale.",
                    "Use Clear Cart if you need to restart before checkout.",
                ],
            ),
            (
                "Inventory Management",
                [
                    "Open Inventory Management to add, update, delete, or search items.",
                    "Fill in the item details such as name, quantity, cost, price, and unit before saving.",
                    "Select an item from the table to update or delete it.",
                    "Use Summary to review inventory records for a selected day, week, or month.",
                ],
            ),
            (
                "CHB and Delivery Production",
                [
                    "Open CHB and Delivery Production to record CHB block production.",
                    "Enter production details, worker count, materials used, and date, then save the record.",
                    "Use Adjust CHB Stock for manual corrections when stock needs to be fixed.",
                    "Open Delivery Section to record delivered CHB blocks or other delivered items.",
                ],
            ),
            (
                "Reports & Analytics",
                [
                    "Open Reports & Analytics to generate sales, profit, CHB production, and inventory reports.",
                    "Choose the report type and date range, then generate the report.",
                    "Review the totals and breakdowns shown on screen.",
                    "Use PDF options when you need a printable or downloadable copy.",
                ],
            ),
        ]

        for title, steps in sections:
            # Render each help guide section as a bordered card.
            card = tk.Frame(content, bg=BG_CARD, highlightthickness=1, highlightbackground="black")
            card.pack(fill="x", pady=(0, 14))
            tk.Label(
                card,
                text=title,
                bg=PRIMARY,
                fg="white",
                font=("Arial", 15, "bold"),
            ).pack(fill="x", anchor="w", padx=0, pady=0, ipady=10)
            for index, step in enumerate(steps, start=1):
                tk.Label(
                    card,
                    text=f"{index}. {step}",
                    bg=BG_CARD,
                    fg=TEXT_PRIMARY,
                    font=("Arial", 13),
                    anchor="w",
                    justify="left",
                    wraplength=900,
                ).pack(fill="x", padx=16, pady=(8 if index == 1 else 4, 4))
            tk.Frame(card, height=8, bg=BG_CARD).pack(fill="x")

    def render_contact_support(container):
        # Render support contact details and what to send when reporting issues.
        card = tk.Frame(container, bg=BG_CARD, highlightthickness=1, highlightbackground="black")
        card.pack(fill="x")
        tk.Label(
            card,
            text="Contact Support",
            bg=PRIMARY,
            fg="white",
            font=("Arial", 16, "bold"),
        ).pack(fill="x", ipady=10)

        body = tk.Frame(card, bg=BG_CARD, padx=22, pady=18)
        body.pack(fill="x")
        tk.Label(
            body,
            text="If you encounter a system problem, contact the support person below.",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=("Arial", 14, "bold"),
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x", pady=(0, 16))

        contact_rows = [
            ("Support Person", "Keana Rose Andoque"),
            ("Email", "keanarose.andoque@wvsu.edu.ph"),
            ("Phone", "0912 004 5205"),
        ]
        for label, value in contact_rows:
            row = tk.Frame(body, bg=BG_CARD)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=f"{label}:", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 13, "bold"), width=16, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 14, "bold"), anchor="w").pack(side="left", fill="x", expand=True)

        reminder = tk.Frame(body, bg="#eff6ff", highlightthickness=1, highlightbackground="#93c5fd", padx=16, pady=14)
        reminder.pack(fill="x", pady=(18, 0))
        tk.Label(
            reminder,
            text="When reporting an issue, include the module name, what you clicked, the error message, date/time, and a screenshot if available.",
            bg="#eff6ff",
            fg=TEXT_PRIMARY,
            font=("Arial", 13, "bold"),
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x")

    set_help_view("guide")
