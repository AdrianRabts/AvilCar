import tkinter as tk
from tkinter import ttk, messagebox
from models.producto import obtener_productos, obtener_producto_por_sku, obtener_producto_por_codigo
from models.ventas import registrar_venta

def _format_display(p):
    id_ = p[0]
    nombre = p[1]
    stock = p[3]
    codigo = p[4] if len(p) > 4 else None
    return f"{codigo or id_} - {nombre} (stock: {stock})"

def _load_opciones(productos):
    return [_format_display(p) for p in productos]

def refrescar_productos(combo_producto):
    productos = obtener_productos()
    opciones = _load_opciones(productos)
    combo_producto['values'] = opciones
    if opciones:
        combo_producto.current(0)

def obtener_producto_id_desde_seleccion(sel):
    codigo_or_id = sel.split(" - ")[0]
    producto = obtener_producto_por_codigo(codigo_or_id)
    if producto is not None:
        return producto[0]
    try:
        return int(codigo_or_id)
    except ValueError:
        raise ValueError("Producto no encontrado por código ni por ID")

def registrar_y_mostrar(producto_id, cantidad, cliente, entry_cantidad, entry_cliente, combo_producto):
    resultado = registrar_venta(producto_id, cantidad, cliente=cliente)
    messagebox.showinfo("Venta", f"Venta registrada.\nTotal: {resultado['total']}\nNuevo stock: {resultado['nuevo_stock']}")
    entry_cantidad.delete(0, tk.END)
    entry_cliente.delete(0, tk.END)
    refrescar_productos(combo_producto)

def ventana_ventas():
    root = tk.Tk()
    root.title("Inventario - Ventas")
    root.geometry("560x320")

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass
    estilo.configure("TButton", padding=(6,4))

    # Frames
    form = ttk.Frame(root, padding=12)
    form.pack(side="top", fill="x")
    controls = ttk.Frame(root, padding=12)
    controls.pack(side="top", fill="x")
    tabla_frame = ttk.Frame(root, padding=12)
    tabla_frame.pack(side="top", fill="both", expand=True)

    # Producto combobox y cantidad/cliente
    tk.Label(form, text="Producto (Código - Nombre - stock)").grid(row=0, column=0, sticky="w")
    productos = obtener_productos()
    opciones = _load_opciones(productos)
    combo_producto = ttk.Combobox(form, values=opciones, state="readonly", width=50)
    combo_producto.grid(row=0, column=1, padx=6, pady=4)
    if opciones:
        combo_producto.current(0)

    tk.Label(form, text="Cantidad").grid(row=1, column=0, sticky="w")
    entry_cantidad = ttk.Entry(form, width=10)
    entry_cantidad.grid(row=1, column=1, sticky="w", padx=6, pady=4)
    tk.Label(form, text="Cliente (opcional)").grid(row=2, column=0, sticky="w")
    entry_cliente = ttk.Entry(form, width=30)
    entry_cliente.grid(row=2, column=1, sticky="w", padx=6, pady=4)

    # acciones
    def realizar_venta():
        sel = combo_producto.get()
        if not sel:
            messagebox.showwarning("Seleccionar", "Seleccione un producto")
            return
        try:
            producto_id = obtener_producto_id_desde_seleccion(sel)
            cantidad = int(entry_cantidad.get())
            cliente = entry_cliente.get().strip() or None
            if not messagebox.askyesno("Confirmar venta", f"Vender {cantidad} unidades del producto ID {producto_id}?"):
                return
            registrar_y_mostrar(producto_id, cantidad, cliente, entry_cantidad, entry_cliente, combo_producto)
        except ValueError as ve:
            messagebox.showerror("Error", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {e}")

    # Botones centralizados
    btn_frame = ttk.Frame(controls)
    btn_frame.pack()
    ttk.Button(btn_frame, text="Vender", command=realizar_venta).grid(row=0, column=0, padx=8, pady=6)
    ttk.Button(btn_frame, text="Refrescar", command=lambda: refrescar_productos(combo_producto)).grid(row=0, column=1, padx=8, pady=6)
    ttk.Button(btn_frame, text="Cerrar", command=root.destroy).grid(row=0, column=2, padx=8, pady=6)

    root.mainloop()
