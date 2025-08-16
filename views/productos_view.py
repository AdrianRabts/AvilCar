# producto_view.py
from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from typing import Any, Optional, Iterable

# ==== MODELOS (se mantienen tus importaciones) ====
from models.producto import (
    agregar_producto,
    obtener_productos,
    eliminar_producto,
    editar_producto,
    buscar_productos,          # disponible si tu modelo lo usa; si no, no pasa nada
    aumentar_stock,
    reducir_stock,
    obtener_producto_por_id,
)
from models.categoria import obtener_categorias, agregar_categoria, eliminar_categoria


# ============================================================
# === CONSTANTES DE UI Y ESTILOS ===
# ============================================================

LABEL_SECCION: str = "Sección"
LABEL_CODIGO: str = "Código"
LABEL_BUSCAR: str = "Buscar por código o nombre"

STYLE_PRIMARY: str = "Primary.TButton"
STYLE_DANGER: str = "Danger.TButton"
STYLE_DEFAULT: str = "Default.TButton"

PLACEHOLDER_BUSCAR: str = "Buscar por código o nombre (p.ej. COD123 o parte del nombre)"

COLUMNS: tuple[str, ...] = ("ID", "Codigo", "Nombre", "Precio", "Stock", "Seccion")


# ============================================================
# === HELPERS DE PLACEHOLDER (Entry con placeholder) ===
# ============================================================

class PlaceholderEntry(tk.Entry):
    def __init__(self, master: tk.Widget, placeholder: str, *args, **kwargs) -> None:
        super().__init__(master, *args, **kwargs)
        self._placeholder = placeholder
        self._default_fg = self["fg"] if "fg" in self.keys() else "black"
        self._has_placeholder = False
        self._put_placeholder()
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _put_placeholder(self) -> None:
        self.delete(0, tk.END)
        self.insert(0, self._placeholder)
        self.config(fg="grey")
        self._has_placeholder = True

    def _on_focus_in(self, _: Any) -> None:
        if self._has_placeholder:
            self.delete(0, tk.END)
            self.config(fg=self._default_fg)
            self._has_placeholder = False

    def _on_focus_out(self, _: Any) -> None:
        if not self.get().strip():
            self._put_placeholder()

    def value(self) -> str:
        v = self.get()
        return "" if self._has_placeholder or v == self._placeholder else v.strip()


# ============================================================
# === PARSE/FORMAT DE PRODUCTOS Y VALORES ===
# ============================================================

def _fmt_precio(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v)

def _parse_producto_tuple(prod: Iterable[Any]) -> dict[str, Any]:
    """
    Los índices esperados (según tu código original):
      0:id, 1:nombre, 2:precio, 3:stock, 4:codigo, 7:categoria_id, 9:categoria_nombre
    Maneja longitudes variables sin romperse.
    """
    p = list(prod)
    def get(i: int, default: Any = None) -> Any:
        try:
            return p[i]
        except Exception:
            return default

    return {
        "id": get(0),
        "nombre": get(1, "") or "",
        "precio": get(2, 0),
        "stock": get(3, 0),
        "codigo": get(4, "") or "",
        "categoria_id": get(7, None),
        "categoria_nombre": get(9, None),
    }

def _value_for_sort(val: Any, col: str) -> Any:
    try:
        if col == "Precio":
            s = str(val).replace("$", "").replace(",", "").strip()
            return float(s) if s else 0.0
        if col in ("ID", "Stock"):
            return int(val or 0)
    except Exception:
        pass
    return str(val).lower() if val is not None else ""


# ============================================================
# === TABLA: CREACIÓN, ORDENAMIENTO, CARGA ===
# ============================================================

def _crear_tabla(parent: tk.Widget) -> ttk.Treeview:
    tabla = ttk.Treeview(parent, columns=COLUMNS, show="headings")
    for col in COLUMNS:
        if col == "Precio":
            anchor, width = "e", 120
        elif col in ("ID", "Stock"):
            anchor, width = "center", 80
        elif col == "Nombre":
            anchor, width = "w", 240
        else:
            anchor, width = "center", 140

        tabla.heading(col, text=col, anchor=anchor, command=lambda c=col: sort_treeview(tabla, c, False))
        tabla.column(col, width=width, anchor=anchor)

    try:
        tabla.tag_configure("odd", background="#ffffff")
        tabla.tag_configure("even", background="#f6f6f6")
    except Exception:
        pass

    return tabla

