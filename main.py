from database.db import create_tables
from views.productos_view import ventana_productos
from views.ventas_view import ventana_ventas
from views.reportes_view import ventana_reportes
import tkinter as tk
from tkinter import ttk, messagebox
import logging

if __name__ == "__main__":
    create_tables()
    root = tk.Tk()
    root.title("Gestion Inventario - AvilCar")
    root.geometry("360x260")

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass
    estilo.configure("TButton", padding=(8, 6))

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="AvilCar - Gestión de Inventario", font=("Segoe UI", 12, "bold")).pack(pady=(0, 12))

    ttk.Button(frm, text="Productos", width=24, command=ventana_productos).pack(pady=6)
    ttk.Button(frm, text="Ventas", width=24, command=ventana_ventas).pack(pady=6)
    ttk.Button(frm, text="Reportes", width=24, command=ventana_reportes).pack(pady=6)

    # Menú simple
    menubar = tk.Menu(root)
    filemenu = tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Salir", command=root.quit)
    menubar.add_cascade(label="Archivo", menu=filemenu)

    # Inicializar logging simple (escalable a archivo/rotación si se desea)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    def mostrar_sugerencias():
        # Ventana con texto de recomendaciones profesionales
        win = tk.Toplevel(root)
        win.title("Sugerencias profesionales - Mejora del sistema")
        win.geometry("800x520")
        txt = tk.Text(win, wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", (
            "Recomendaciones prioritarias para llevar el sistema a nivel profesional:\n\n"
            "1) Migraciones y versionado de BD: crear esquema de migrations y aplicar ALTER/Índices controlados.\n"
            "2) Auditoría y roles: registrar usuario/acción; añadir autenticación y permisos.\n"
            "3) Compras/Recepciones/Órdenes de compra: controlar entradas, lotes y costos históricos.\n"
            "4) Reservación de stock y transacciones atómicas para evitar sobreventa.\n"
            "5) Tests automatizados (unit/integración) y CI para asegurar cambios seguros.\n"
            "6) Dashboards KPI y exportes (CSV/PDF) para decisiones comerciales.\n"
            "7) Backups automáticos y políticas de recuperación.\n"
            "8) Mejoras UX: búsqueda inteligente, autocompletado y filtros guardados.\n\n"
            "Pasos recomendados:\n"
            "- Implementar migraciones y testear en copia de BD.\n"
            "- Añadir autenticación básica y registrar usuario en ventas/ajustes.\n"
            "- Implementar ordenes de compra y recepción con matching.\n"
            "- Añadir exportes e indicadores en reportes.\n\n"
            "Si quieres, puedo generar tickets/conjuntos de cambios por prioridad (p.ej. sprint 1,2,3) incluyendo archivos y cambios concretos."
        ))
        txt.config(state="disabled")
        ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=6)

    # Añadir menú 'Ayuda' → 'Sugerencias profesionales'
    ayuda_menu = tk.Menu(menubar, tearoff=0)
    ayuda_menu.add_command(label="Sugerencias profesionales", command=mostrar_sugerencias)
    menubar.add_cascade(label="Ayuda", menu=ayuda_menu)
    root.config(menu=menubar)

    root.mainloop()
