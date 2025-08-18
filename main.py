# C:\Users\User\Desktop\InventarioAvilCar\AvilCar\main.py

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from database.db import create_tables, migrate_schema
from views.productos_view import ventana_productos
from views.ventas_view import ventana_ventas
from views.reportes_view import ventana_reportes

# ======================== CONSTANTES ========================
APP_NAME = "AvilCar - Gestión de Inventario"
APP_SIZE = "1280x800"
START_MAXIMIZED = True

PRIMARY_COLOR = "#eb257b"
HOVER_COLOR = "#1e40af"
PRESSED_COLOR = "#1c3aa9"
BG_COLOR = "#f3f4f6"
TEXT_COLOR = "#111827"
FOOTER_COLOR = "#6b7280"
BTN_FONT = ("Segoe UI", 13, "bold")
TITLE_FONT = ("Segoe UI", 26, "bold")
FOOTER_FONT = ("Segoe UI", 9, "italic")

# ======================== RUTAS ========================
def resource_path(relative_path):
    """
    Retorna la ruta absoluta del recurso.
    Compatible con PyInstaller (.exe) o desarrollo normal.
    """
    try:
        # PyInstaller crea un folder temporal _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Rutas globales de recursos
DB_PATH = resource_path("database/inventario.db")
ASSETS_PATH = resource_path("assets")

