# productos_view.py
from __future__ import annotations

import csv
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Any, Optional, Iterable, Sequence
import tkinter.font as tkfont

# ============================
# === MODELOS (tu backend) ===
# ============================
from models.producto import (
    agregar_producto,
    obtener_productos,
    eliminar_producto,
    editar_producto,
    buscar_productos,          # si tu modelo no lo tiene, el código hace fallback
    aumentar_stock,
    reducir_stock,
    obtener_producto_por_id,
)
from models.categoria import (
    obtener_categorias,
    agregar_categoria,
    eliminar_categoria
)


# ============================
# === CONSTANTES Y ESTILOS ===
# ============================
STYLE_PRIMARY: str = "Primary.TButton"
STYLE_DANGER: str = "Danger.TButton"
STYLE_DEFAULT: str = "Default.TButton"

# Secciones disponibles (puedes editar esta lista a tu gusto)
SECCIONES: list[str] = ["Ninguno", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

# Columnas de la tabla (SIN mínimo stock)
COLUMNS: tuple[str, ...] = (
    "ID", "Codigo", "Nombre",
    "Precio Venta", "Precio Costo",
    "Stock",
    "Seccion", "Categoria"
)

PLACEHOLDER_BUSCAR: str = "Buscar por código o nombre…"

# ============================
# === UTILIDADES GENERALES ===
# ============================
def _safe_str(x: Any) -> str:
    try:
        return "" if x is None else str(x)
    except Exception:
        return ""

def _get_key(d: Any, *keys_or_indexes: Any, default: Any = None) -> Any:
    """
    Obtiene un valor robustamente de dict/sqlite3.Row/tupla/lista.
    keys_or_indexes: lista de claves o índices alternativos.
    Devuelve el primero que exista, o default.
    """
    for k in keys_or_indexes:
        try:
            if isinstance(d, dict):
                if k in d:
                    return d[k]
            elif hasattr(d, "keys") and k in d.keys():  # sqlite3.Row
                return d[k]
            elif isinstance(d, (list, tuple)) and isinstance(k, int):
                return d[k]
        except Exception:
            pass
    return default

def _fmt_precio(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return _safe_str(v)

# ============================
# === ENTRY CON PLACEHOLDER ==
# ============================
class PlaceholderEntry(tk.Entry):
    def __init__(self, master: tk.Widget, placeholder: str, *args, **kwargs) -> None:
        super().__init__(master, *args, **kwargs)
        self._placeholder = placeholder
        self._default_fg = self.cget("fg") or "black"
        self._has_placeholder = False
        self._put_placeholder()
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _put_placeholder(self) -> None:
        self.delete(0, tk.END)
        self.insert(0, self._placeholder)
        try:
            self.config(fg="grey")
        except Exception:
            pass
        self._has_placeholder = True

    def _on_focus_in(self, _: Any) -> None:
        if self._has_placeholder:
            self.delete(0, tk.END)
            try:
                self.config(fg=self._default_fg)
            except Exception:
                pass
            self._has_placeholder = False

    def _on_focus_out(self, _: Any) -> None:
        if not self.get().strip():
            self._put_placeholder()

    def value(self) -> str:
        v = self.get()
        return "" if self._has_placeholder or v == self._placeholder else v.strip()

# ============================
# === PARSEO DE PRODUCTOS  ===
# ============================
def _parse_producto(prod: Any) -> dict[str, Any]:
    """
    Adapta filas de tu backend (sqlite3.Row/dict/tupla) a un dict estándar.
    """
    return {
        "id": _get_key(prod, "id", 0),
        "codigo": _get_key(prod, "sku", "codigo", 1, 4, default=""),
        "nombre": _get_key(prod, "nombre", 2, default=""),

        "precio_venta": _get_key(prod, "precio_venta", 3, default=0),
        "precio_costo": _get_key(prod, "precio_costo", 4, default=0),

        "stock": _get_key(prod, "stock", 5, default=0),

        "seccion": _get_key(prod, "seccion", 6, default="Ninguno"),

        "categoria_id": _get_key(prod, "categoria_id", 7),
        "categoria_nombre": _get_key(prod, "categoria_nombre", "categoria", 8),

    }

def _row_values_from_parsed(p: dict[str, Any]) -> tuple[Any, ...]:
    categoria = (
        f"{p['categoria_id']} - {p['categoria_nombre']}"
        if p.get("categoria_id") is not None and p.get("categoria_nombre")
        else _safe_str(p.get("categoria_nombre") or "")
    )

    return (
        p["id"],
        p["codigo"],
        p["nombre"],
        _fmt_precio(p["precio_venta"]),
        _fmt_precio(p["precio_costo"]),
        p["stock"],
        _safe_str(p.get("seccion") or "Ninguno"),
        categoria,
    )

# ============================
# === TABLA (Treeview)     ===
# ============================
def _value_for_sort(val: Any, col: str) -> Any:
    try:
        if col in ("Precio Venta", "Precio Costo"):
            s = _safe_str(val).replace("$", "").replace(",", "").strip()
            return float(s) if s else 0.0
        if col in ("ID", "Stock"):
            return int(val or 0)
    except Exception:
        pass
    return _safe_str(val).lower()

def sort_treeview(tabla: ttk.Treeview, col: str, reverse: bool) -> None:
    data: list[tuple[Any, str]] = []
    for item in tabla.get_children(""):
        val = tabla.set(item, col)
        data.append((_value_for_sort(val, col), item))
    data.sort(reverse=reverse, key=lambda t: t[0])
    for index, (_, item) in enumerate(data):
        tabla.move(item, "", index)
        try:
            tabla.item(item, tags=("even" if index % 2 == 0 else "odd",))
        except Exception:
            pass
    tabla.heading(col, command=lambda: sort_treeview(tabla, col, not reverse))

def _crear_tabla(parent: tk.Widget) -> ttk.Treeview:
    tabla = ttk.Treeview(parent, columns=COLUMNS, show="headings", selectmode="browse")
    for col in COLUMNS:
        if col in ("Precio Venta", "Precio Costo"):
            anchor, width = "e", 130
        elif col in ("ID", "Stock"):
            anchor, width = "center", 90
        elif col == "Nombre":
            anchor, width = "w", 320
        else:
            anchor, width = "center", 170

        tabla.heading(col, text=col, anchor=anchor, command=lambda c=col: sort_treeview(tabla, c, False))
        tabla.column(col, width=width, anchor=anchor, stretch=(col in ("Nombre", "Seccion", "Categoria")))
    try:
        tabla.tag_configure("odd", background="#ffffff")
        tabla.tag_configure("even", background="#f6f6f6")
    except Exception:
        pass
    return tabla

def _set_rows(tabla: ttk.Treeview, productos: Sequence[Iterable[Any]]) -> None:
    for i in tabla.get_children():
        tabla.delete(i)
    for idx, prod in enumerate(productos):
        p = _parse_producto(prod)
        tag = "even" if (idx % 2 == 0) else "odd"
        tabla.insert("", tk.END, values=_row_values_from_parsed(p), tags=(tag,))

def cargar_datos(tabla: ttk.Treeview) -> None:
    try:
        productos = obtener_productos()
    except Exception as e:
        messagebox.showerror("Error", f"No se pudieron cargar productos: {e}")
        productos = []
    _set_rows(tabla, productos)

# ============================
# === BÚSQUEDA / FILTROS    ==
# ============================
def _producto_match_term(prod: Iterable[Any], term_low: str) -> bool:
    p = _parse_producto(prod)
    return (
        term_low in (p["nombre"] or "").lower()
        or term_low in _safe_str(p["codigo"]).lower()
        or term_low in _safe_str(p["id"])
    )

def filtrar_en_tabla_por_termino(term: str, tabla: ttk.Treeview) -> None:
    term = (term or "").strip()
    if term == "":
        cargar_datos(tabla)
        return
    term_low = term.lower()
    try:
        base = buscar_productos(term)  # si existe en el modelo
        if not base:
            raise Exception("fallback")
        filtrados = base
    except Exception:
        try:
            allp = obtener_productos()
        except Exception:
            allp = []
        filtrados = [prod for prod in allp if _producto_match_term(prod, term_low)]
    _set_rows(tabla, filtrados)

def cargar_categorias_combobox(combo: ttk.Combobox, include_all: bool = True) -> None:
    opciones: list[str] = (["Todas"] if include_all else [])
    try:
        for c in obtener_categorias():
            cid = _get_key(c, 0, "id")
            cnombre = _get_key(c, 1, "nombre")
            opciones.append(f"{cid} - {cnombre}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudieron cargar categorías: {e}")
    combo["values"] = opciones
    if opciones:
        try:
            combo.current(0)
        except Exception:
            pass



def parse_id_from_combo_value(val: str) -> Optional[int]:
    if not val or val in ("Todas",):
        return None
    try:
        return int(val.split(" - ")[0])
    except Exception:
        return None

def filtrar_por_categoria(combo_categoria: ttk.Combobox, tabla: ttk.Treeview) -> None:
    cat_id = parse_id_from_combo_value(combo_categoria.get())
    if cat_id is None:
        cargar_datos(tabla)
        return
    filtrados: list[Iterable[Any]] = []
    try:
        for prod in obtener_productos():
            p = _parse_producto(prod)
            if p["categoria_id"] == cat_id:
                filtrados.append(prod)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo filtrar: {e}")
    _set_rows(tabla, filtrados)

# ============================
# === CSV EXPORT            ==
# ============================
def export_tabla_csv(tabla: ttk.Treeview, parent: tk.Misc) -> None:
    if not tabla.get_children():
        messagebox.showwarning("Exportar", "No hay datos para exportar.")
        return
    fpath = filedialog.asksaveasfilename(
        parent=parent,
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    if not fpath:
        return
    cols = tabla["columns"]
    try:
        with open(fpath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for item in tabla.get_children():
                values = tabla.item(item, "values")
                writer.writerow([_safe_str(v) for v in values])
        messagebox.showinfo("Exportar", f"Tabla exportada a:\n{fpath}")
    except Exception as e:
        messagebox.showerror("Exportar", f"No se pudo exportar: {e}")

# ============================
# === HANDLERS CRUD         ==
# ============================
def _get_selected_row_id(tabla: ttk.Treeview) -> Optional[int]:
    seleccionado = tabla.selection()
    if not seleccionado:
        return None
    item_id = seleccionado[0]
    item = tabla.item(item_id)
    try:
        return int(item["values"][0])
    except Exception:
        return None

def borrar_handler(tabla: ttk.Treeview) -> None:
    id_producto = _get_selected_row_id(tabla)
    if id_producto is None:
        messagebox.showwarning("Seleccionar", "Seleccione un producto")
        return
    if not messagebox.askyesno("Confirmar", "¿Seguro que desea eliminar el producto seleccionado?"):
        return
    try:
        eliminar_producto(id_producto)
        cargar_datos(tabla)
        messagebox.showinfo("OK", "Producto eliminado.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def _agregar_producto_flexible(**kwargs: Any) -> None:
    """
    Llama agregar_producto con distintas firmas posibles de tu backend.
    kwargs esperados: nombre, precio_venta, stock, sku, precio_costo, seccion, categoria_id
    """
    nombre = kwargs.get("nombre")
    precio_venta = kwargs.get("precio_venta")
    stock = kwargs.get("stock")
    sku = kwargs.get("sku")
    precio_costo = kwargs.get("precio_costo", 0)
    seccion = kwargs.get("seccion")
    categoria_id = kwargs.get("categoria_id")


    # 1) firma completa posicional
    try:
        return agregar_producto(nombre, precio_venta, stock, sku, precio_costo, seccion, categoria_id)  # type: ignore[misc]
    except TypeError:
        pass
    # 2) con keywords
    try:
        return agregar_producto(
            nombre=nombre, precio_venta=precio_venta, stock=stock,
            sku=sku, precio_costo=precio_costo, seccion=seccion,
            categoria_id=categoria_id
        )  # type: ignore[misc]
    except TypeError:
        pass
    # 3) versión reducida (como en algunos ejemplos)
    try:
        return agregar_producto(nombre, precio_venta, stock, sku=sku, categoria_id=categoria_id)  # type: ignore[misc]
    except TypeError:
        pass
    # 4) mínima
    return agregar_producto(nombre, precio_venta, stock)  # type: ignore[misc]

def _editar_producto_flexible(producto_id: int, **kwargs: Any) -> None:
    """
    Similar a _agregar_producto_flexible pero para editar_producto.
    """
    nombre = kwargs.get("nombre")
    precio_venta = kwargs.get("precio_venta")
    stock = kwargs.get("stock")
    sku = kwargs.get("sku")
    precio_costo = kwargs.get("precio_costo", 0)
    seccion = kwargs.get("seccion")
    categoria_id = kwargs.get("categoria_id")


    # 1) firma completa posicional
    try:
        return editar_producto(producto_id, nombre, precio_venta, stock, sku, precio_costo, seccion, categoria_id)  # type: ignore[misc]
    except TypeError:
        pass
    # 2) con keywords
    try:
        return editar_producto(
            producto_id,
            nombre=nombre, precio_venta=precio_venta, stock=stock,
            sku=sku, precio_costo=precio_costo, seccion=seccion
        )  # type: ignore[misc]
    except TypeError:
        pass
    # 3) reducida
    try:
        return editar_producto(producto_id, nombre, precio_venta, stock, sku=sku, categoria_id=categoria_id)  # type: ignore[misc]
    except TypeError:
        pass
    # 4) mínima
    return editar_producto(producto_id, nombre, precio_venta, stock)  # type: ignore[misc]

def _ajuste_stock_flexible(producto_id: int, cantidad: int, motivo: str, tipo: str) -> None:
    if tipo == "entrada":
        # con motivo
        try:
            return aumentar_stock(producto_id, cantidad, motivo=motivo)  # type: ignore[misc]
        except TypeError:
            return aumentar_stock(producto_id, cantidad)  # type: ignore[misc]
    else:
        try:
            return reducir_stock(producto_id, cantidad, motivo=motivo)  # type: ignore[misc]
        except TypeError:
            return reducir_stock(producto_id, cantidad)  # type: ignore[misc]

def ajustar_stock_handler(root: tk.Misc, tabla: ttk.Treeview, tipo: str) -> None:
    id_producto = _get_selected_row_id(tabla)
    if id_producto is None:
        messagebox.showwarning("Seleccionar", "Seleccione un producto")
        return

    top = tk.Toplevel(root)
    top.title("Ajuste de stock")
    top.transient(root)
    top.grab_set()
    top.resizable(True, True)

    tk.Label(top, text="Cantidad").grid(row=0, column=0, padx=8, pady=8, sticky="e")
    entry_cant = tk.Entry(top, width=22)
    entry_cant.grid(row=0, column=1, padx=8, pady=8, sticky="w")

    tk.Label(top, text="Motivo").grid(row=1, column=0, padx=8, pady=8, sticky="e")
    entry_motivo = tk.Entry(top, width=32)
    entry_motivo.grid(row=1, column=1, padx=8, pady=8, sticky="w")

    def aplicar() -> None:
        try:
            cantidad = int(entry_cant.get())
            if cantidad <= 0:
                messagebox.showerror("Validación", "La cantidad debe ser mayor que 0.")
                return
            motivo = entry_motivo.get().strip()

            prod = obtener_producto_por_id(id_producto)
            p = _parse_producto(prod) if prod is not None else {"stock": 0}
            if tipo != "entrada" and int(p.get("stock", 0)) - cantidad < 0:
                messagebox.showerror("Stock", "La salida dejaría el stock negativo.")
                return

            if not messagebox.askyesno("Confirmar", f"¿Confirmar ajuste de stock ({tipo}) por {cantidad}?"):
                return

            _ajuste_stock_flexible(id_producto, cantidad, motivo, tipo)
            top.destroy()
            cargar_datos(tabla)
        except ValueError:
            messagebox.showerror("Error", "Cantidad inválida")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    btns = ttk.Frame(top)
    btns.grid(row=2, column=0, columnspan=2, pady=12)
    ttk.Button(btns, text="Aplicar", command=aplicar).grid(row=0, column=0, padx=8)
    ttk.Button(btns, text="Cancelar", command=top.destroy).grid(row=0, column=1, padx=8)

# ============================
# === MODAL NUEVO / EDITAR  ==
# ============================
def _validar_modal(
    codigo: str, nombre: str, precio_venta_str: str, stock_str: str, seccion_val: str,
    lbl_err_codigo: tk.Label, lbl_err_nombre: tk.Label, lbl_err_precio: tk.Label,
    lbl_err_stock: tk.Label, lbl_err_seccion: tk.Label
) -> tuple[bool, Optional[float], Optional[float], Optional[int]]:
    ok = True
    for lbl in (lbl_err_codigo, lbl_err_nombre, lbl_err_precio, lbl_err_stock, lbl_err_seccion):
        lbl.config(text="")

    if not codigo.strip():
        lbl_err_codigo.config(text="Código requerido")
        ok = False

    if not nombre.strip():
        lbl_err_nombre.config(text="Nombre requerido")
        ok = False

    precio_venta: Optional[float] = None
    try:
        precio_venta = float(precio_venta_str)
        if precio_venta < 0:
            raise ValueError()
    except Exception:
        lbl_err_precio.config(text="Precio inválido")
        ok = False

    stock: Optional[int] = None
    try:
        stock = int(stock_str)
        if stock < 0:
            raise ValueError()
    except Exception:
        lbl_err_stock.config(text="Stock inválido")
        ok = False

    if not seccion_val.strip():
        lbl_err_seccion.config(text="Seleccione una sección")
        ok = False

    return ok, precio_venta, None, stock

def abrir_modal_producto(
    parent: tk.Misc,
    modo: str,
    tabla: ttk.Treeview,
    combo_categoria_filter: ttk.Combobox,
    entry_buscar: Optional[PlaceholderEntry] = None,
    producto_id: Optional[int] = None,
) -> None:
    """
    modo: "nuevo" o "editar".
    Si modo == "editar", se usa producto_id; si es None, se toma del seleccionado en la tabla.
    """
    if modo not in ("nuevo", "editar"):
        messagebox.showerror("Error", "Modo inválido")
        return

    if modo == "editar" and producto_id is None:
        producto_id = _get_selected_row_id(tabla)
        if producto_id is None:
            messagebox.showwarning("Seleccionar", "Seleccione un producto para editar")
            return

    producto = None
    parsed = None
    if modo == "editar":
        try:
            producto = obtener_producto_por_id(producto_id)  # type: ignore[arg-type]
            parsed = _parse_producto(producto)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el producto: {e}")
            return
        if producto is None:
            messagebox.showerror("Error", "Producto no encontrado")
            return

    # --- Construir modal ---
    top = tk.Toplevel(parent)
    top.title("Nuevo producto" if modo == "nuevo" else "Editar producto")
    top.transient(parent)
    top.grab_set()
    top.resizable(True, True)

    frm = ttk.Frame(top, padding=14)
    frm.pack(fill="both", expand=True)

    # Código *
    ttk.Label(frm, text="Código (SKU)").grid(row=0, column=0, sticky="w", padx=6, pady=6)
    tk.Label(frm, text="*", fg="red").grid(row=0, column=2, sticky="w")
    entry_codigo = ttk.Entry(frm, width=34)
    entry_codigo.grid(row=0, column=1, padx=6, pady=6, sticky="ew")

    # Nombre *
    ttk.Label(frm, text="Nombre").grid(row=1, column=0, sticky="w", padx=6, pady=6)
    tk.Label(frm, text="*", fg="red").grid(row=1, column=2, sticky="w")
    entry_nombre = ttk.Entry(frm, width=44)
    entry_nombre.grid(row=1, column=1, padx=6, pady=6, sticky="ew")

    # Precio venta *
    ttk.Label(frm, text="Precio venta").grid(row=2, column=0, sticky="w", padx=6, pady=6)
    tk.Label(frm, text="*", fg="red").grid(row=2, column=2, sticky="w")
    entry_precio_venta = ttk.Entry(frm, width=24)
    entry_precio_venta.grid(row=2, column=1, padx=6, pady=6, sticky="w")

    # Precio costo (opcional)
    ttk.Label(frm, text="Precio costo (opcional)").grid(row=3, column=0, sticky="w", padx=6, pady=6)
    entry_precio_costo = ttk.Entry(frm, width=24)
    entry_precio_costo.grid(row=3, column=1, padx=6, pady=6, sticky="w")

    # Stock *
    ttk.Label(frm, text="Stock").grid(row=4, column=0, sticky="w", padx=6, pady=6)
    tk.Label(frm, text="*", fg="red").grid(row=4, column=2, sticky="w")
    entry_stock = ttk.Entry(frm, width=24)
    entry_stock.grid(row=4, column=1, padx=6, pady=6, sticky="w")

    # Sección * (con "Ninguno")
    ttk.Label(frm, text="Sección").grid(row=5, column=0, sticky="w", padx=6, pady=6)
    tk.Label(frm, text="*", fg="red").grid(row=5, column=2, sticky="w")
    combo_seccion = ttk.Combobox(frm, state="readonly", width=30)
    combo_seccion.grid(row=5, column=1, padx=6, pady=6, sticky="w")
    combo_seccion["values"] = SECCIONES
    combo_seccion.set("Ninguno")

    # Categoría (opcional)
    ttk.Label(frm, text="Categoría (opcional)").grid(row=6, column=0, sticky="w", padx=6, pady=6)
    combo_categoria = ttk.Combobox(frm, state="readonly", width=30)
    combo_categoria.grid(row=6, column=1, padx=6, pady=6, sticky="w")
    cargar_categorias_combobox(combo_categoria, include_all=False)


    # Labels de error
    lbl_err_codigo = tk.Label(frm, text="", fg="red");    lbl_err_codigo.grid(row=0, column=3, sticky="w")
    lbl_err_nombre = tk.Label(frm, text="", fg="red");    lbl_err_nombre.grid(row=1, column=3, sticky="w")
    lbl_err_precio = tk.Label(frm, text="", fg="red");    lbl_err_precio.grid(row=2, column=3, sticky="w")
    lbl_err_stock  = tk.Label(frm, text="", fg="red");    lbl_err_stock.grid(row=4, column=3, sticky="w")
    lbl_err_seccion= tk.Label(frm, text="", fg="red");    lbl_err_seccion.grid(row=5, column=3, sticky="w")

    # Prellenar si editamos
    if parsed:
        entry_codigo.insert(0, _safe_str(parsed["codigo"]))
        entry_nombre.insert(0, _safe_str(parsed["nombre"]))
        entry_precio_venta.insert(0, _safe_str(parsed["precio_venta"]))
        entry_precio_costo.insert(0, _safe_str(parsed["precio_costo"]))
        entry_stock.insert(0, _safe_str(parsed["stock"]))
        combo_seccion.set(_safe_str(parsed["seccion"] or "Ninguno"))
        # set categoría por ID
        if parsed.get("categoria_id") is not None:
            for v in combo_categoria["values"]:
                if _safe_str(v).startswith(f"{parsed['categoria_id']} -"):
                    combo_categoria.set(v); break


    def on_confirm() -> None:
        ok, precio_venta, _pc, stock = _validar_modal(
            entry_codigo.get(), entry_nombre.get(), entry_precio_venta.get(), entry_stock.get(),
            combo_seccion.get(),
            lbl_err_codigo, lbl_err_nombre, lbl_err_precio, lbl_err_stock, lbl_err_seccion
        )
        if not ok:
            return

        # Precio costo opcional
        try:
            precio_costo_val = float(entry_precio_costo.get()) if entry_precio_costo.get().strip() else 0.0
        except Exception:
            messagebox.showerror("Validación", "Precio costo inválido")
            return

        codigo = entry_codigo.get().strip()
        seccion_val = combo_seccion.get().strip() or "Ninguno"
        categoria_id: Optional[int] = parse_id_from_combo_value(combo_categoria.get())


        try:
            if modo == "nuevo":
                _agregar_producto_flexible(
                    nombre=entry_nombre.get().strip(),
                    precio_venta=float(precio_venta),  # type: ignore[arg-type]
                    stock=int(stock),                  # type: ignore[arg-type]
                    sku=codigo,
                    precio_costo=precio_costo_val,
                    seccion=seccion_val,
                    categoria_id=categoria_id
                )
                messagebox.showinfo("OK", "Producto agregado")
            else:
                assert producto_id is not None
                _editar_producto_flexible(
                    int(producto_id),
                    nombre=entry_nombre.get().strip(),
                    precio_venta=float(precio_venta),  # type: ignore[arg-type]
                    stock=int(stock),                  # type: ignore[arg-type]
                    sku=codigo,
                    precio_costo=precio_costo_val,
                    seccion=seccion_val,
                    categoria_id=categoria_id
                )
                messagebox.showinfo("OK", "Producto actualizado")

            # refrescar tabla respetando filtro/búsqueda
            fil_sel = combo_categoria_filter.get()
            if fil_sel and fil_sel != "Todas":
                filtrar_por_categoria(combo_categoria_filter, tabla)
            else:
                cargar_datos(tabla)
            if entry_buscar and entry_buscar.value():
                filtrar_en_tabla_por_termino(entry_buscar.value(), tabla)

            top.destroy()
        except ValueError as ve:
            messagebox.showerror("Error", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {e}")

    # Botones
    btns = ttk.Frame(frm)
    btns.grid(row=8, column=0, columnspan=2, pady=12)
    ttk.Button(btns, text=("Agregar" if modo == "nuevo" else "Guardar cambios"),
               command=on_confirm, style=STYLE_PRIMARY).grid(row=0, column=0, padx=8)
    ttk.Button(btns, text="Cancelar", command=top.destroy).grid(row=0, column=1, padx=8)

# ============================
# === PANEL IZQUIERDO       ==
# ============================
def _build_left_panel(root: tk.Widget) -> dict[str, Any]:
    left = ttk.Frame(root, padding=14)
    left.grid(row=0, column=0, sticky="ns")
    left.columnconfigure(1, weight=1)

    tk.Label(left, text="Buscar").grid(row=0, column=0, padx=8, pady=8, sticky="w")
    entry_buscar = PlaceholderEntry(left, PLACEHOLDER_BUSCAR, width=32)
    entry_buscar.grid(row=0, column=1, padx=8, pady=8, sticky="ew")

    acciones = ttk.LabelFrame(left, text="Acciones", padding=10)
    acciones.grid(row=1, column=0, columnspan=2, pady=12, sticky="ew")
    for i in range(2):
        acciones.columnconfigure(i, weight=1)

    add_btn = ttk.Button(acciones, text="➕  Nuevo producto", style=STYLE_PRIMARY)
    edit_btn = ttk.Button(acciones, text="✏️  Editar seleccionado", style=STYLE_DEFAULT)
    del_btn = ttk.Button(acciones, text="🗑️  Eliminar", style=STYLE_DANGER)
    in_btn  = ttk.Button(acciones, text="⬆️  Entrada stock", style=STYLE_DEFAULT)
    out_btn = ttk.Button(acciones, text="⬇️  Salida stock", style=STYLE_DEFAULT)

    add_btn.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
    edit_btn.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
    del_btn.grid(row=1, column=0, padx=8, pady=8, sticky="ew")
    in_btn.grid(row=1, column=1, padx=8, pady=8, sticky="ew")
    out_btn.grid(row=2, column=0, padx=8, pady=8, sticky="ew", columnspan=2)

    return {
        "frame": left,
        "entry_buscar": entry_buscar,
        "add_btn": add_btn,
        "edit_btn": edit_btn,
        "del_btn": del_btn,
        "in_btn": in_btn,
        "out_btn": out_btn,
    }

# ============================
# === PANEL DERECHO (tabla) ==
# ============================
def _build_right_panel(root: tk.Widget) -> dict[str, Any]:
    right = ttk.Frame(root, padding=10)
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(1, weight=1)

    top_filters = ttk.Frame(right)
    top_filters.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    for i in range(6):
        top_filters.columnconfigure(i, weight=(1 if i == 1 else 0))

    tk.Label(top_filters, text="Categoría (filtro):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
    combo_categoria = ttk.Combobox(top_filters, state="readonly", width=32)
    combo_categoria.grid(row=0, column=1, padx=6, pady=6, sticky="w")
    cargar_categorias_combobox(combo_categoria, include_all=True)

    btn_aplicar = ttk.Button(top_filters, text="Aplicar filtro")
    btn_agregar_cat = ttk.Button(top_filters, text="Agregar categoría")
    btn_eliminar_cat = ttk.Button(top_filters, text="Eliminar categoría")
    btn_exportar = ttk.Button(top_filters, text="💾  Exportar CSV", style=STYLE_PRIMARY)

    btn_aplicar.grid(row=0, column=2, padx=6, pady=6)
    btn_agregar_cat.grid(row=0, column=3, padx=6, pady=6)
    btn_eliminar_cat.grid(row=0, column=4, padx=6, pady=6)
    btn_exportar.grid(row=0, column=5, padx=8, pady=6)

    # Tabla + scrollbars
    table_container = ttk.Frame(right)
    table_container.grid(row=1, column=0, sticky="nsew")
    table_container.columnconfigure(0, weight=1)
    table_container.rowconfigure(0, weight=1)

    tabla = _crear_tabla(table_container)
    tabla.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

    vsb = ttk.Scrollbar(table_container, orient="vertical", command=tabla.yview)
    hsb = ttk.Scrollbar(table_container, orient="horizontal", command=tabla.xview)
    tabla.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    return {
        "frame": right,
        "combo_categoria": combo_categoria,
        "tabla": tabla,
        "btn_aplicar": btn_aplicar,
        "btn_agregar_cat": btn_agregar_cat,
        "btn_eliminar_cat": btn_eliminar_cat,
        "btn_exportar": btn_exportar,
    }

# ============================
# === CATEGORÍAS handlers   ==
# ============================
def agregar_categoria_handler(combo_categoria_filter: ttk.Combobox) -> None:
    nombre = simpledialog.askstring("Nueva categoría", "Nombre de la nueva categoría:")
    if not (nombre and nombre.strip()):
        return
    try:
        agregar_categoria(nombre.strip())
        cargar_categorias_combobox(combo_categoria_filter, include_all=True)
        messagebox.showinfo("Categoría", "Categoría creada.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def eliminar_categoria_handler(combo_categoria_filter: ttk.Combobox) -> None:
    sel = combo_categoria_filter.get()
    if not sel or sel == "Todas":
        messagebox.showwarning("Seleccionar", "Seleccione una categoría válida para eliminar")
        return
    if not messagebox.askyesno("Confirmar", "¿Eliminar la categoría seleccionada?"):
        return
    try:
        id_cat = int(sel.split(" - ")[0])
        eliminar_categoria(id_cat)
        cargar_categorias_combobox(combo_categoria_filter, include_all=True)
        messagebox.showinfo("Categoría", "Categoría eliminada.")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# ============================
# === ESTILOS/ATAJOS        ==
# ============================
def _apply_fonts_and_styles(root: tk.Misc) -> None:
    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass

    # Aumentar fuentes por defecto para que "se vea más grande"
    try:
        default_font = tkfont.nametofont("TkDefaultFont")
        text_font = tkfont.nametofont("TkTextFont")
        fixed_font = tkfont.nametofont("TkFixedFont")
        heading_font = tkfont.nametofont("TkHeadingFont")
        icon_font = tkfont.nametofont("TkIconFont")
        menu_font = tkfont.nametofont("TkMenuFont")
        small_font = tkfont.nametofont("TkSmallCaptionFont")

        for f in (default_font, text_font, fixed_font, heading_font, icon_font, menu_font, small_font):
            size = f.cget("size")
            try:
                f.configure(size=int(size) + 6)
            except Exception:
                pass
    except Exception:
        pass

    estilo.configure("TButton", padding=(12, 10))
    try:
        estilo.configure(STYLE_PRIMARY, foreground="white", background="#0078D7")
        estilo.map(STYLE_PRIMARY, background=[("active", "#0a66c2")])
        estilo.configure(STYLE_DANGER, foreground="white", background="#D9534F")
        estilo.map(STYLE_DANGER, background=[("active", "#c9302c")])
        estilo.configure(STYLE_DEFAULT, foreground="black")
        estilo.configure("Treeview", rowheight=30)
        estilo.configure("Treeview.Heading", font=("Segoe UI", 15, "bold"))
    except Exception:
        pass

def _bind_shortcuts(root: tk.Misc, search_entry: PlaceholderEntry, tabla: ttk.Treeview) -> None:
    root.bind_all("<Control-f>", lambda e: (search_entry.focus_set(), "break"))
    root.bind_all("<Delete>", lambda e: tabla.event_generate("<<delete_selected>>"))
    root.bind_all("<Return>", lambda e: tabla.event_generate("<<edit_selected>>"))

# ============================
# === ENTRADA PRINCIPAL     ==
# ============================
def ventana_productos(parent: tk.Misc | None = None) -> None:
    """
    Si parent es None, crea una ventana raíz (Tk) y ejecuta mainloop.
    Si parent no es None, crea un Toplevel (no llama mainloop).
    """
    stand_alone = parent is None
    root_window: tk.Misc
    container: tk.Misc

    if stand_alone:
        root_window = tk.Tk()
        root_window.title("Inventario - Productos")
        container = root_window
    else:
        root_window = parent  # type: ignore[assignment]
        toplevel = tk.Toplevel(parent)
        toplevel.title("Inventario - Productos")
        toplevel.transient(parent)
        toplevel.grab_set()
        toplevel.resizable(True, True)
        container = toplevel

    # Permitir resize y establecer tamaño inicial
    # Permitir resize y establecer tamaño inicial
    try:
        container.state("zoomed")        # se abre maximizada
        container.geometry("1900x1080")
        container.minsize(1200, 720)     # tamaño mínimo
        container.resizable(True, True)  # se puede redimensionar
    except Exception:
        pass


    _apply_fonts_and_styles(container)

    # Layout principal
    try:
        container.columnconfigure(0, weight=0)  # panel izquierdo
        container.columnconfigure(1, weight=1)  # panel derecho
        container.rowconfigure(0, weight=1)
    except Exception:
        pass

    left = _build_left_panel(container)   # type: ignore[arg-type]
    right = _build_right_panel(container) # type: ignore[arg-type]

    # Bindings
    left["entry_buscar"].bind(  # type: ignore
        "<KeyRelease>",
        lambda e: filtrar_en_tabla_por_termino(left["entry_buscar"].value(), right["tabla"])  # type: ignore
    )
    right["combo_categoria"].bind(  # type: ignore
        "<<ComboboxSelected>>",
        lambda e: filtrar_por_categoria(right["combo_categoria"], right["tabla"])  # type: ignore
    )
    right["tabla"].bind(  # type: ignore
        "<Double-1>",
        lambda e: abrir_modal_producto(
            container, "editar", right["tabla"], right["combo_categoria"], left["entry_buscar"]  # type: ignore
        )
    )

    def _edit_selected_event(_: Any = None) -> None:
        abrir_modal_producto(
            container, "editar", right["tabla"], right["combo_categoria"], left["entry_buscar"]  # type: ignore
        )

    def _delete_selected_event(_: Any = None) -> None:
        borrar_handler(right["tabla"])  # type: ignore

    right["tabla"].bind("<<edit_selected>>", _edit_selected_event)     # type: ignore
    right["tabla"].bind("<<delete_selected>>", _delete_selected_event) # type: ignore

    left["add_btn"].config(  # type: ignore
        command=lambda: abrir_modal_producto(
            container, "nuevo", right["tabla"], right["combo_categoria"], left["entry_buscar"]  # type: ignore
        )
    )
    left["edit_btn"].config(command=_edit_selected_event)  # type: ignore
    left["del_btn"].config(command=_delete_selected_event) # type: ignore
    left["in_btn"].config(   # type: ignore
        command=lambda: ajustar_stock_handler(container, right["tabla"], "entrada")  # type: ignore
    )
    left["out_btn"].config(  # type: ignore
        command=lambda: ajustar_stock_handler(container, right["tabla"], "salida")  # type: ignore
    )

    right["btn_aplicar"].config(  # type: ignore
        command=lambda: filtrar_por_categoria(right["combo_categoria"], right["tabla"])  # type: ignore
    )
    right["btn_agregar_cat"].config(  # type: ignore
        command=lambda: agregar_categoria_handler(right["combo_categoria"])  # type: ignore
    )
    right["btn_eliminar_cat"].config(  # type: ignore
        command=lambda: eliminar_categoria_handler(right["combo_categoria"])  # type: ignore
    )
    right["btn_exportar"].config(  # type: ignore
        command=lambda: export_tabla_csv(right["tabla"], container)  # type: ignore
    )

    _bind_shortcuts(container, left["entry_buscar"], right["tabla"])  # type: ignore

    cargar_datos(right["tabla"])  # type: ignore

    if stand_alone:
        try:
            root_window.mainloop()
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    ventana_productos()