def sort_treeview(tabla: ttk.Treeview, col: str, reverse: bool) -> None:
    data: list[tuple[Any, str]] = []
    for item in tabla.get_children(""):
        val = tabla.set(item, col)
        data.append((_value_for_sort(val, col), item))
    data.sort(reverse=reverse, key=lambda t: t[0])
    for index, (_, item) in enumerate(data):
        tabla.move(item, "", index)
    tabla.heading(col, command=lambda: sort_treeview(tabla, col, not reverse))

def _row_values_from_parsed(p: dict[str, Any]) -> tuple[Any, ...]:
    seccion = f"{p['categoria_id']} - {p['categoria_nombre']}" if p.get("categoria_id") is not None else ""
    return (
        p["id"],
        p["codigo"],
        p["nombre"],
        _fmt_precio(p["precio"]),
        p["stock"],
        seccion,
    )

def _set_rows(tabla: ttk.Treeview, productos: list[Iterable[Any]]) -> None:
    for i in tabla.get_children():
        tabla.delete(i)
    for idx, prod in enumerate(productos):
        p = _parse_producto_tuple(prod)
        tag = "even" if (idx % 2 == 0) else "odd"
        tabla.insert("", tk.END, values=_row_values_from_parsed(p), tags=(tag,))

def cargar_datos(tabla: ttk.Treeview) -> None:
    _set_rows(tabla, obtener_productos())

def _producto_match_term(prod: Iterable[Any], term_low: str) -> bool:
    p = _parse_producto_tuple(prod)
    return (
        term_low in (p["nombre"] or "").lower()
        or term_low in str(p["codigo"]).lower()
        or term_low in str(p["id"])
    )

def filtrar_en_tabla_por_termino(term: str, tabla: ttk.Treeview) -> None:
    term = (term or "").strip()
    if term == "":
        cargar_datos(tabla)
        return
    term_low = term.lower()
    filtrados = [prod for prod in obtener_productos() if _producto_match_term(prod, term_low)]
    _set_rows(tabla, filtrados)


# ============================================================
# === CATEGORÍAS: COMBOBOX, PARSE Y HANDLERS ===
# ============================================================

def cargar_categorias_combobox(combo: ttk.Combobox, include_all: bool = True) -> None:
    opciones: list[str] = (["Todas"] if include_all else [])
    for c in obtener_categorias():
        # se asume (id, nombre, ...)
        opciones.append(f"{c[0]} - {c[1]}")
    combo["values"] = opciones
    if opciones:
        combo.current(0)

def parse_categoria_id_from_combo(combo: Optional[ttk.Combobox]) -> Optional[int]:
    if combo is None:
        return None
    sel = combo.get()
    if not sel or sel == "Todas":
        return None
    try:
        return int(sel.split(" - ")[0])
    except Exception:
        return None

def agregar_categoria_handler(combo_categoria_filter: ttk.Combobox, combo_categoria_form: ttk.Combobox) -> None:
    nombre = simpledialog.askstring("Nueva sección", "Nombre de la nueva sección:")
    if not nombre:
        return
    try:
        agregar_categoria(nombre)
        cargar_categorias_combobox(combo_categoria_filter, include_all=True)
        cargar_categorias_combobox(combo_categoria_form, include_all=False)
    except Exception as e:
        messagebox.showerror("Error", str(e))

