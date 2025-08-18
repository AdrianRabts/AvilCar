from __future__ import annotations

"""
Ventas (Tkinter + ttk) — versión pro
------------------------------------
- Sin imports circulares.
- Instancia única (si ya está abierta, solo trae la ventana al frente).
- Lista de productos con scroll V/H, columna de selección (checkbox simulado ✓), doble click agrega al carrito.
- Panel derecho amplio: Detalle + Carrito + Totales con **Descuento** (porcentaje o valor) e **IVA** opcional.
- Lógica de venta sólida: valida stock, descuenta, registra en `ventas` y `movimientos_stock`.
- Visual limpio, tamaños cómodos, sin columna de Proveedor (pedido del usuario).

Requisitos:
- `database/db.py` con `get_connection()` (como el que pasaste).
- Tablas: `productos`, `categorias`, `ventas`, `movimientos_stock` compatibles con tu esquema.

Nota: No tocamos el esquema. Guardamos el `total` final ya con descuento/IVA en `ventas.total`.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Any, Dict, List
from datetime import datetime
import sqlite3

# ==========================
# BD
# ==========================
try:
    from database.db import get_connection
except Exception as e:
    raise RuntimeError("No se pudo importar database.db.get_connection. Verifica rutas del proyecto.") from e


# ==========================
# Columnas de la grilla
# ==========================
COLUMNS: List[str] = [
    "sel",          # checkbox simulado
    "id",
    "nombre",
    "sku",
    "stock",
    "precio_venta",
    "seccion",
    "categoria",
]

COLUMN_HEADERS: Dict[str, str] = {
    "sel": "✔",
    "id": "ID",
    "nombre": "Nombre",
    "sku": "SKU",
    "stock": "Stock",
    "precio_venta": "P. Venta",
    "seccion": "Sección",
    "categoria": "Categoría",
}

COLUMN_WIDTHS: Dict[str, int] = {
    "sel": 48,
    "id": 60,
    "nombre": 280,
    "sku": 120,
    "stock": 90,
    "precio_venta": 120,
    "seccion": 140,
    "categoria": 160,
}

# ==========================
# Utils
# ==========================

def money(n: Any) -> str:
    try:
        return f"{float(n):.2f}"
    except Exception:
        return "0.00"


def now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==========================
# Vista
# ==========================
class SalesView:
    COLS = COLUMNS

    def __init__(self, owner: Optional[tk.Misc] = None):
        self.owner = owner
        self.root = tk.Toplevel(owner) if owner is not None else tk.Tk()
        self.root.title("Ventas")
        self.root.geometry("1900x800")
        self.root.minsize(1150, 720)
        self.root.configure(bg="#f6f7fb")
        if owner is not None:
            self.root.transient(owner)
            try:
                self.root.grab_set()  # experiencia modal suave
            except Exception:
                pass

        # Estado
        self._rows: List[Dict[str, Any]] = []
        self._by_id: Dict[int, Dict[str, Any]] = {}
        self._selected_ids: Dict[int, bool] = {}
        self._cart: Dict[int, Dict[str, Any]] = {}  # {id: {id,nombre,precio,cantidad}}

        # Filtros
        self.filtro_texto_var = tk.StringVar(value="")
        self.filtro_existencia_var = tk.BooleanVar(value=False)
        self.filtro_seccion_var = tk.StringVar(value="Todas")
        self.filtro_categoria_var = tk.StringVar(value="Todas")

        # Totales / Venta
        self.cliente_var = tk.StringVar(value="Consumidor Final")
        self.desc_mode_var = tk.StringVar(value="none")   # none | pct | abs
        self.desc_value_var = tk.DoubleVar(value=0.0)
        self.apply_iva_var = tk.BooleanVar(value=False)
        self.iva_percent_var = tk.DoubleVar(value=15.0)    # opcional

        self.subtotal_var = tk.StringVar(value="0.00")
        self.descuento_var = tk.StringVar(value="0.00")
        self.iva_var = tk.StringVar(value="0.00")
        self.total_var = tk.StringVar(value="0.00")

        self._init_style()
        self._build_ui()
        self._load_filters_sources()
        self.aplicar_filtro()

        # Focus inicial
        self.root.after(120, lambda: self.txt_buscar.focus_set())

        # Cierre controlado
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Destroy>", self._on_destroy)

    # ----------------------
    # Estilos
    # ----------------------
    def _init_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Primary.TButton", padding=(12, 8), background="#2563eb", foreground="#fff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])

        style.configure("Danger.TButton", padding=(12, 8), background="#ef4444", foreground="#fff")
        style.map("Danger.TButton", background=[("active", "#dc2626")])

        style.configure("Secondary.TButton", padding=(10, 6))
        style.configure("Panel.TLabelframe", background="#ffffff")
        style.configure("Panel.TLabelframe.Label", font=("Segoe UI", 11, "bold"))

        style.configure("Big.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Total.TLabel", font=("Segoe UI", 18, "bold"))

    # ----------------------
    # UI
    # ----------------------
    def _build_ui(self):
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Izquierda: filtros + lista
        left = ttk.Frame(paned)
        paned.add(left, weight=3)
        self._build_filters(left)
        self._build_list(left)

        # Derecha: detalle + carrito + totales
        right = ttk.Panedwindow(paned, orient="vertical")
        paned.add(right, weight=2)

        detail_frame = ttk.Labelframe(right, text="Detalle del producto", style="Panel.TLabelframe")
        right.add(detail_frame, weight=1)
        self._build_detail(detail_frame)

        cart_frame = ttk.Labelframe(right, text="Carrito / Acciones", style="Panel.TLabelframe")
        right.add(cart_frame, weight=2)
        self._build_cart(cart_frame)

    # Filtros
    def _build_filters(self, parent: tk.Misc):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=6, pady=(0, 8))

        ttk.Label(bar, text="Buscar:").pack(side="left")
        self.txt_buscar = ttk.Entry(bar, textvariable=self.filtro_texto_var, width=30)
        self.txt_buscar.pack(side="left", padx=(6, 14))
        self.txt_buscar.bind("<Return>", lambda e: self.aplicar_filtro())

        ttk.Label(bar, text="Sección:").pack(side="left")
        self.cbo_seccion = ttk.Combobox(bar, textvariable=self.filtro_seccion_var, width=18, state="readonly")
        self.cbo_seccion.pack(side="left", padx=(6, 14))

        ttk.Label(bar, text="Categoría:").pack(side="left")
        self.cbo_categoria = ttk.Combobox(bar, textvariable=self.filtro_categoria_var, width=18, state="readonly")
        self.cbo_categoria.pack(side="left", padx=(6, 14))

        self.chk_exist = ttk.Checkbutton(bar, variable=self.filtro_existencia_var, text="Solo con stock")
        self.chk_exist.pack(side="left", padx=(6, 14))

        ttk.Button(bar, text="Aplicar", style="Primary.TButton", command=self.aplicar_filtro).pack(side="left")
        ttk.Button(bar, text="Limpiar", style="Secondary.TButton", command=self._clear_filters).pack(side="left", padx=(8, 0))

    # Lista de productos
    def _build_list(self, parent: tk.Misc):
        wrap = ttk.Frame(parent)
        wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.tree = ttk.Treeview(wrap, columns=self.COLS, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        for col in self.COLS:
            self.tree.heading(col, text=COLUMN_HEADERS[col], anchor="w")
            self.tree.column(col, width=COLUMN_WIDTHS[col], stretch=(col in {"nombre", "categoria"}))

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-1>", self._on_tree_click_toggle_checkbox)

    # Detalle
    def _build_detail(self, parent: tk.Misc):
        grid = ttk.Frame(parent)
        grid.pack(fill="both", expand=True, padx=10, pady=10)
        grid.columnconfigure(1, weight=1)

        self.var_det_id = tk.StringVar()
        self.var_det_nombre = tk.StringVar()
        self.var_det_sku = tk.StringVar()
        self.var_det_seccion = tk.StringVar()
        self.var_det_categoria = tk.StringVar()
        self.var_det_stock = tk.StringVar()
        self.var_det_precio = tk.StringVar()

        r = 0
        ttk.Label(grid, text="ID:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_id).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Nombre:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_nombre).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="SKU:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_sku).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Sección:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_seccion).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Categoría:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_categoria).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Stock:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_stock).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(grid, text="Precio venta:").grid(row=r, column=0, sticky="e", padx=6, pady=4)
        ttk.Label(grid, textvariable=self.var_det_precio).grid(row=r, column=1, sticky="w")

        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="Agregar al carrito (Enter)", style="Primary.TButton", command=self._detail_add_to_cart).pack(side="left")
        ttk.Button(btns, text="+1", command=lambda: self._detail_add_to_cart(1)).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="+5", command=lambda: self._detail_add_to_cart(5)).pack(side="left", padx=(4, 0))
        ttk.Button(btns, text="+10", command=lambda: self._detail_add_to_cart(10)).pack(side="left", padx=(4, 0))

        # Bind solo mientras la ventana viva
        self.root.bind("<Return>", lambda e: self._detail_add_to_cart())

    # Carrito + totales
    def _build_cart(self, parent: tk.Misc):
        top = ttk.Frame(parent)
        top.pack(fill="both", expand=True, padx=10, pady=10)
        top.rowconfigure(0, weight=1)
        top.columnconfigure(0, weight=1)

        cols = ["id", "nombre", "cant", "precio", "subtotal"]
        self.cart = ttk.Treeview(top, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", "ID", 60),
            ("nombre", "Producto", 320),
            ("cant", "Cant.", 90),
            ("precio", "P. U.", 110),
            ("subtotal", "Subtotal", 130),
        ]:
            self.cart.heading(c, text=h, anchor="w")
            self.cart.column(c, width=w, stretch=(c == "nombre"))

        vsb = ttk.Scrollbar(top, orient="vertical", command=self.cart.yview)
        self.cart.configure(yscroll=vsb.set)
        self.cart.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        actions = ttk.Frame(parent)
        actions.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(actions, text="Quitar", style="Danger.TButton", command=self._cart_remove_selected).pack(side="left")
        ttk.Button(actions, text="Vaciar", command=self._cart_clear).pack(side="left", padx=(6, 14))
        ttk.Button(actions, text="+", command=lambda: self._cart_incdec(+1)).pack(side="left")
        ttk.Button(actions, text="-", command=lambda: self._cart_incdec(-1)).pack(side="left", padx=(6, 0))

        ttk.Label(actions, text="Cliente:").pack(side="left", padx=(18, 6))
        ttk.Entry(actions, textvariable=self.cliente_var, width=28).pack(side="left")

        ttk.Button(actions, text="Registrar venta", style="Primary.TButton", command=self._register_sale).pack(side="right")

        totals = ttk.Frame(parent)
        totals.pack(fill="x", padx=10, pady=(0, 10))

        # Descuento
        box_desc = ttk.Labelframe(totals, text="Descuento", padding=8)
        box_desc.pack(side="left", padx=(0, 12))
        rb_none = ttk.Radiobutton(box_desc, text="Sin descuento", value="none", variable=self.desc_mode_var, command=self._recalc_totals)
        rb_pct = ttk.Radiobutton(box_desc, text="%", value="pct", variable=self.desc_mode_var, command=self._recalc_totals)
        rb_abs = ttk.Radiobutton(box_desc, text="$", value="abs", variable=self.desc_mode_var, command=self._recalc_totals)
        rb_none.grid(row=0, column=0, sticky="w")
        rb_pct.grid(row=0, column=1, sticky="w")
        rb_abs.grid(row=0, column=2, sticky="w")
        spn_desc = ttk.Spinbox(box_desc, from_=0.0, to=1_000_000.0, increment=0.5, textvariable=self.desc_value_var, width=10, command=self._recalc_totals)
        spn_desc.grid(row=0, column=3, padx=(6, 0))
        for w in (spn_desc,):
            w.bind("<KeyRelease>", lambda e: self._recalc_totals())

        # IVA
        box_tax = ttk.Labelframe(totals, text="IVA", padding=8)
        box_tax.pack(side="left", padx=(0, 12))
        chk = ttk.Checkbutton(box_tax, text="Aplicar", variable=self.apply_iva_var, command=self._recalc_totals)
        chk.grid(row=0, column=0, sticky="w")
        ttk.Label(box_tax, text="%:").grid(row=0, column=1, padx=(8, 4))
        spn_iva = ttk.Spinbox(box_tax, from_=0.0, to=100.0, increment=0.5, textvariable=self.iva_percent_var, width=6, command=self._recalc_totals)
        spn_iva.grid(row=0, column=2)
        for w in (spn_iva,):
            w.bind("<KeyRelease>", lambda e: self._recalc_totals())

        # Resumen
        box_sum = ttk.Labelframe(totals, text="Resumen", padding=8)
        box_sum.pack(side="right", fill="x", expand=True)

        def row(parent, r, label, var, style=None):
            ttk.Label(parent, text=label).grid(row=r, column=0, sticky="e", padx=(0, 8))
            ttk.Label(parent, textvariable=var, style=style or "").grid(row=r, column=1, sticky="w")

        row(box_sum, 0, "Subtotal:", self.subtotal_var, "Big.TLabel")
        row(box_sum, 1, "Descuento:", self.descuento_var)
        row(box_sum, 2, "IVA:", self.iva_var)
        row(box_sum, 3, "Total:", self.total_var, "Total.TLabel")

    # ==========================
    # Datos
    # ==========================
    def _load_filters_sources(self):
        try:
            conn = get_connection()
            cur = conn.cursor()

            # Secciones
            cur.execute("SELECT DISTINCT COALESCE(NULLIF(TRIM(seccion), ''), 'Sin sección') as s FROM productos ORDER BY 1")
            secciones = [r[0] for r in cur.fetchall()] or ["Sin sección"]
            secciones = ["Todas"] + secciones
            self.cbo_seccion["values"] = secciones
            if self.filtro_seccion_var.get() not in secciones:
                self.filtro_seccion_var.set("Todas")

            # Categorías
            cur.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
            cats = cur.fetchall()
            self._categorias_idx: Dict[str, Optional[int]] = {"Todas": None}
            for cid, nom in cats:
                self._categorias_idx[str(nom)] = int(cid)
            self.cbo_categoria["values"] = list(self._categorias_idx.keys())
            if self.filtro_categoria_var.get() not in self._categorias_idx:
                self.filtro_categoria_var.set("Todas")
        except Exception as e:
            messagebox.showerror("Filtros", f"No se pudo cargar filtros:\n{e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def aplicar_filtro(self):
        try:
            conn = get_connection()
            cur = conn.cursor()

            q = [
                "SELECT p.id, p.nombre, p.sku, p.stock, p.precio_venta,",
                "       COALESCE(NULLIF(TRIM(p.seccion), ''), 'Sin sección') as seccion,",
                "       COALESCE(c.nombre, 'Sin categoría') as categoria",
                "FROM productos p",
                "LEFT JOIN categorias c ON p.categoria_id = c.id",
                "WHERE 1=1",
            ]
            params: List[Any] = []

            txt = self.filtro_texto_var.get().strip()
            if txt:
                q.append("AND (p.nombre LIKE ? OR p.sku LIKE ?)")
                like = f"%{txt}%"
                params.extend([like, like])

            sec = self.filtro_seccion_var.get()
            if sec and sec not in ("Todas",):
                if sec == "Sin sección":
                    q.append("AND (p.seccion IS NULL OR TRIM(p.seccion) = '')")
                else:
                    q.append("AND p.seccion = ?")
                    params.append(sec)

            cat_nom = self.filtro_categoria_var.get()
            if cat_nom and cat_nom != "Todas":
                cat_id = self._categorias_idx.get(cat_nom)
                if cat_id is not None:
                    q.append("AND p.categoria_id = ?")
                    params.append(cat_id)

            if self.filtro_existencia_var.get():
                q.append("AND p.stock > 0")

            q.append("ORDER BY p.nombre COLLATE NOCASE")
            sql = "\n".join(q)
            cur.execute(sql, params)
            rows = cur.fetchall()

            self._rows.clear()
            self._by_id.clear()
            self._selected_ids.clear()

            for r in rows:
                d = {
                    "id": int(r[0]),
                    "nombre": r[1] or "",
                    "sku": r[2] or "",
                    "stock": int(r[3] or 0),
                    "precio_venta": float(r[4] or 0.0),
                    "seccion": r[5] or "Sin sección",
                    "categoria": r[6] or "Sin categoría",
                }
                self._rows.append(d)
                self._by_id[d["id"]] = d

            self._refresh_tree()
            self._update_detail_from_selection()
        except Exception as e:
            messagebox.showerror("Productos", f"No se pudieron cargar los productos:\n{e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _clear_filters(self):
        self.filtro_texto_var.set("")
        self.filtro_existencia_var.set(False)
        self.filtro_seccion_var.set("Todas")
        self.filtro_categoria_var.set("Todas")
        self.aplicar_filtro()

    # ==========================
    # Grilla
    # ==========================
    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for d in self._rows:
            sel = "✓" if self._selected_ids.get(d["id"]) else ""
            values = [
                sel,
                d["id"],
                d["nombre"],
                d["sku"],
                d["stock"],
                money(d["precio_venta"]),
                d["seccion"],
                d["categoria"],
            ]
            self.tree.insert("", "end", iid=str(d["id"]), values=values)

    def _on_tree_select(self, _=None):
        self._update_detail_from_selection()

    def _on_tree_click_toggle_checkbox(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)  # '#1' = primera col
        if col != "#1":
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        pid = int(row_id)
        self._selected_ids[pid] = not self._selected_ids.get(pid, False)
        self._refresh_tree()

    def _on_tree_double_click(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        pid = int(sel[0])
        self._cart_add(pid, 1)

    def _update_detail_from_selection(self):
        sel = self.tree.selection()
        if not sel:
            for v in (self.var_det_id, self.var_det_nombre, self.var_det_sku, self.var_det_seccion, self.var_det_categoria, self.var_det_stock, self.var_det_precio):
                v.set("")
            return
        pid = int(sel[0])
        d = self._by_id.get(pid)
        if not d:
            return
        self.var_det_id.set(str(d["id"]))
        self.var_det_nombre.set(d["nombre"])
        self.var_det_sku.set(d["sku"])
        self.var_det_seccion.set(d["seccion"])
        self.var_det_categoria.set(d["categoria"])
        self.var_det_stock.set(str(d["stock"]))
        self.var_det_precio.set(money(d["precio_venta"]))

    # ==========================
    # Detalle → carrito
    # ==========================
    def _detail_add_to_cart(self, delta: int = 1):
        try:
            pid = int(self.var_det_id.get())
        except Exception:
            return
        self._cart_add(pid, delta)

    # ==========================
    # Carrito
    # ==========================
    def _cart_add(self, producto_id: int, cantidad: int = 1):
        d = self._by_id.get(producto_id)
        if not d:
            return
        if d["stock"] <= 0 and cantidad > 0:
            messagebox.showwarning("Stock", f"El producto '{d['nombre']}' no tiene stock disponible.")
            return

        item = self._cart.get(producto_id)
        nueva = (item["cantidad"] if item else 0) + cantidad
        if nueva <= 0:
            self._cart.pop(producto_id, None)
        else:
            if nueva > d["stock"]:
                nueva = d["stock"]
            self._cart[producto_id] = {
                "id": producto_id,
                "nombre": d["nombre"],
                "precio": float(d["precio_venta"] or 0),
                "cantidad": int(nueva),
            }
        self._cart_refresh()

    def _cart_remove_selected(self):
        sel = self.cart.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            pid = int(self.cart.set(iid, "id"))
        except Exception:
            return
        self._cart.pop(pid, None)
        self._cart_refresh()

    def _cart_clear(self):
        if not self._cart:
            return
        if messagebox.askyesno("Vaciar", "¿Vaciar todo el carrito?"):
            self._cart.clear()
            self._cart_refresh()

    def _cart_incdec(self, delta: int):
        sel = self.cart.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            pid = int(self.cart.set(iid, "id"))
        except Exception:
            return
        self._cart_add(pid, delta)

    def _cart_refresh(self):
        self.cart.delete(*self.cart.get_children())
        for item in self._cart.values():
            subtotal = item["cantidad"] * item["precio"]
            self.cart.insert("", "end", values=[
                item["id"],
                item["nombre"],
                item["cantidad"],
                money(item["precio"]),
                money(subtotal),
            ])
        self._recalc_totals()

    # ==========================
    # Totales (desc + IVA)
    # ==========================
    def _recalc_totals(self):
        # Subtotal del carrito
        subtotal = 0.0
        for item in self._cart.values():
            subtotal += item["cantidad"] * item["precio"]

        # Descuento
        d_mode = self.desc_mode_var.get()
        d_val = float(self.desc_value_var.get() or 0)
        descuento = 0.0
        if d_mode == "pct":
            descuento = max(0.0, min(100.0, d_val)) * subtotal / 100.0
        elif d_mode == "abs":
            descuento = max(0.0, min(subtotal, d_val))

        base = max(0.0, subtotal - descuento)

        # IVA
        iva = 0.0
        if self.apply_iva_var.get():
            iva_pct = max(0.0, min(100.0, float(self.iva_percent_var.get() or 0)))
            iva = base * (iva_pct / 100.0)

        total = base + iva

        self.subtotal_var.set(money(subtotal))
        self.descuento_var.set(f"-{money(descuento)}")
        self.iva_var.set(money(iva))
        self.total_var.set(money(total))

    # ==========================
    # Registrar venta
    # ==========================
    def _register_sale(self):
        if not self._cart:
            messagebox.showinfo("Venta", "El carrito está vacío.")
            return

        cliente = self.cliente_var.get().strip() or "Consumidor Final"
        fecha = now_date()

        # Calcular totales finales por si no están frescos
        self._recalc_totals()
        try:
            total_final = float(self.total_var.get())
        except Exception:
            total_final = 0.0

        try:
            conn = get_connection()
            cur = conn.cursor()

            # Validación de stock en BD
            for pid, item in self._cart.items():
                cur.execute("SELECT stock, nombre FROM productos WHERE id=?", (pid,))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"Producto id={pid} no existe.")
                stock_actual = int(row[0] or 0)
                nombre = row[1]
                if item["cantidad"] > stock_actual:
                    raise RuntimeError(f"Stock insuficiente para '{nombre}'. Disponible: {stock_actual}")

            # Registrar cada ítem como una línea de venta (manteniendo tu esquema)
            for pid, item in self._cart.items():
                line_total = item["cantidad"] * item["precio"]
                # Proporción del total_final (por si hubo desc/IVA) —
                # guardamos el total de la línea sin prorratear para mantenerlo simple y
                # el total_final queda como referencia en la última línea (o podríamos ignorarlo).
                cur.execute(
                    "INSERT INTO ventas (producto_id, cantidad, total, fecha, cliente) VALUES (?,?,?,?,?)",
                    (pid, item["cantidad"], line_total, fecha, cliente),
                )
                # Movimiento de stock (salida)
                cur.execute(
                    "INSERT INTO movimientos_stock (producto_id, cantidad, tipo, motivo, fecha) VALUES (?,?,?,?,?)",
                    (pid, item["cantidad"], "salida", "venta", fecha),
                )
                # Descontar stock
                cur.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (item["cantidad"], pid))

            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            messagebox.showerror("Venta", f"No se pudo registrar la venta:\n{e}")
            return
        finally:
            try:
                conn.close()
            except Exception:
                pass

        messagebox.showinfo("Venta", f"Venta registrada. Total: ${money(total_final)}")
        self._cart.clear()
        self._cart_refresh()
        self.aplicar_filtro()  # refresca stocks

    # ==========================
    # Cierre / Limpieza
    # ==========================
    def _on_close(self):
        try:
            if self.owner is not None:
                try:
                    self.root.grab_release()
                except Exception:
                    pass
            self.root.destroy()
        except Exception:
            pass

    def _on_destroy(self, event):
        # cuando la ventana principal de la vista muere, liberar singleton
        if event.widget is self.root:
            try:
                set_instance(None)
            except Exception:
                pass

    # Debug helper (opcional)
    def status(self, text: str):
        print(f"[Ventas] {text}")


# ==========================
# Singleton de ventana
# ==========================
_instance: Optional[SalesView] = None

def get_instance() -> Optional[SalesView]:
    global _instance
    return _instance


def set_instance(v: Optional[SalesView]):
    global _instance
    _instance = v


def ventana_ventas(owner: Optional[tk.Misc] = None):
    inst = get_instance()
    if inst is not None:
        try:
            if inst.root.winfo_exists():
                inst.root.deiconify()
                inst.root.lift()
                inst.root.focus_force()
                return
        except Exception:
            pass
    inst = SalesView(owner)
    set_instance(inst)


if __name__ == "__main__":
    ventana_ventas()
