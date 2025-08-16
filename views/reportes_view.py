import tkinter as tk
from tkinter import ttk
from models.reportes import ventas_totales, ventas_por_producto, productos_bajo_stock, movimientos_recientes
from models.ventas import obtener_ventas

def ventana_reportes():
    root = tk.Tk()
    root.title("Inventario - Reportes")
    root.geometry("1000x700")

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass
    estilo.configure("TButton", padding=(6,4))

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=8, pady=8)

    # Tab Resumen
    tab_resumen = ttk.Frame(notebook)
    notebook.add(tab_resumen, text="Resumen")
    total = ventas_totales()
    ttk.Label(tab_resumen, text=f"Ventas Totales: {total}", font=("Segoe UI", 12, "bold")).pack(pady=8)

    cols = ("ID", "Nombre", "Unidades Vendidas", "Total Vendido")
    tv_ventas = ttk.Treeview(tab_resumen, columns=cols, show="headings", height=8)
    for c in cols:
        tv_ventas.heading(c, text=c)
        tv_ventas.column(c, width=200)
    for fila in ventas_por_producto():
        tv_ventas.insert("", tk.END, values=fila)
    tv_ventas.pack(pady=5, fill="x")

    # Tab Historial Ventas
    tab_hist = ttk.Frame(notebook)
    notebook.add(tab_hist, text="Historial Ventas")
    cols_hist = ("ID", "Producto ID", "Nombre", "Cantidad", "Total", "Fecha", "Cliente")
    tv_hist = ttk.Treeview(tab_hist, columns=cols_hist, show="headings", height=12)
    for c in cols_hist:
        tv_hist.heading(c, text=c)
        tv_hist.column(c, width=140)
    for fila in obtener_ventas():
        tv_hist.insert("", tk.END, values=fila)
    tv_hist.pack(pady=5, fill="both", expand=True)

    # Tab Movimientos / Stock
    tab_mov = ttk.Frame(notebook)
    notebook.add(tab_mov, text="Movimientos / Stock")
    # Movimientos
    ttk.Label(tab_mov, text="Movimientos recientes").pack(pady=6)
    cols_m = ("ID", "Producto ID", "Nombre", "Cantidad", "Tipo", "Motivo", "Fecha")
    tv_mov = ttk.Treeview(tab_mov, columns=cols_m, show="headings", height=8)
    for c in cols_m:
        tv_mov.heading(c, text=c)
        tv_mov.column(c, width=120)
    for fila in movimientos_recientes(200):
        tv_mov.insert("", tk.END, values=fila)
    tv_mov.pack(pady=5, fill="x")

    # Stock crítico con texto claro
    frame_stock = ttk.Frame(tab_mov)
    frame_stock.pack(pady=8, fill="x")
    ttk.Label(frame_stock, text="Mostrar productos con stock menor o igual a:").pack(side="left", padx=6)
    entry_umbral = ttk.Entry(frame_stock, width=6)
    entry_umbral.insert(0, "5")
    entry_umbral.pack(side="left", padx=6)
    ttk.Button(frame_stock, text="Mostrar", command=lambda: cargar_bajo_stock()).pack(side="left", padx=6)

    cols2 = ("ID", "Nombre", "Stock")
    tv_stock = ttk.Treeview(tab_mov, columns=cols2, show="headings", height=8)
    for c in cols2:
        tv_stock.heading(c, text=c)
        tv_stock.column(c, width=200)
    tv_stock.pack(pady=5, fill="both", expand=True)

    def cargar_bajo_stock():
        for fila in tv_stock.get_children():
            tv_stock.delete(fila)
        try:
            umbral = int(entry_umbral.get())
        except ValueError:
            umbral = 5
        for p in productos_bajo_stock(umbral):
            tv_stock.insert("", tk.END, values=p)

    cargar_bajo_stock()
    ttk.Button(root, text="Cerrar", command=root.destroy).pack(pady=6)
    root.mainloop()