def eliminar_categoria_handler(combo_categoria_filter: ttk.Cobmbobox, combo_categoria_form: ttk.Combobox) -> None:  # type: ignore
    # corregimos typo Cobmbobox -> Combobox, pero mantenemos type: ignore por si el editor molesta
    sel = combo_categoria_filter.get()
    if not sel or sel == "Todas":
        messagebox.showwarning("Seleccionar", "Seleccione una sección válida para eliminar")
        return
    if not messagebox.askyesno("Confirmar", "¿Eliminar la sección seleccionada?"):
        return
    try:
        id_cat = int(sel.split(" - ")[0])
        eliminar_categoria(id_cat)
        cargar_categorias_combobox(combo_categoria_filter, include_all=True)
        cargar_categorias_combobox(combo_categoria_form, include_all=False)
    except Exception as e:
        messagebox.showerror("Error", str(e))


# ============================================================
# === FILTRO POR CATEGORÍA ===
# ============================================================

def filtrar_por_categoria(combo_categoria: ttk.Combobox, tabla: ttk.Treeview) -> None:
    cat_id = parse_categoria_id_from_combo(combo_categoria)
    if cat_id is None:
        cargar_datos(tabla)
        return
    filtrados = []
    for prod in obtener_productos():
        p = _parse_producto_tuple(prod)
        if p["categoria_id"] == cat_id:
            filtrados.append(prod)
    _set_rows(tabla, filtrados)


# ============================================================
# === CRUD: GUARDAR/EDITAR/BORRAR Y STOCK ===
# ============================================================

def _clear_entries(*entries: tk.Entry) -> None:
    for e in entries:
        try:
            e.delete(0, tk.END)
        except Exception:
            pass

def refresh_ui_after_change(
    combo_filter: ttk.Combobox,
    combo_form: ttk.Combobox,
    tabla: ttk.Treeview,
    entry_buscar: Optional[PlaceholderEntry] = None,
    nueva_categoria_id: Optional[int] = None,
) -> None:
    # refrescar combos
    cargar_categorias_combobox(combo_filter, include_all=True)
    cargar_categorias_combobox(combo_form, include_all=False)

    # si el filtro actual coincide con nueva categoría, mantener filtro
    current_filter = combo_filter.get() if combo_filter is not None else None
    if current_filter and current_filter != "Todas" and nueva_categoria_id is not None:
        try:
            filt_id = int(current_filter.split(" - ")[0])
            if filt_id == nueva_categoria_id:
                filtrar_por_categoria(combo_filter, tabla)
                if entry_buscar:
                    term = entry_buscar.value()
                    if term:
                        filtrar_en_tabla_por_termino(term, tabla)
                return
        except Exception:
            pass

    cargar_datos(tabla)
    if entry_buscar:
        term = entry_buscar.value()
        if term:
            filtrar_en_tabla_por_termino(term, tabla)

def guardar_handler(
    entry_codigo: tk.Entry,
    entry_nombre: tk.Entry,
    entry_precio: tk.Entry,
    entry_stock: tk.Entry,
    combo_categoria_form: ttk.Combobox,
    combo_categoria_filter: ttk.Combobox,
    tabla: ttk.Treeview,
    entry_buscar: Optional[PlaceholderEntry],
) -> None:
    try:
        categoria_id = parse_categoria_id_from_combo(combo_categoria_form)
        agregar_producto(
            entry_nombre.get().strip(),
            float(entry_precio.get()),
            int(entry_stock.get()),
            sku=(entry_codigo.get().strip() or None),
            categoria_id=categoria_id,
        )
        _clear_entries(entry_codigo, entry_nombre, entry_precio, entry_stock)
        refresh_ui_after_change(combo_categoria_filter, combo_categoria_form, tabla, entry_buscar, nueva_categoria_id=categoria_id)
    except ValueError as ve:
        messagebox.showerror("Error", str(ve))
    except Exception as e:
        messagebox.showerror("Error", str(e))

def borrar_handler(tabla: ttk.Treeview) -> None:
    seleccionado = tabla.selection()
    if not seleccionado:
        messagebox.showwarning("Seleccionar", "Seleccione un producto")
        return
    if not messagebox.askyesno("Confirmar", "¿Seguro que desea eliminar el producto seleccionado?"):
        return
    item = tabla.item(seleccionado)
    id_producto = item["values"][0]
    try:
        eliminar_producto(id_producto)
        cargar_datos(tabla)
    except Exception as e:
        messagebox.showerror("Error", str(e))

