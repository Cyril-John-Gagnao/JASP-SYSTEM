import tkinter as tk
from inventory import open_inventory
from pos import open_pos  # Assuming you have this

def open_main():
    root = tk.Tk()
    root.title("JASP Dashboard")
    root.state("zoomed")
    root.configure(bg="#f4f6f9")

    # ================= SIDEBAR =================
    sidebar = tk.Frame(root, bg="#1e293b", width=220)
    sidebar.pack(side="left", fill="y")

    # Logo / Title
    tk.Label(sidebar, text="JASP System",
             bg="#1e293b", fg="white",
             font=("Arial", 16, "bold")).pack(pady=20)

    # -------- BUTTON STYLE --------
    def sidebar_btn(text, command=None):
        return tk.Button(
            sidebar,
            text=text,
            command=command,
            font=("Arial", 11),
            bg="#1e293b",
            fg="white",
            activebackground="#334155",
            activeforeground="white",
            bd=0,
            relief="flat",
            anchor="w",
            padx=20,
            pady=10
        )

    # Sidebar Buttons
    sidebar_btn("🛒 POS", open_pos).pack(fill="x")
    sidebar_btn("📦 Inventory", open_inventory).pack(fill="x")
    sidebar_btn("📊 Sales", lambda: print("Sales clicked")).pack(fill="x")
    sidebar_btn("📄 Reports", lambda: print("Reports clicked")).pack(fill="x")

    # Spacer
    tk.Label(sidebar, bg="#1e293b").pack(expand=True, fill="both")

    # Logout Button
    tk.Button(sidebar, text="Logout",
              bg="#dc3545", fg="white",
              font=("Arial", 10, "bold"),
              relief="flat",
              command=root.destroy).pack(fill="x", pady=10, padx=10)

    # ================= MAIN CONTENT =================
    main_area = tk.Frame(root, bg="#f4f6f9")
    main_area.pack(side="right", fill="both", expand=True)

    # Header
    header = tk.Frame(main_area, bg="white", height=60)
    header.pack(fill="x")

    tk.Label(header, text="Dashboard",
             bg="white", fg="#333",
             font=("Arial", 16, "bold")).pack(side="left", padx=20, pady=10)

    # Content Area
    content = tk.Frame(main_area, bg="#f4f6f9")
    content.pack(fill="both", expand=True, padx=20, pady=20)

    # Welcome Card
    card = tk.Frame(content, bg="white", padx=20, pady=20)
    card.pack(fill="x")

    tk.Label(card, text="Welcome to JASP Hardware System",
             font=("Arial", 14, "bold"), bg="white").pack(anchor="w")

    tk.Label(card, text="Use the sidebar to navigate (POS, Inventory, Sales, Reports)",
             font=("Arial", 10), bg="white", fg="gray").pack(anchor="w", pady=5)

    root.mainloop()

if __name__ == "__main__":
    open_main()