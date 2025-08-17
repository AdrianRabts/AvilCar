import logging
import tkinter as tk
from tkinter import ttk, messagebox

from database.db import create_tables
from views.productos_view import ventana_productos
from views.ventas_view import ventana_ventas
from views.reportes_view import ventana_reportes

# ======================== CONSTANTES ========================
APP_NAME = "AvilCar - Gestión de Inventario"
APP_SIZE = "550x450"
PRIMARY_COLOR = "#2563eb"
HOVER_COLOR = "#1e40af"
PRESSED_COLOR = "#1c3aa9"
BG_COLOR = "#f3f4f6"
TEXT_COLOR = "#111827"
FOOTER_COLOR = "#6b7280"
BTN_FONT = ("Segoe UI", 12, "bold")
TITLE_FONT = ("Segoe UI", 18, "bold")
FOOTER_FONT = ("Segoe UI", 9, "italic")
BTN_WIDTH = 30
BTN_HEIGHT = 2

# ======================== LOGGING ========================
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

# ======================== ESTILOS ========================
def init_style(root: tk.Tk):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        logging.warning("Tema clam no disponible, usando por defecto.")
    root.configure(bg=BG_COLOR)

    style.configure(
        "Modern.TButton",
        padding=12,
        font=BTN_FONT,
        relief="flat",
        background=PRIMARY_COLOR,
        foreground="white",
        borderwidth=0
    )
    style.map(
        "Modern.TButton",
        background=[("active", HOVER_COLOR), ("pressed", PRESSED_COLOR)],
        foreground=[("disabled", "#9ca3af")]
    )

    style.configure("Title.TLabel", font=TITLE_FONT, background=BG_COLOR, foreground=TEXT_COLOR)
    style.configure("Footer.TLabel", font=FOOTER_FONT, background=BG_COLOR, foreground=FOOTER_COLOR)

# ======================== TOOLTIP ========================
class ToolTip:
    """ Muestra un pequeño tooltip cuando se pasa el mouse por un widget """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Segoe UI", 9))
        label.pack(ipadx=5, ipady=2)

    def hide(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
        self.tipwindow = None

# ======================== HOVER EFECTO ========================
def add_hover_effect(button: ttk.Button):
    # Cambia color de fondo al pasar el mouse usando style temporal
    original_bg = PRIMARY_COLOR
    hover_bg = HOVER_COLOR
    pressed_bg = PRESSED_COLOR

    def on_enter(e):
        button.configure(style="Hover.TButton")
    def on_leave(e):
        button.configure(style="Modern.TButton")

    style = ttk.Style()
    style.configure("Hover.TButton", background=hover_bg, foreground="white")
    
    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)

# ======================== UI PRINCIPAL ========================
def init_ui(root: tk.Tk):
    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="both", expand=True)

    # Título
    ttk.Label(frm, text=APP_NAME, style="Title.TLabel").pack(pady=(10, 30))

    # Botones principales
    botones = [
        ("📦  Productos", ventana_productos, "Abrir ventana de productos"),
        ("🛒  Ventas", ventana_ventas, "Registrar y ver ventas"),
        ("📊  Reportes", ventana_reportes, "Ver reportes y estadísticas"),
        ("🚪  Salir", lambda: confirmar_salida(root), "Cerrar aplicación")
    ]

    for text, cmd, tip in botones:
        btn = ttk.Button(frm, text=text, style="Modern.TButton", width=BTN_WIDTH, command=cmd)
        btn.pack(pady=10)
        add_hover_effect(btn)
        ToolTip(btn, tip)

    # Separador
    ttk.Separator(frm, orient='horizontal').pack(fill='x', pady=(20, 10))
    # Footer
    ttk.Label(frm, text="© 2025 AvilCar Systems", style="Footer.TLabel").pack()

# ======================== CONFIRMAR SALIDA ========================
def confirmar_salida(root: tk.Tk):
    if messagebox.askyesno("Salir", "¿Estás seguro que deseas salir de la aplicación?"):
        logging.info("Aplicación cerrada por usuario.")
        root.destroy()

# ======================== MAIN ========================
def main():
    create_tables()
    setup_logging()

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry(APP_SIZE)
    root.minsize(500, 400)

    init_style(root)
    init_ui(root)

    # Manejo global de errores
    def report_callback_exception(_, exc, val, tb):
        logging.exception("Error no controlado", exc_info=(exc, val, tb))
        messagebox.showerror("Error inesperado", f"Ocurrió un error:\n{val}")

    root.report_callback_exception = report_callback_exception
    root.mainloop()

if __name__ == "__main__":
    main()