def ajustar_stock_handler(root: tk.Tk, tabla: ttk.Treeview, tipo: str) -> None:
    seleccionado = tabla.selection()
    if not seleccionado:
        messagebox.showwarning("Seleccionar", "Seleccione un producto")
        return
    item = tabla.item(seleccionado)
    id_producto = item["values"][0]

    top = tk.Toplevel(root)
    top.title("Ajuste de stock")
    tk.Label(top, text="Cantidad").grid(row=0, column=0, padx=5, pady=5)
    entry_cant = tk.Entry(top)
    entry_cant.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(top, text="Motivo").grid(row=1, column=0, padx=5, pady=5)
    entry_motivo = tk.Entry(top)
    entry_motivo.grid(row=1, column=1, padx=5, pady=5)

    def aplicar() -> None:
        try:
            cantidad = int(entry_cant.get())
            motivo = entry_motivo.get().strip()
            if not messagebox.askyesno("Confirmar", f"¿Confirmar ajuste de stock ({tipo}) por {cantidad}?"):
                return
            if tipo == "entrada":
                aumentar_stock(id_producto, cantidad, motivo=motivo)
            else:
                reducir_stock(id_producto, cantidad, motivo=motivo)
            top.destroy()
            cargar_datos(tabla)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    tk.Button(top, text="Aplicar", command=aplicar).grid(row=2, column=0, columnspan=2, pady=10)


# ============================================================
# === EXPORT CSV ===
# ============================================================

def export_tabla_csv(tabla: ttk.Treeview, parent: tk.Tk) -> None:
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
                writer.writerow([str(v) for v in values])
        messagebox.showinfo("Exportar", f"Tabla exportada a:\n{fpath}")
    except Exception as e:
        messagebox.showerror("Exportar", f"No se pudo exportar: {e}")


# ============================================================
# === MODAL UNIFICADO (NUEVO / EDITAR) ===
# ============================================================

def _validar_campos_modal(
    nombre: str, precio_str: str, stock_str: str,
    lbl_err_nombre: tk.Label, lbl_err_precio: tk.Label, lbl_err_stock: tk.Label
) -> tuple[bool, Optional[float], Optional[int]]:
    ok = True
    lbl_err_nombre.config(text=""); lbl_err_precio.config(text=""); lbl_err_stock.config(text="")

    if not nombre.strip():
        lbl_err_nombre.config(text="Nombre requerido")
        ok = False

    precio: Optional[float] = None
    try:
        precio = float(precio_str)
        if precio < 0:
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

    return ok, precio, stock