# ======================== LOGGING ========================
def setup_logging():
    os.makedirs(resource_path("logs"), exist_ok=True)
    handlers = [
        RotatingFileHandler(resource_path("logs/app.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )
    logging.info("Aplicación iniciada.")

# ======================== DPI (PRE-ROOT) ========================
def enable_high_dpi_pre_root():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

# ======================== ESTILOS ========================
def _auto_scaling(root: tk.Tk):
    try:
        h = root.winfo_screenheight()
        if h >= 1440:
            root.tk.call("tk", "scaling", 1.6)
        elif h >= 1080:
            root.tk.call("tk", "scaling", 1.3)
        else:
            root.tk.call("tk", "scaling", 1.1)
    except Exception:
        pass

def init_style(root: tk.Tk):
    _auto_scaling(root)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        logging.warning("Tema clam no disponible, usando por defecto.")
    root.configure(bg=BG_COLOR)

    style.configure(
        "Modern.TButton",
        padding=16,
        font=BTN_FONT,
        relief="flat",
        background=PRIMARY_COLOR,
        foreground="white",
        borderwidth=0
    )
    style.map(
        "Modern.TButton",
        background=[("active", HOVER_COLOR), ("pressed", PRESSED_COLOR), ("focus", PRIMARY_COLOR)],
        foreground=[("disabled", "#9ca3af")],
        relief=[("pressed", "flat"), ("!pressed", "flat")]
    )
    style.configure("Hover.TButton", background=HOVER_COLOR, foreground="white")
    style.configure("Title.TLabel", font=TITLE_FONT, background=BG_COLOR, foreground=TEXT_COLOR)
    style.configure("Footer.TLabel", font=FOOTER_FONT, background=BG_COLOR, foreground=FOOTER_COLOR)

    root.option_add("*TButton.focusHighlight", "0")
    root.option_add("*Font", ("Segoe UI", 10))
    root.option_add("*Label.Font", ("Segoe UI", 10))

# ======================== TOOLTIP ========================
class ToolTip:
    def __init__(self, widget, text, delay_ms=350):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self._job = None
        self.delay_ms = delay_ms
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self.hide)
        widget.bind("<Destroy>", self.hide)

    def _schedule(self, _=None):
        self._cancel()
        self._job = self.widget.after(self.delay_ms, self.show)

    def _cancel(self):
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
        self._job = None

    def show(self):
        if self.tipwindow or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 12
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            scr_w = self.widget.winfo_screenwidth()
            scr_h = self.widget.winfo_screenheight()
        except Exception:
            return
        tw = tk.Toplevel(self.widget)
        self.tipwindow = tw
        tw.wm_overrideredirect(True)
        label = tk.Label(
            tw, text=self.text, justify="left",
            background="#ffffe0", relief="solid", borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=6, ipady=3)
        tw.update_idletasks()
        w, h = tw.winfo_reqwidth(), tw.winfo_reqheight()
        x = min(max(0, x), scr_w - w - 4)
        y = min(max(0, y), scr_h - h - 4)
        tw.wm_geometry(f"+{x}+{y}")

    def hide(self, _=None):
        self._cancel()
        if self.tipwindow:
            try:
                self.tipwindow.destroy()
            except Exception:
                pass
        self.tipwindow = None

# ======================== EFECTOS ========================
def add_hover_effect(button: ttk.Button):
    def on_enter(_): button.configure(style="Hover.TButton")
    def on_leave(_): button.configure(style="Modern.TButton")
    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)

# ======================== ACCIONES ========================
def safe_open(func, root, nombre):
    try:
        func(root)
    except Exception as e:
        logging.exception(f"Error abriendo {nombre}")
        messagebox.showerror("Error", f"No se pudo abrir {nombre}:\n{e}")

def abrir_productos(root): safe_open(ventana_productos, root, "Productos")
def abrir_ventas(root): safe_open(ventana_ventas, root, "Ventas")
def abrir_reportes(root): safe_open(ventana_reportes, root, "Reportes")

def confirmar_salida(root: tk.Tk):
    if messagebox.askyesno("Salir", "¿Estás seguro que deseas salir de la aplicación?"):
        logging.info("Aplicación cerrada por usuario.")
        root.destroy()

# ======================== MENÚ ========================
def build_menubar(root: tk.Tk):
    menubar = tk.Menu(root)
    m_archivo = tk.Menu(menubar, tearoff=0)
    m_archivo.add_command(label="Productos\tCtrl+1", command=lambda: abrir_productos(root))
    m_archivo.add_command(label="Ventas\tCtrl+2", command=lambda: abrir_ventas(root))
    m_archivo.add_command(label="Reportes\tCtrl+3", command=lambda: abrir_reportes(root))
    m_archivo.add_separator()
    m_archivo.add_command(label="Salir\tCtrl+Q", command=lambda: confirmar_salida(root))
    menubar.add_cascade(label="Archivo", menu=m_archivo)

    m_ver = tk.Menu(menubar, tearoff=0)
    m_ver.add_command(label="Maximizar", command=lambda: root.state("zoomed"))
    m_ver.add_command(label="Restaurar", command=lambda: root.state("normal"))
    m_ver.add_separator()
    m_ver.add_command(label="Pantalla completa\tF11", command=lambda: toggle_fullscreen(root))
    m_ver.add_command(label="Salir de pantalla completa\tEsc", command=lambda: end_fullscreen(root))
    menubar.add_cascade(label="Ver", menu=m_ver)

    m_ayuda = tk.Menu(menubar, tearoff=0)
    m_ayuda.add_command(label="Acerca de", command=lambda: messagebox.showinfo(
        "Acerca de", "AvilCar - Gestión de Inventario\n© 2025 AvilCar Systems"))
    menubar.add_cascade(label="Ayuda", menu=m_ayuda)
    root.config(menu=menubar)

# ======================== PANTALLA COMPLETA ========================
def toggle_fullscreen(root: tk.Tk, event=None):
    root.is_fullscreen = not getattr(root, "is_fullscreen", False)
    root.attributes("-fullscreen", root.is_fullscreen)

def end_fullscreen(root: tk.Tk, event=None):
    root.is_fullscreen = False
    root.attributes("-fullscreen", False)

# ======================== UI PRINCIPAL ========================
def init_ui(root: tk.Tk):
    container = ttk.Frame(root, padding=40)
    container.pack(fill="both", expand=True)
    container.grid_propagate(False)
    container.update_idletasks()

    title = ttk.Label(container, text=APP_NAME, style="Title.TLabel", anchor="center")
    title.pack(pady=(0, 30))

    botones_frame = ttk.Frame(container)
    botones_frame.pack(fill="both", expand=True)
    botones_frame.columnconfigure(0, weight=1)
    botones_frame.columnconfigure(1, weight=1)

    botones_def = [
        ("📦  Productos", lambda: abrir_productos(root), "Abrir ventana de productos"),
        ("🛒  Ventas",    lambda: abrir_ventas(root),    "Registrar y ver ventas"),
        ("📊  Reportes",  lambda: abrir_reportes(root),  "Ver reportes y estadísticas"),
        ("🚪  Salir",     lambda: confirmar_salida(root),"Cerrar aplicación"),
    ]
    botones_widgets = []
    for text, cmd, tip in botones_def:
        btn = ttk.Button(botones_frame, text=text, style="Modern.TButton", command=cmd)
        add_hover_effect(btn)
        ToolTip(btn, tip, delay_ms=350)
        botones_widgets.append(btn)

    def do_layout(cols: int):
        for child in botones_widgets:
            child.grid_forget()
        rows = (len(botones_widgets) + cols - 1) // cols
        for r in range(rows):
            botones_frame.rowconfigure(r, weight=1, minsize=80)
        for idx, btn in enumerate(botones_widgets):
            col = idx % cols
            row = idx // cols
            btn.grid(row=row, column=col, padx=18, pady=18, sticky="nsew")
        for c in range(cols):
            botones_frame.columnconfigure(c, weight=1)

    botones_frame.current_cols = 2
    do_layout(botones_frame.current_cols)

    def on_resize(event=None):
        try:
            width = botones_frame.winfo_width()
            desired_cols = 1 if width < 900 else 2
            if desired_cols != botones_frame.current_cols:
                botones_frame.current_cols = desired_cols
                do_layout(desired_cols)
        except Exception:
            pass

    botones_frame.bind("<Configure>", on_resize)

    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(30, 10))
    status = ttk.Frame(container)
    status.pack(fill="x")
    lbl_left = ttk.Label(
        status,
        text="Listo • F11: Pantalla completa • Esc: Salir de pantalla completa",
        style="Footer.TLabel"
    )
    lbl_left.pack(side="left")
    lbl_right = ttk.Label(status, text="© 2025 AvilCar Systems", style="Footer.TLabel")
    lbl_right.pack(side="right")

