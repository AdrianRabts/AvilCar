import logging
import tkinter as tk
from tkinter import ttk, messagebox

from database.db import create_tables
from views.productos_view import ventana_productos
from views.ventas_view import ventana_ventas
from views.reportes_view import ventana_reportes


APP_NAME = "AvilCar - Gestión de Inventario"
APP_SIZE = "500x400"
PRIMARY_COLOR = "#2563eb"   # Azul elegante
HOVER_COLOR = "#1d4ed8"     # Azul más oscuro en hover
BG_COLOR = "#f3f4f6"        # Gris claro
TEXT_COLOR = "#111827"      # Gris oscuro (texto principal)


# ---------------- Logging ----------------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.info("Aplicación iniciada.")


# ---------------- Estilos ----------------
def init_style(root: tk.Tk):
    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except Exception:
        logging.warning("Tema clam no disponible, usando por defecto.")

    root.configure(bg=BG_COLOR)

    # Botones modernos
    style.configure(
        "Modern.TButton",
        padding=12,
        font=("Segoe UI", 12, "bold"),
        relief="flat",
        background=PRIMARY_COLOR,
        foreground="white",
        borderwidth=0
    )
    style.map(
        "Modern.TButton",
        background=[("active", HOVER_COLOR), ("pressed", "#1e40af")],
        foreground=[("disabled", "#9ca3af")]
    )

    # Labels
    style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), background=BG_COLOR, foreground=TEXT_COLOR)
    style.configure("Footer.TLabel", font=("Segoe UI", 9, "italic"), background=BG_COLOR, foreground="#6b7280")


# ---------------- UI ----------------
def init_ui(root: tk.Tk):
    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="both", expand=True)

    # Título
    ttk.Label(frm, text=APP_NAME, style="Title.TLabel").pack(pady=(10, 30))

    # Botones principales
    ttk.Button(frm, text="📦  Productos", style="Modern.TButton", width=30, command=ventana_productos).pack(pady=10)
    ttk.Button(frm, text="🛒  Ventas", style="Modern.TButton", width=30, command=ventana_ventas).pack(pady=10)
    ttk.Button(frm, text="📊  Reportes", style="Modern.TButton", width=30, command=ventana_reportes).pack(pady=10)
    ttk.Button(frm, text="🚪  Salir", style="Modern.TButton", width=30, command=root.quit).pack(pady=20)

    # Footer
    ttk.Label(frm, text="© 2025 AvilCar Systems", style="Footer.TLabel").pack(pady=(30, 0))


# ---------------- Main ----------------
def main():
    create_tables()
    setup_logging()

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry(APP_SIZE)
    root.minsize(460, 360)

    init_style(root)
    init_ui(root)

    # Manejo global de errores
    def report_callback_exception(_, exc, val, tb):
        logging.exception("Error no controlado", exc_info=(exc, val, tb))
        messagebox.showerror("Error inesperado", f"Ocurrió un error: {val}")

    root.report_callback_exception = report_callback_exception
    root.mainloop()


if __name__ == "__main__":
    main()