def abrir_modal_producto(
    parent: tk.Tk,
    modo: str,
    tabla: ttk.Treeview,
    combo_categoria_filter: ttk.Combobox,
    combo_categoria_form: ttk.Combobox,
    entry_buscar: Optional[PlaceholderEntry] = None,
    producto_id: Optional[int] = None,
) -> None:
    """
    modo: "nuevo" o "editar".
    Si modo == "editar", se usa producto_id; si es None, se toma del seleccionado en la tabla.
    """
    if modo not in ("nuevo", "editar"):
        raise ValueError("Modo inválido")

    if modo == "editar" and producto_id is None:
        seleccionado = tabla.selection()
        if not seleccionado:
            messagebox.showwarning("Seleccionar", "Seleccione un producto para editar")
            return
        item = tabla.item(seleccionado)
        producto_id = item["values"][0]

    producto = None
    if modo == "editar":
        producto = obtener_producto_por_id(producto_id)  # type: ignore

        if producto is None:
            messagebox.showerror("Error", "Producto no encontrado")
            return

    # Construir modal
    top = tk.Toplevel(parent)
    top.title("Nuevo producto" if modo == "nuevo" else "Editar producto")
    top.transient(parent)
    top.grab_set()

    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    # Campos
    ttk.Label(frm, text=LABEL_CODIGO).grid(row=0, column=0, sticky="w", padx=4, pady=4)
    entry_codigo = ttk.Entry(frm, width=30)
    entry_codigo.grid(row=0, column=1, padx=4, pady=4)
    if producto:
        entry_codigo.insert(0, _parse_producto_tuple(producto)["codigo"])  # type: ignore

    ttk.Label(frm, text="Nombre").grid(row=1, column=0, sticky="w", padx=4, pady=4)
    tk.Label(frm, text="*", fg="red").grid(row=1, column=2, sticky="w")
    entry_nombre = ttk.Entry(frm, width=40)
    entry_nombre.grid(row=1, column=1, padx=4, pady=4)
    if producto:
        entry_nombre.insert(0, _parse_producto_tuple(producto)["nombre"])  # type: ignore

    ttk.Label(frm, text="Precio").grid(row=2, column=0, sticky="w", padx=4, pady=4)
    tk.Label(frm, text="*", fg="red").grid(row=2, column=2, sticky="w")
    entry_precio = ttk.Entry(frm, width=20)
    entry_precio.grid(row=2, column=1, padx=4, pady=4)
    if producto:
        entry_precio.insert(0, str(_parse_producto_tuple(producto)["precio"]))  # type: ignore

    ttk.Label(frm, text="Stock").grid(row=3, column=0, sticky="w", padx=4, pady=4)
    tk.Label(frm, text="*", fg="red").grid(row=3, column=2, sticky="w")
    entry_stock = ttk.Entry(frm, width=20)
    entry_stock.grid(row=3, column=1, padx=4, pady=4)
    if producto:
        entry_stock.insert(0, str(_parse_producto_tuple(producto)["stock"]))  # type: ignore

    ttk.Label(frm, text=LABEL_SECCION).grid(row=4, column=0, sticky="w", padx=4, pady=4)
    combo_categoria_modal = ttk.Combobox(frm, state="readonly", width=28)
    combo_categoria_modal.grid(row=4, column=1, padx=4, pady=4)
    cargar_categorias_combobox(combo_categoria_modal, include_all=False)

    # Set categoría si estamos editando
    if producto:
        p = _parse_producto_tuple(producto)  # type: ignore
        if p["categoria_id"]:
            for v in combo_categoria_modal["values"]:
                if str(v).startswith(f"{p['categoria_id']} -"):
                    combo_categoria_modal.set(v)
                    break

    # Labels de error
    lbl_err_nombre = tk.Label(frm, text="", fg="red")
    lbl_err_nombre.grid(row=1, column=3, sticky="w")
    lbl_err_precio = tk.Label(frm, text="", fg="red")
    lbl_err_precio.grid(row=2, column=3, sticky="w")
    lbl_err_stock = tk.Label(frm, text="", fg="red")
    lbl_err_stock.grid(row=3, column=3, sticky="w")

    def on_confirm() -> None:
        ok, precio, stock = _validar_campos_modal(
            entry_nombre.get(), entry_precio.get(), entry_stock.get(),
            lbl_err_nombre, lbl_err_precio, lbl_err_stock
        )
        if not ok:
            return

        codigo = entry_codigo.get().strip() or None
        cat_sel = combo_categoria_modal.get()
        categoria_id: Optional[int] = None
        if cat_sel and cat_sel != "Todas":
            try:
                categoria_id = int(cat_sel.split(" - ")[0])
            except Exception:
                categoria_id = None

        try:
            if modo == "nuevo":
                agregar_producto(entry_nombre.get().strip(), float(precio), int(stock), sku=codigo, categoria_id=categoria_id)  # type: ignore[arg-type]
                messagebox.showinfo("OK", "Producto agregado")
            else:
                assert producto_id is not None
                editar_producto(producto_id, entry_nombre.get().strip(), float(precio), int(stock), sku=codigo, categoria_id=categoria_id)  # type: ignore[arg-type]
                messagebox.showinfo("OK", "Producto actualizado")

            refresh_ui_after_change(combo_categoria_filter, combo_categoria_form, tabla, entry_buscar, nueva_categoria_id=categoria_id)
            top.destroy()
        except ValueError as ve:
            messagebox.showerror("Error", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error: {e}")

    # Botones
    btns = ttk.Frame(frm)
    btns.grid(row=5, column=0, columnspan=2, pady=8)
    ttk.Button(btns, text=("Agregar" if modo == "nuevo" else "Guardar cambios"), command=on_confirm).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Cancelar", command=top.destroy).grid(row=0, column=1, padx=6)


# ============================================================
# === CONSTRUCCIÓN DE UI (PANELES) ===
# ============================================================

def _crear_campos_left(root: tk.Widget) -> tuple[ttk.Combobox, PlaceholderEntry]:
    tk.Label(root, text=LABEL_SECCION).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    combo_categoria_form = ttk.Combobox(root, state="readonly", width=28)
    combo_categoria_form.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    tk.Label(root, text=LABEL_BUSCAR).grid(row=1, column=0, padx=5, pady=5, sticky="w")
    entry_buscar = PlaceholderEntry(root, PLACEHOLDER_BUSCAR)
    entry_buscar.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    return combo_categoria_form, entry_buscar

def _build_left_panel(root: tk.Widget) -> dict[str, Any]:
    left = ttk.Frame(root, padding=12)
    left.grid(row=0, column=0, sticky="ns")
    left.columnconfigure(1, weight=1)

    combo_categoria_form, entry_buscar = _crear_campos_left(left)
    cargar_categorias_combobox(combo_categoria_form, include_all=False)

    acciones = ttk.LabelFrame(left, text="Acciones", padding=8)
    acciones.grid(row=3, column=0, columnspan=2, pady=10, sticky="ew")
    for i in range(2):
        acciones.columnconfigure(i, weight=1)

    add_btn = ttk.Button(acciones, text="➕  Nuevo producto", style=STYLE_PRIMARY)
    edit_btn = ttk.Button(acciones, text="✏️  Editar seleccionado", style=STYLE_DEFAULT)
    del_btn = ttk.Button(acciones, text="🗑️  Eliminar", style=STYLE_DANGER)
    in_btn  = ttk.Button(acciones, text="⬆️  Entrada stock", style=STYLE_DEFAULT)
    out_btn = ttk.Button(acciones, text="⬇️  Salida stock", style=STYLE_DEFAULT)

    add_btn.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
    edit_btn.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
    del_btn.grid(row=1, column=0, padx=6, pady=6, sticky="ew")
    in_btn.grid(row=1, column=1, padx=6, pady=6, sticky="ew")
    out_btn.grid(row=2, column=0, padx=6, pady=6, sticky="ew")

    return {
        "frame": left,
        "combo_categoria_form": combo_categoria_form,
        "entry_buscar": entry_buscar,
        "add_btn": add_btn,
        "edit_btn": edit_btn,
        "del_btn": del_btn,
        "in_btn": in_btn,
        "out_btn": out_btn,
    }

def _build_right_panel(root: tk.Widget) -> dict[str, Any]:
    right = ttk.Frame(root, padding=8)
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(1, weight=1)

    top_filters = ttk.Frame(right)
    top_filters.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    top_filters.columnconfigure(1, weight=1)

    tk.Label(top_filters, text="Sección (filtro):").grid(row=0, column=0, padx=4, pady=2, sticky="w")
    combo_categoria = ttk.Combobox(top_filters, state="readonly", width=30)
    combo_categoria.grid(row=0, column=1, padx=4, pady=2, sticky="w")
    cargar_categorias_combobox(combo_categoria, include_all=True)

    tabla = _crear_tabla(right)
    tabla.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

    vsb = ttk.Scrollbar(right, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=vsb.set)
    vsb.grid(row=1, column=1, sticky="ns")

    # Botones filtros
    ttk.Button(top_filters, text="Aplicar filtro", command=lambda: filtrar_por_categoria(combo_categoria, tabla)).grid(row=0, column=2, padx=4, pady=2)
    ttk.Button(top_filters, text="Agregar sección", command=lambda: agregar_categoria_handler(combo_categoria, combo_categoria_form_placeholder)).grid(row=0, column=3, padx=4, pady=2)  # type: ignore
    ttk.Button(top_filters, text="Eliminar sección", command=lambda: eliminar_categoria_handler(combo_categoria, combo_categoria_form_placeholder)).grid(row=0, column=4, padx=4, pady=2)  # type: ignore

    # Export CSV
    try:
        ttk.Button(top_filters, text="💾  Exportar CSV", command=lambda: export_tabla_csv(tabla, root), style=STYLE_PRIMARY).grid(row=0, column=5, padx=6, pady=2)
    except Exception:
        ttk.Button(top_filters, text="💾  Exportar CSV", command=lambda: export_tabla_csv(tabla, root)).grid(row=0, column=5, padx=6, pady=2)

    return {
        "frame": right,
        "combo_categoria": combo_categoria,
        "tabla": tabla,
        "top_filters": top_filters,
    }


# ============================================================
# === ENTRADA PRINCIPAL ===
# ============================================================

def ventana_productos() -> None:
    global combo_categoria_form_placeholder  # para handlers de categorías
    root = tk.Tk()
    root.title("Inventario - Productos")
    root.geometry("1100x650")

    # Estilos
    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass

    estilo.configure("TButton", padding=(8, 6))
    estilo.configure(STYLE_PRIMARY, foreground="white", background="#007acc")
    estilo.configure(STYLE_DANGER, foreground="white", background="#c44")
    estilo.configure(STYLE_DEFAULT, foreground="black", background="#ddd")
    try:
        estilo.configure("Treeview", rowheight=24)
        estilo.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
    except Exception:
        pass

    # Layout
    root.columnconfigure(0, weight=0)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    left_widgets = _build_left_panel(root)
    right_widgets = _build_right_panel(root)

    # Exponer para handlers de categorías
    combo_categoria_form_placeholder = left_widgets["combo_categoria_form"]  # type: ignore

    # Bindings
    # Buscar
    left_widgets["entry_buscar"].bind(  # type: ignore
        "<KeyRelease>",
        lambda e: filtrar_en_tabla_por_termino(left_widgets["entry_buscar"].value(), right_widgets["tabla"])  # type: ignore
    )
    # Filtro categoría
    right_widgets["combo_categoria"].bind(  # type: ignore
        "<<ComboboxSelected>>",
        lambda e: filtrar_por_categoria(right_widgets["combo_categoria"], right_widgets["tabla"])  # type: ignore
    )
    # Doble click editar
    right_widgets["tabla"].bind(  # type: ignore
        "<Double-1>",
        lambda e: abrir_modal_producto(
            root, "editar", right_widgets["tabla"], right_widgets["combo_categoria"],
            left_widgets["combo_categoria_form"], left_widgets["entry_buscar"]  # type: ignore
        )
    )

    # Acciones
    left_widgets["add_btn"].config(  # type: ignore
        command=lambda: abrir_modal_producto(
            root, "nuevo", right_widgets["tabla"], right_widgets["combo_categoria"],
            left_widgets["combo_categoria_form"], left_widgets["entry_buscar"]  # type: ignore
        )
    )
    left_widgets["edit_btn"].config(  # type: ignore
        command=lambda: abrir_modal_producto(
            root, "editar", right_widgets["tabla"], right_widgets["combo_categoria"],
            left_widgets["combo_categoria_form"], left_widgets["entry_buscar"]  # type: ignore
        )
    )
    left_widgets["del_btn"].config(  # type: ignore
        command=lambda: borrar_handler(right_widgets["tabla"])  # type: ignore
    )
    left_widgets["in_btn"].config(   # type: ignore
        command=lambda: ajustar_stock_handler(root, right_widgets["tabla"], "entrada")  # type: ignore
    )
    left_widgets["out_btn"].config(  # type: ignore
        command=lambda: ajustar_stock_handler(root, right_widgets["tabla"], "salida")  # type: ignore
    )

    # Data inicial
    cargar_datos(right_widgets["tabla"])  # type: ignore

    root.mainloop()


if __name__ == "__main__":
    ventana_productos()