# ======================== MAIN ========================
def main():
    setup_logging()
    try:
        create_tables()
        migrate_schema()
        logging.info("Esquema de base de datos creado/migrado correctamente.")
    except Exception as e:
        logging.exception("Error al crear/migrar esquema")
        messagebox.showerror("Base de datos", f"No se pudo inicializar la base de datos:\n{e}")
        return

    enable_high_dpi_pre_root()
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry(APP_SIZE)
    root.minsize(1024, 700)
    root.resizable(True, True)
    root.protocol("WM_DELETE_WINDOW", lambda: confirmar_salida(root))
    root.is_fullscreen = False

    init_style(root)
    build_menubar(root)
    init_ui(root)

    # Atajos
    root.bind("<Control-Key-1>", lambda e: abrir_productos(root))
    root.bind("<Control-Key-2>", lambda e: abrir_ventas(root))
    root.bind("<Control-Key-3>", lambda e: abrir_reportes(root))
    root.bind("<Control-q>", lambda e: confirmar_salida(root))
    root.bind("<F11>", lambda e: toggle_fullscreen(root))
    root.bind("<Escape>", lambda e: end_fullscreen(root))

    # Maximizado inicial
    try:
        if START_MAXIMIZED and sys.platform.startswith(("win", "linux")):
            root.state("zoomed")
    except Exception:
        pass

    # Captura global de errores
    def report_callback_exception(exc, val, tb):
        logging.exception("Error no controlado", exc_info=(exc, val, tb))
        try:
            messagebox.showerror("Error inesperado", f"Ocurrió un error:\n{val}")
        except Exception:
            pass
    root.report_callback_exception = report_callback_exception

    root.mainloop()

if __name__ == "__main__":
    main()
