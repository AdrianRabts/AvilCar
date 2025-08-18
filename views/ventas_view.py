# views/ventas_view.py
# -*- coding: utf-8 -*-

import platform
import tkinter as tk
import sqlite3

import datetime as _dt
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, Optional, Tuple, Union, List

from models.producto import obtener_productos, obtener_producto_por_codigo, obtener_producto_por_sku
from models.ventas import registrar_venta

UMBRAL_STOCK_BAJO = 5
DEBOUNCE_MS = 220
ROW_HEIGHT = 28

COLOR_BG_OK = "#F6FFF6"
COLOR_BG_LOW = "#FFF6F6"
COLOR_ROW_ALT = "#FAFAFA"
COLOR_TXT_OK = "#1B5E20"
COLOR_TXT_LOW = "#B71C1C"
COLOR_BADGE_NEUTRO = "#9e9e9e"
COLOR_BADGE_OK_BG = "#E8F5E9"
COLOR_BADGE_LOW_BG = "#FFEBEE"
COLOR_BADGE_OK_FG = "#2E7D32"
COLOR_BADGE_LOW_FG = "#C62828"
COLOR_HINT = "#607D8B"

COLUMNS = ("ID", "Código", "Nombre", "Precio Venta", "Precio Costo", "Stock", "Sección", "Categoría")


def _get(row: Union[sqlite3.Row, Tuple, list, Dict[str, Any]], key: str, idx: Optional[int] = None, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        if hasattr(row, "keys") and key in row.keys():
            return row[key]
    except Exception:
        pass
    if idx is not None:
        try:
            return row[idx]
        except Exception:
            return default
    return default


def _to_float(val, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return default
        if isinstance(val, str):
            v = val.replace("$", "").replace(",", "").strip()
            if not v:
                return default
            return float(v)
        return float(val)
    except Exception:
        return default


def _to_int(val, default: int = 0) -> int:
    try:
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return default
        if isinstance(val, str):
            v = val.replace(",", "").strip()
            if not v:
                return default
            return int(float(v))
        return int(val)
    except Exception:
        return default


def _clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))


def format_currency(val: Optional[float]) -> str:
    if val is None:
        return "-"
    try:
        return f"${val:,.2f}"
    except Exception:
        return "-"


def parse_producto(row: Union[sqlite3.Row, Dict[str, Any], Tuple, list]) -> Dict[str, Any]:
    return {
        "id": _get(row, "id"),
        "codigo": _get(row, "codigo"),
        "nombre": (_get(row, "nombre") or "").strip(),
        "precio_venta": _to_float(_get(row, "precio_venta", default=None), None),
        "precio_costo": _to_float(_get(row, "precio_costo", default=None), None),
        "stock": _to_int(_get(row, "stock", default=0), 0),
        "seccion": (_get(row, "seccion") or "Ninguno"),
        "categoria": (_get(row, "categoria") or ""),
    }


def product_key(info: Dict[str, Any]) -> str:
    if info.get("id") not in (None, ""):
        return f"id:{info['id']}"
    return f"cod:{info.get('codigo')}"


def is_low_stock(info: Dict[str, Any], umbral: int = UMBRAL_STOCK_BAJO) -> bool:
    return _to_int(info.get("stock", 0), 0) <= umbral


def find_producto_en_bd(codigo_o_id: Any):
    try:
        prod = obtener_producto_por_codigo(str(codigo_o_id))
        if prod:
            return prod
    except Exception:
        pass
    try:
        prod = obtener_producto_por_sku(str(codigo_o_id))
        if prod:
            return prod
    except Exception:
        pass
    try:
        pid = int(str(codigo_o_id))
        prod = obtener_producto_por_codigo(str(pid))
        if prod:
            return prod
    except Exception:
        pass
    return None


class SalesView:
    COLS = COLUMNS

    def __init__(self, owner: Optional[tk.Misc] = None):
        self.owner = owner
        self.win = tk.Toplevel(owner) if owner else tk.Tk()
        if owner:
            self.win.transient(owner)
            self.win.grab_set()
        self.win.title("Inventario - Ventas")
        self.win.geometry("1366x820")
        self.win.minsize(1100, 700)

        self._init_scaling()
        self._init_styles()

        self.productos_all: List[Union[sqlite3.Row, Dict[str, Any]]] = []
        self.visible_by_iid: Dict[str, Dict[str, Any]] = {}
        self.selected_by_key: Dict[str, Dict[str, Any]] = {}
        self.sort_state: Dict[str, bool] = {}
        self.search_job: Optional[str] = None
        self.last_focus_key: Optional[str] = None

        self.filtro_texto_var = tk.StringVar(value="")
        self.filtro_existencia_var = tk.BooleanVar(value=False)
        self.filtro_seccion_var = tk.StringVar(value="Todas")
        self.filtro_categoria_var = tk.StringVar(value="Todas")

        self.descuento_var = tk.StringVar(value="0")
        self.impuesto_var = tk.StringVar(value="0")
        self.metodo_pago_var = tk.StringVar(value="Efectivo")
        self.recibido_var = tk.StringVar(value="0")
        self.cambio_var = tk.StringVar(value="$0.00")
        self.codigo_rapido_var = tk.StringVar(value="")

        self._build_ui()
        self.cargar_productos()
        self.entry_buscar.focus_set()

        if not self.owner:
            self.win.mainloop()

    def _init_scaling(self):
        try:
            if platform.system() == "Windows":
                current = float(self.win.tk.call("tk", "scaling"))
                if current < 1.25:
                    self.win.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

    
    def _init_styles(self):
        style = ttk.Style(self.win)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=ROW_HEIGHT, font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 6), font=("Segoe UI", 10))
        style.configure("Accent.TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#2e7d32")], foreground=[("active", "white")])
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Muted.TLabel", foreground="#666")
        style.configure("Hint.TLabel", foreground=COLOR_HINT)

    def _build_ui(self):
        header = ttk.Frame(self.win, padding=(12, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Panel de ventas", style="Header.TLabel").pack(side="left")

        filters = ttk.Frame(header)
        filters.pack(side="right")

        ttk.Label(filters, text="Buscar:").pack(side="left")
        self.entry_buscar = ttk.Entry(filters, textvariable=self.filtro_texto_var, width=30)
        self.entry_buscar.pack(side="left", padx=(6, 8))

        self.chk_exist = ttk.Checkbutton(filters, text="Solo con stock", variable=self.filtro_existencia_var, command=self.aplicar_filtro)
        self.chk_exist.pack(side="left", padx=(0, 10))

        self.cbo_seccion = ttk.Combobox(filters, textvariable=self.filtro_seccion_var, values=["Todas"], state="readonly", width=12)
        self.cbo_seccion.pack(side="left", padx=(0, 6))
        self.cbo_categoria = ttk.Combobox(filters, textvariable=self.filtro_categoria_var, values=["Todas"], state="readonly", width=16)
        self.cbo_categoria.pack(side="left", padx=(0, 10))

        ttk.Button(filters, text="Limpiar", command=self._clear_filters).pack(side="left", padx=(0, 6))

        quick = ttk.Frame(self.win, padding=(12, 0))
        quick.pack(fill="x")
        ttk.Label(quick, text="Código rápido:").pack(side="left")
        self.entry_codigo_rapido = ttk.Entry(quick, textvariable=self.codigo_rapido_var, width=24)
        self.entry_codigo_rapido.pack(side="left", padx=(6, 6))
        ttk.Button(quick, text="Agregar", command=self._agregar_por_codigo_rapido).pack(side="left", padx=(0, 6))
        ttk.Label(quick, text="(Escanea o escribe un código y presiona Enter)", style="Hint.TLabel").pack(side="left")

        body = ttk.Frame(self.win)
        body.pack(fill="both", expand=True, padx=12, pady=6)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        tabla_frame = ttk.LabelFrame(body, text="Productos", padding=6)
        tabla_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tabla_frame.rowconfigure(0, weight=1)
        tabla_frame.columnconfigure(0, weight=1)

        self.tv = ttk.Treeview(tabla_frame, columns=self.COLS, show="headings", height=20)
        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(tabla_frame, orient="vertical", command=self.tv.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tv.configure(yscroll=vsb.set)

        self.tv.tag_configure("ok", background=COLOR_BG_OK)
        self.tv.tag_configure("low", background=COLOR_BG_LOW)
        self.tv.tag_configure("alt", background=COLOR_ROW_ALT)

        self.tv.column("ID", width=70, anchor="center")
        self.tv.column("Código", width=140, anchor="w")
        self.tv.column("Nombre", width=440, anchor="w")
        self.tv.column("Precio Venta", width=140, anchor="e")
        self.tv.column("Precio Costo", width=140, anchor="e")
        self.tv.column("Stock", width=90, anchor="e")
        self.tv.column("Sección", width=160, anchor="w")
        self.tv.column("Categoría", width=200, anchor="w")

        for c in self.COLS:
            self.tv.heading(c, text=c, command=lambda cc=c: self.ordenar_por(cc))

        self.lbl_empty = ttk.Label(tabla_frame, text="Sin resultados", style="Muted.TLabel")

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        card = ttk.LabelFrame(right, text="Detalle", padding=10)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        card.columnconfigure(1, weight=1)

        ttk.Label(card, text="Nombre:").grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_p_nombre = ttk.Label(card, text="—", font=("Segoe UI", 11, "bold"))
        self.lbl_p_nombre.grid(row=0, column=1, sticky="w")

        ttk.Label(card, text="Código:").grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_p_codigo = ttk.Label(card, text="—")
        self.lbl_p_codigo.grid(row=1, column=1, sticky="w")

        ttk.Label(card, text="ID:").grid(row=2, column=0, sticky="w", pady=2)
        self.lbl_p_id = ttk.Label(card, text="—")
        self.lbl_p_id.grid(row=2, column=1, sticky="w")

        ttk.Label(card, text="Stock:").grid(row=3, column=0, sticky="w", pady=2)
        self.stock_badge = tk.Label(card, text="—", bg=COLOR_BADGE_NEUTRO, fg="white", padx=10, pady=3)
        self.stock_badge.grid(row=3, column=1, sticky="w")

        ttk.Label(card, text="Precio venta:").grid(row=4, column=0, sticky="w", pady=2)
        self.lbl_p_precio_v = ttk.Label(card, text="—")
        self.lbl_p_precio_v.grid(row=4, column=1, sticky="w")

        ttk.Label(card, text="Precio costo:").grid(row=5, column=0, sticky="w", pady=2)
        self.lbl_p_precio_c = ttk.Label(card, text="—")
        self.lbl_p_precio_c.grid(row=5, column=1, sticky="w")

        sel_frame = ttk.LabelFrame(right, text="Carrito", padding=8)
        sel_frame.grid(row=1, column=0, sticky="nsew")
        sel_frame.rowconfigure(0, weight=1)
        sel_frame.columnconfigure(0, weight=1)

        self.sel_canvas = tk.Canvas(sel_frame, highlightthickness=0)
        self.sel_vsb = ttk.Scrollbar(sel_frame, orient="vertical", command=self.sel_canvas.yview)
        self.sel_inner = ttk.Frame(self.sel_canvas)
        self.sel_window_id = self.sel_canvas.create_window((0, 0), window=self.sel_inner, anchor="nw")
        self.sel_canvas.configure(yscrollcommand=self.sel_vsb.set)
        self.sel_canvas.grid(row=0, column=0, sticky="nsew")
        self.sel_vsb.grid(row=0, column=1, sticky="ns")

        actions = ttk.LabelFrame(right, text="Acciones de venta", padding=10)
        actions.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(3, weight=1)

        ttk.Label(actions, text="Cliente (obligatorio):").grid(row=0, column=0, sticky="w", pady=(6, 0))
        self.entry_cliente = ttk.Entry(actions)
        self.entry_cliente.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(6, 0))

        ttk.Label(actions, text="Método de pago:").grid(row=0, column=2, sticky="w", pady=(6, 0))
        self.cbo_metodo = ttk.Combobox(actions, textvariable=self.metodo_pago_var, values=["Efectivo", "Tarjeta", "Transferencia", "Mixto"], state="readonly", width=18)
        self.cbo_metodo.grid(row=0, column=3, sticky="w", padx=(6, 0), pady=(6, 0))

        ttk.Label(actions, text="Descuento %:").grid(row=1, column=0, sticky="w")
        self.entry_descuento = ttk.Entry(actions, width=10, textvariable=self.descuento_var, validate="key")
        self.entry_descuento.grid(row=1, column=1, sticky="w", padx=(6, 6))

        ttk.Label(actions, text="Impuesto %:").grid(row=1, column=2, sticky="w")
        self.entry_impuesto = ttk.Entry(actions, width=10, textvariable=self.impuesto_var, validate="key")
        self.entry_impuesto.grid(row=1, column=3, sticky="w", padx=(6, 6))

        ttk.Label(actions, text="Recibido:").grid(row=2, column=0, sticky="w")
        self.entry_recibido = ttk.Entry(actions, width=14, textvariable=self.recibido_var, validate="key")
        self.entry_recibido.grid(row=2, column=1, sticky="w", padx=(6, 6))

        ttk.Label(actions, text="Cambio:").grid(row=2, column=2, sticky="w")
        self.lbl_cambio = ttk.Label(actions, textvariable=self.cambio_var)
        self.lbl_cambio.grid(row=2, column=3, sticky="w")

        self.lbl_resumen_sel = ttk.Label(actions, text="—", style="Muted.TLabel")
        self.lbl_resumen_sel.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.lbl_total_precio = ttk.Label(actions, text="Total: $0.00  (Base: $0.00, Desc: 0%, Imp: 0%)", font=("Segoe UI", 10, "bold"))
        self.lbl_total_precio.grid(row=3, column=1, columnspan=3, sticky="e", pady=(6, 0))

        self.lbl_omitidos = ttk.Label(actions, text="", style="Muted.TLabel")
        self.lbl_omitidos.grid(row=4, column=0, columnspan=4, sticky="w")

        btns = ttk.Frame(actions)
        btns.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)
        btns.columnconfigure(3, weight=1)
        self.btn_vender = ttk.Button(btns, text="Vender (Ctrl+Enter)", style="Accent.TButton", command=self.vender_seleccionados)
        self.btn_vender.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_act_totales = ttk.Button(btns, text="Actualizar totales (F5)", command=self.actualizar_totales)
        self.btn_act_totales.grid(row=0, column=1, sticky="ew", padx=6)
        self.btn_clear_sel = ttk.Button(btns, text="Vaciar carrito (Ctrl+L)", command=self.limpiar_seleccion)
        self.btn_clear_sel.grid(row=0, column=2, sticky="ew", padx=6)
        self.btn_nueva = ttk.Button(btns, text="Nueva venta", command=self._nueva_venta)
        self.btn_nueva.grid(row=0, column=3, sticky="ew", padx=(6, 0))

        statusbar = ttk.Frame(self.win)
        statusbar.pack(fill="x", side="bottom")
        self.lbl_status = ttk.Label(statusbar, text="Listo", anchor="w")
        self.lbl_status.pack(fill="x", padx=10, pady=4)

        self.entry_buscar.bind("<KeyRelease>", self.debounce_filtro)
        self.cbo_seccion.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtro())
        self.cbo_categoria.bind("<<ComboboxSelected>>", lambda e: self.aplicar_filtro())
        self.entry_codigo_rapido.bind("<Return>", lambda e: self._agregar_por_codigo_rapido())

        self.tv.bind("<Double-1>", self.on_tree_double_click)
        self.tv.bind("<Button-3>", self.on_tree_context_menu)
        self.tv.bind("<Return>", self.toggle_selection_current)
        self.tv.bind("<space>", self.toggle_selection_current)
        self.tv.bind("<Escape>", lambda e: self.entry_buscar.focus_set())

        self.sel_inner.bind("<Configure>", self._on_cart_frame_configure)
        self.sel_canvas.bind("<MouseWheel>", self._on_mousewheel_sel)
        self.sel_canvas.bind("<Button-4>", self._on_mousewheel_sel)
        self.sel_canvas.bind("<Button-5>", self._on_mousewheel_sel)

        vnum = (self.win.register(self._validate_number), "%P")
        self.entry_descuento.configure(validatecommand=vnum)
        self.entry_impuesto.configure(validatecommand=vnum)
        self.entry_recibido.configure(validatecommand=vnum)

        self.win.bind("<Control-Return>", self.vender_seleccionados)
        self.win.bind("<Control-l>", lambda e: self.limpiar_seleccion())
        self.win.bind("<Control-f>", lambda e: (self.entry_buscar.focus_set(), self.entry_buscar.select_range(0, tk.END)))
        self.win.bind("<Control-r>", lambda e: self.cargar_productos())
        self.win.bind("<F5>", lambda e: self.actualizar_totales())
        self.win.bind("<F2>", lambda e: self._focus_cart_first_qty())
        self.win.bind("<F1>", lambda e: self._show_help())
        self.win.bind("<Escape>", lambda e: self.win.destroy())

        self.ctx_menu = tk.Menu(self.win, tearoff=0)
        self.ctx_menu.add_command(label="Agregar/Quitar del carrito (Enter)", command=self._ctx_toggle_row)
        self.ctx_menu.add_command(label="Agregar con cantidad...", command=self._ctx_add_with_qty)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Copiar código", command=self._ctx_copy_codigo)
        self.ctx_menu.add_command(label="Copiar ID", command=self._ctx_copy_id)

    def _validate_number(self, proposed: str) -> bool:
        if proposed.strip() == "":
            return True
        try:
            float(proposed.replace(",", "."))
            return True
        except Exception:
            self.win.bell()
            return False

    def status(self, msg: str):
        self.lbl_status.config(text=msg)

    def cargar_productos(self):
        try:
            prods = obtener_productos() or []
            self.productos_all = []
            for p in prods:
                try:
                    _ = p.keys()
                    self.productos_all.append(p)
                except Exception:
                    d = {}
                    try:
                        d["id"] = p[0]
                        d["codigo"] = p[1]
                        d["nombre"] = p[2]
                        d["precio_costo"] = p[3]
                        d["precio_venta"] = p[4]
                        d["stock"] = p[5]
                        d["seccion"] = p[6] if len(p) > 6 else "Ninguno"
                        d["categoria"] = p[7] if len(p) > 7 else ""
                    except Exception:
                        pass
                    self.productos_all.append(d)

            secciones = {"Todas"}
            categorias = {"Todas"}
            for p in self.productos_all:
                info = parse_producto(p)
                secciones.add(info["seccion"] or "Ninguno")
                categorias.add(info["categoria"] or "")
            sec_vals = sorted(secciones, key=lambda x: (x != "Todas", x))
            cat_vals = sorted(categorias, key=lambda x: (x != "Todas", x))
            self.cbo_seccion.configure(values=sec_vals)
            self.cbo_categoria.configure(values=cat_vals)
            if self.filtro_seccion_var.get() not in sec_vals:
                self.filtro_seccion_var.set("Todas")
            if self.filtro_categoria_var.get() not in cat_vals:
                self.filtro_categoria_var.set("Todas")

            self.aplicar_filtro()
        except Exception as e:
            self.productos_all = []
            messagebox.showerror("Productos", f"No se pudieron cargar los productos:\n{e}")
            self.aplicar_filtro()

    def _passes_filters(self, info: Dict[str, Any], token: str) -> bool:
        if token:
            txt = token
            if not (
                txt in str(info["nombre"]).lower()
                or txt in str(info["codigo"]).lower()
                or (info["id"] is not None and txt in str(info["id"]).lower())
                or txt in str(info["seccion"]).lower()
                or txt in str(info["categoria"]).lower()
            ):
                return False
        if self.filtro_existencia_var.get() and _to_int(info["stock"], 0) <= 0:
            return False
        sec = self.filtro_seccion_var.get()
        if sec and sec != "Todas":
            if (info["seccion"] or "Ninguno") != sec:
                return False
        cat = self.filtro_categoria_var.get()
        if cat and cat != "Todas":
            if (info["categoria"] or "") != cat:
                return False
        return True

    def parse_row_display(self, info: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            info["id"],
            info["codigo"],
            info["nombre"],
            format_currency(info["precio_venta"]),
            format_currency(info["precio_costo"]),
            info["stock"],
            info["seccion"] or "Ninguno",
            info["categoria"] or "",
        )

    def _clear_filters(self):
        """Resetea todos los filtros y vuelve a mostrar todos los productos."""
        self.filtro_texto_var.set("")
        self.filtro_existencia_var.set(False)
        self.filtro_seccion_var.set("Todas")
        self.filtro_categoria_var.set("Todas")
        self.aplicar_filtro()
        self.status("Filtros limpiados")


    def aplicar_filtro(self, *_):
        token = self.filtro_texto_var.get().strip().lower()
        for child in self.tv.get_children():
            self.tv.delete(child)
        self.visible_by_iid.clear()

        count = 0
        for idx, p in enumerate(self.productos_all):
            info = parse_producto(p)
            if not self._passes_filters(info, token):
                continue
            tag = "ok" if not is_low_stock(info) else "low"
            tags = (tag, "alt") if idx % 2 == 1 else (tag,)
            iid = self.tv.insert("", "end", values=self.parse_row_display(info), tags=tags)
            self.visible_by_iid[iid] = {"info": info, "key": product_key(info)}
            count += 1

        if count == 0:
            self.lbl_empty.place(relx=0.5, rely=0.5, anchor="center")
            self.status("Sin resultados")
        else:
            self.lbl_empty.place_forget()
            self.status(f"{count} producto(s) encontrados")

        if self.last_focus_key:
            for iid, meta in self.visible_by_iid.items():
                if meta["key"] == self.last_focus_key:
                    self.tv.selection_set(iid)
                    self.tv.focus(iid)
                    self.tv.see(iid)
                    break

        self.actualizar_panel_detalle()
        self.actualizar_panel_seleccion()
        self.actualizar_totales()

    def debounce_filtro(self, *_):
        if self.search_job:
            try:
                self.win.after_cancel(self.search_job)
            except Exception:
                pass
        self.search_job = self.win.after(DEBOUNCE_MS, self.aplicar_filtro)

    def _set_sort_heading(self, col: str, reverse: bool):
        up = " ▲"
        down = " ▼"
        for c in self.COLS:
            base = c
            if c == col:
                base += down if reverse else up
            self.tv.heading(c, text=base, command=lambda cc=c: self.ordenar_por(cc))

    def ordenar_por(self, col: str):
        reverse = self.sort_state.get(col, False)
        filas = [(self.tv.item(iid, "values"), iid) for iid in self.tv.get_children("")]

        def parse_for_sort(values: Tuple[str, ...]) -> Any:
            mapping = {self.COLS[i]: values[i] for i in range(len(self.COLS))}
            v = mapping[col]
            if col in ("ID", "Stock"):
                return _to_int(v, 0)
            if col in ("Precio Venta", "Precio Costo"):
                return _to_float(v, float("inf"))
            return str(v).lower()

        filas.sort(key=lambda t: parse_for_sort(t[0]), reverse=reverse)
        for i, (_, iid) in enumerate(filas):
            self.tv.move(iid, "", i)

        self.sort_state[col] = not reverse
        self._set_sort_heading(col, reverse)

    def _toggle_by_iid(self, iid: Optional[str], qty: Optional[int] = None):
        if not iid or iid not in self.visible_by_iid:
            return
        meta = self.visible_by_iid[iid]
        info = meta["info"]
        key = meta["key"]
        self.last_focus_key = key

        if key in self.selected_by_key:
            if qty is None:
                self.selected_by_key.pop(key, None)
            else:
                self.selected_by_key[key]["qty"] = max(1, qty)
        else:
            self.selected_by_key[key] = {"info": info, "qty": max(1, qty or 1)}

        self.actualizar_panel_detalle()
        self.actualizar_panel_seleccion()
        self.actualizar_totales()

    def toggle_selection_current(self, event=None):
        cur = self.tv.focus() or (self.tv.selection()[0] if self.tv.selection() else None)
        self._toggle_by_iid(cur)

    def on_tree_double_click(self, event):
        rowid = self.tv.identify_row(event.y)
        if not rowid:
            return
        if (event.state & 0x0001):
            qty = self._prompt_quantity(initial=1)
            if qty is None:
                return
            self._toggle_by_iid(rowid, qty=qty)
        else:
            self._toggle_by_iid(rowid)

    def on_tree_context_menu(self, event):
        try:
            rowid = self.tv.identify_row(event.y)
            if rowid:
                self.tv.selection_set(rowid)
                self.tv.focus(rowid)
            self.ctx_menu.post(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    def _ctx_toggle_row(self):
        cur = self.tv.focus()
        self._toggle_by_iid(cur)

    def _ctx_add_with_qty(self):
        cur = self.tv.focus()
        if not cur:
            return
        qty = self._prompt_quantity(initial=1)
        if qty is None:
            return
        self._toggle_by_iid(cur, qty=qty)

    def _ctx_copy_codigo(self):
        cur = self.tv.focus()
        if cur and cur in self.visible_by_iid:
            info = self.visible_by_iid[cur]["info"]
            self.win.clipboard_clear()
            self.win.clipboard_append(str(info.get("codigo") or ""))
            self.status("Código copiado")

    def _ctx_copy_id(self):
        cur = self.tv.focus()
        if cur and cur in self.visible_by_iid:
            info = self.visible_by_iid[cur]["info"]
            self.win.clipboard_clear()
            self.win.clipboard_append(str(info.get("id") or ""))
            self.status("ID copiado")

    def _prompt_quantity(self, initial: int = 1) -> Optional[int]:
        top = tk.Toplevel(self.win)
        top.title("Cantidad")
        top.transient(self.win)
        top.grab_set()
        ttk.Label(top, text="Cantidad:").grid(row=0, column=0, padx=10, pady=10)
        var = tk.StringVar(value=str(initial))
        ent = ttk.Entry(top, textvariable=var, width=10)
        ent.grid(row=0, column=1, padx=10, pady=10)
        result = {"val": None}

        def ok():
            v = _to_int(var.get(), 0)
            if v <= 0:
                self.win.bell()
                return
            result["val"] = v
            top.destroy()

        def cancel():
            top.destroy()

        btns = ttk.Frame(top)
        btns.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        ttk.Button(btns, text="Aceptar", command=ok).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancelar", command=cancel).pack(side="left", padx=6)

        ent.focus_set()
        ent.select_range(0, tk.END)
        top.bind("<Return>", lambda e: ok())
        top.bind("<Escape>", lambda e: cancel())
        top.wait_window()
        return result["val"]

    def actualizar_panel_detalle(self):
        total_sel = len(self.selected_by_key)
        if total_sel == 0:
            self.lbl_p_nombre.config(text="—")
            self.lbl_p_codigo.config(text="—")
            self.lbl_p_id.config(text="—")
            self.lbl_p_precio_v.config(text="—")
            self.lbl_p_precio_c.config(text="—")
            self.stock_badge.config(text="—", bg=COLOR_BADGE_NEUTRO, fg="white")
            return

        if total_sel == 1:
            key = next(iter(self.selected_by_key.keys()))
            info = self.selected_by_key[key]["info"]
            prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") else info.get("id"))
            fresh = parse_producto(prod_db) if prod_db else info

            self.lbl_p_nombre.config(text=str(fresh.get("nombre") or f"ID {fresh.get('id')}"))
            self.lbl_p_codigo.config(text=str(fresh.get("codigo") or "—"))
            self.lbl_p_id.config(text=str(fresh.get("id") or "—"))
            self.lbl_p_precio_v.config(text=format_currency(fresh.get("precio_venta")))
            self.lbl_p_precio_c.config(text=format_currency(fresh.get("precio_costo")))

            low = is_low_stock(fresh)
            self.stock_badge.config(
                text=f"{_to_int(fresh.get('stock', 0), 0)}",
                bg=COLOR_BADGE_LOW_BG if low else COLOR_BADGE_OK_BG,
                fg=COLOR_BADGE_LOW_FG if low else COLOR_BADGE_OK_FG,
            )
        else:
            total = total_sel
            bajos = 0
            uds = 0
            for _, v in self.selected_by_key.items():
                inf = v["info"]
                if is_low_stock(inf):
                    bajos += 1
                uds += v.get("qty", 1)

            self.lbl_p_nombre.config(text=f"{total} productos seleccionados")
            self.lbl_p_codigo.config(text=f"Unidades: {uds}")
            self.lbl_p_id.config(text=f"Stock bajo: {bajos}")
            self.lbl_p_precio_v.config(text="—")
            self.lbl_p_precio_c.config(text="—")
            self.stock_badge.config(text="—", bg=COLOR_BADGE_NEUTRO, fg="white")

    def _clear_frame(self, f: tk.Misc):
        for w in f.winfo_children():
            w.destroy()

    def _on_cart_frame_configure(self, _event):
        self.sel_canvas.configure(scrollregion=self.sel_canvas.bbox("all"))
        try:
            self.sel_canvas.itemconfig(self.sel_window_id, width=self.sel_canvas.winfo_width())
        except Exception:
            pass

    def _on_mousewheel_sel(self, event):
        if event.delta:
            self.sel_canvas.yview_scroll(int(-event.delta / 120), "units")
        elif getattr(event, "num", None) == 4:
            self.sel_canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.sel_canvas.yview_scroll(1, "units")
        return "break"

    def _focus_cart_first_qty(self):
        for child in self.sel_inner.winfo_children():
            if isinstance(child, ttk.Spinbox):
                child.focus_set()
                child.select_range(0, tk.END)
                break

    def actualizar_panel_seleccion(self):
        self._clear_frame(self.sel_inner)

        if not self.selected_by_key:
            ttk.Label(self.sel_inner, text="Carrito vacío. Doble clic en la tabla o presiona Enter para agregar.", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
            self.btn_vender.state(["disabled"])
            self.btn_clear_sel.state(["disabled"])
            self.btn_act_totales.state(["disabled"])
            return

        self.btn_vender.state(["!disabled"])
        self.btn_clear_sel.state(["!disabled"])
        self.btn_act_totales.state(["!disabled"])

        hdr = ("#", "Código", "Nombre", "Stock", "Precio", "Cant.", "Subtotal", "")
        for c, text in enumerate(hdr):
            lbl = ttk.Label(self.sel_inner, text=text)
            lbl.grid(row=0, column=c, sticky="w" if c in (0, 1, 2) else "e", padx=(0, 4), pady=(0, 4))

        for r, (key, data) in enumerate(list(self.selected_by_key.items()), start=1):
            info = data["info"]
            prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") else info.get("id"))
            fresh = parse_producto(prod_db) if prod_db else info
            info.update(fresh)

            ok = not is_low_stock(fresh)
            color_fg = COLOR_TXT_OK if ok else COLOR_TXT_LOW

            ttk.Label(self.sel_inner, text=str(r)).grid(row=r, column=0, sticky="w")
            ttk.Label(self.sel_inner, text=str(fresh["codigo"])).grid(row=r, column=1, sticky="w")
            ttk.Label(self.sel_inner, text=str(fresh["nombre"])).grid(row=r, column=2, sticky="w")
            ttk.Label(self.sel_inner, text=f"{_to_int(fresh['stock'], 0)}", foreground=color_fg).grid(row=r, column=3, sticky="e")

            ttk.Label(self.sel_inner, text=format_currency(fresh["precio_venta"])).grid(row=r, column=4, sticky="e")

            max_to = max(1, _to_int(fresh["stock"], 0))
            qty_val = _clamp(_to_int(data.get("qty", 1), 1), 1, max_to)
            data["qty"] = int(qty_val)
            qty_var = tk.StringVar(value=str(int(qty_val)))

            sp = ttk.Spinbox(self.sel_inner, from_=1, to=max_to, textvariable=qty_var, width=6, justify="right")
            sp.grid(row=r, column=5, sticky="e", padx=(6, 0))

            pv = fresh.get("precio_venta")
            if pv is None:
                lbl_st = ttk.Label(self.sel_inner, text="Sin precio", foreground="#B00020")
            else:
                lbl_st = ttk.Label(self.sel_inner, text=format_currency(_to_float(pv, 0.0) * _to_int(qty_var.get(), 1)))
            lbl_st.grid(row=r, column=6, sticky="e", padx=(6, 0))

            def make_on_change(k=key, var=qty_var, max_stock=max_to, unit_price=pv, lbl=lbl_st):
                def _on_change(*_):
                    try:
                        val = _to_int(var.get(), 1)
                        val = int(_clamp(val, 1, max_stock))
                        self.selected_by_key[k]["qty"] = val
                        var.set(str(val))
                        if unit_price is None:
                            lbl.config(text="Sin precio", foreground="#B00020")
                        else:
                            lbl.config(text=format_currency(_to_float(unit_price, 0.0) * val), foreground="")
                        self.actualizar_totales()
                    except Exception:
                        self.selected_by_key[k]["qty"] = 1
                        var.set("1")
                        if unit_price is None:
                            lbl.config(text="Sin precio", foreground="#B00020")
                        else:
                            lbl.config(text=format_currency(_to_float(unit_price, 0.0) * 1), foreground="")
                        self.actualizar_totales()
                return _on_change

            qty_var.trace_add("write", make_on_change())

            def make_remove(k=key):
                def _rm():
                    self.selected_by_key.pop(k, None)
                    self.aplicar_filtro()
                    self.actualizar_totales()
                return _rm

            ttk.Button(self.sel_inner, text="Quitar", command=make_remove()).grid(row=r, column=7, sticky="e", padx=(6, 0))

        self.sel_inner.update_idletasks()
        self.sel_canvas.configure(scrollregion=self.sel_canvas.bbox("all"))
        self.actualizar_totales()

    def _leer_descuento_impuesto(self) -> Tuple[float, float]:
        try:
            d = float(self.descuento_var.get() or "0")
            d = _clamp(d, 0.0, 100.0)
        except Exception:
            d = 0.0
        try:
            i = float(self.impuesto_var.get() or "0")
            i = _clamp(i, 0.0, 100.0)
        except Exception:
            i = 0.0
        self.descuento_var.set(f"{d:g}")
        self.impuesto_var.set(f"{i:g}")
        return d, i

    def _leer_recibido(self) -> float:
        try:
            r = float(self.recibido_var.get() or "0")
            if r < 0:
                r = 0
        except Exception:
            r = 0.0
        self.recibido_var.set(f"{r:g}")
        return r

    def calcular_totales(self) -> Dict[str, Any]:
        total_precio = 0.0
        total_unidades = 0
        omitidos_sin_precio = 0

        for _, data in self.selected_by_key.items():
            info = data["info"]
            qty = _to_int(data.get("qty", 1), 1)
            total_unidades += qty
            pv = info.get("precio_venta")
            if pv is None:
                prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") else info.get("id"))
                if prod_db:
                    fresh = parse_producto(prod_db)
                    info.update(fresh)
                    pv = fresh.get("precio_venta")

            if pv is None:
                if qty > 0:
                    omitidos_sin_precio += 1
                continue

            try:
                total_precio += _to_float(pv, 0.0) * qty
            except Exception:
                omitidos_sin_precio += 1

        dsc, imp = self._leer_descuento_impuesto()
        base = total_precio
        con_desc = base * (1 - dsc / 100.0)
        final = con_desc * (1 + imp / 100.0)

        return {"base": base, "descuento": dsc, "impuesto": imp, "total": final, "unidades": total_unidades, "omitidos": omitidos_sin_precio}

    def actualizar_totales(self):
        tot = self.calcular_totales()
        self.lbl_resumen_sel.config(text=f"{len(self.selected_by_key)} prod / {tot['unidades']} uds")
        self.lbl_total_precio.config(text=f"Total: {format_currency(tot['total'])}  (Base: {format_currency(tot['base'])}, Desc: {tot['descuento']}%, Imp: {tot['impuesto']}%)")
        self.lbl_omitidos.config(text=("Omitidos sin precio: " + str(tot["omitidos"])) if tot["omitidos"] > 0 else "")
        recibido = self._leer_recibido()
        cambio = max(0.0, recibido - tot["total"])
        self.cambio_var.set(format_currency(cambio))

    def limpiar_seleccion(self):
        if not self.selected_by_key:
            return
        if messagebox.askyesno("Vaciar carrito", "¿Deseas quitar todos los productos del carrito?"):
            self.selected_by_key.clear()
            self.aplicar_filtro()
            self.actualizar_totales()

    def vender_seleccionados(self, event=None):
        cliente = (self.entry_cliente.get() or "").strip()
        if not cliente:
            messagebox.showwarning("Cliente requerido", "Debe ingresar el nombre del cliente antes de vender.")
            return
        if not self.selected_by_key:
            messagebox.showinfo("Carrito vacío", "No hay productos seleccionados para vender.")
            return

        items_venta = []
        errores = []

        for _, data in self.selected_by_key.items():
            info = data["info"]
            qty = _to_int(data.get("qty", 1), 1)
            if qty <= 0:
                continue

            prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") else info.get("id"))
            if not prod_db:
                errores.append(f"{info.get('codigo') or info.get('id')}: no encontrado")
                continue

            fresh = parse_producto(prod_db)
            stock_disp = _to_int(fresh.get("stock", 0), 0)
            if qty > stock_disp:
                errores.append(f"{fresh.get('codigo')}: stock insuficiente (disp {stock_disp}, pedido {qty})")
                continue

            items_venta.append({"pid": fresh.get("id"), "nombre": fresh.get("nombre"), "codigo": fresh.get("codigo"), "qty": qty, "precio": fresh.get("precio_venta")})

        if not items_venta:
            if errores:
                messagebox.showerror("No se puede vender", "Problemas detectados:\n- " + "\n- ".join(errores))
            else:
                messagebox.showinfo("Sin ítems", "No hay cantidades válidas para vender.")
            return

        tot = self.calcular_totales()
        recibido = self._leer_recibido()
        metodo = self.metodo_pago_var.get()

        detalle = []
        for it in items_venta:
            if it["precio"] is not None:
                subtotal = _to_float(it["precio"], 0.0) * it["qty"]
                detalle.append(f"- {it['nombre']} x{it['qty']} = {format_currency(subtotal)}")
            else:
                detalle.append(f"- {it['nombre']} x{it['qty']} = (sin precio)")

        msg = (
            f"Cliente: {cliente}\n"
            f"Método de pago: {metodo}\n\n"
            f"Detalle:\n" + "\n".join(detalle) + "\n\n"
            f"Base: {format_currency(tot['base'])}\n"
            f"Descuento {tot['descuento']}% → {format_currency(tot['base'] * (1 - tot['descuento']/100.0))}\n"
            f"Impuesto {tot['impuesto']}% → Total: {format_currency(tot['total'])}\n"
            f"Recibido: {format_currency(recibido)}\n"
            f"Cambio: {self.cambio_var.get()}\n"
        )
        if errores:
            msg += "\nAdvertencias:\n- " + "\n- ".join(errores)
        msg += "\n¿Confirmar venta?"

        if not messagebox.askyesno("Confirmar venta", msg):
            return

        ok_count = 0
        totales_backend = []
        nuevos_stocks = {}
        errores_exec = []

        for it in items_venta:
            try:
                res = registrar_venta(it["pid"], it["qty"], cliente)
                ok_count += 1
                if isinstance(res, dict):
                    totales_backend.append(res.get("total"))
                    if "nuevo_stock" in res:
                        nuevos_stocks[it["codigo"]] = res.get("nuevo_stock")
            except Exception as e:
                errores_exec.append(f"{it['codigo']}: {e}")

        resumen = [f"Ventas registradas: {ok_count}"]
        valid_totales = [t for t in totales_backend if t is not None]
        if valid_totales:
            try:
                suma = sum(_to_float(t, 0.0) for t in valid_totales)
                resumen.append(f"Total backend: {format_currency(suma)}")
            except Exception:
                pass
        if nuevos_stocks:
            try:
                partes = []
                for k, v in nuevos_stocks.items():
                    if v is None:
                        partes.append(f"{k}→?")
                    else:
                        partes.append(f"{k}→{_to_int(v, 0)}")
                resumen.append("Nuevos stocks: " + ", ".join(partes))
            except Exception:
                resumen.append("Nuevos stocks: " + ", ".join(f"{k}→{v}" for k, v in nuevos_stocks.items()))
        if errores or errores_exec:
            resumen.append("Errores: " + "; ".join(errores + errores_exec))

        if ok_count > 0:
            messagebox.showinfo("Resultado de ventas", "\n".join(resumen))
        else:
            messagebox.showerror("No se completaron ventas", "\n".join(resumen))

        self._post_venta_refresh(nuevos_stocks)

        if ok_count > 0:
            if messagebox.askyesno("Comprobante", "¿Deseas exportar el comprobante de esta venta?"):
                self._exportar_comprobante(cliente, metodo, items_venta, tot, recibido, self.cambio_var.get())

    def _post_venta_refresh(self, nuevos_stocks: Dict[str, Any]):
        current_search = self.filtro_texto_var.get()
        self.cargar_productos()
        self.filtro_texto_var.set(current_search)
        self.aplicar_filtro()
        self.actualizar_totales()

        to_remove = []
        for key, data in self.selected_by_key.items():
            info = data["info"]
            codigo = info.get("codigo")
            if codigo in nuevos_stocks and (nuevos_stocks[codigo] is not None):
                try:
                    if _to_float(nuevos_stocks[codigo], 0.0) <= 0.0:
                        to_remove.append(key)
                except Exception:
                    pass
        for k in to_remove:
            self.selected_by_key.pop(k, None)
        self.aplicar_filtro()
        self.actualizar_totales()
        self.status("Proceso de venta finalizado")

    def _nueva_venta(self):
        self.entry_cliente.delete(0, tk.END)
        self.descuento_var.set("0")
        self.impuesto_var.set("0")
        self.metodo_pago_var.set("Efectivo")
        self.recibido_var.set("0")
        self.cambio_var.set("$0.00")
        self.selected_by_key.clear
        self.selected_by_key.clear()
        self.aplicar_filtro()
        self.actualizar_panel_detalle()
        self.actualizar_panel_seleccion()
        self.actualizar_totales()
        self.status("Nueva venta iniciada")

    def _agregar_por_codigo_rapido(self):
        codigo = self.codigo_rapido_var.get().strip()
        if not codigo:
            return
        prod_db = find_producto_en_bd(codigo)
        if not prod_db:
            messagebox.showerror("No encontrado", f"No se encontró ningún producto con código/ID: {codigo}")
            self.codigo_rapido_var.set("")
            return
        info = parse_producto(prod_db)
        key = product_key(info)
        if key in self.selected_by_key:
            self.selected_by_key[key]["qty"] += 1
        else:
            self.selected_by_key[key] = {"info": info, "qty": 1}
        self.codigo_rapido_var.set("")
        self.aplicar_filtro()
        self.actualizar_totales()

    def _show_help(self):
        ayuda = (
            "Atajos de teclado:\n"
            "Ctrl+F: Buscar\n"
            "Ctrl+R: Recargar productos\n"
            "Ctrl+L: Vaciar carrito\n"
            "Ctrl+Enter: Vender\n"
            "F2: Editar cantidad\n"
            "F5: Recalcular totales\n"
            "Esc: Cerrar ventana\n\n"
            "Interacción:\n"
            "- Doble clic o Enter sobre un producto: agregar o quitar del carrito\n"
            "- Shift+Doble clic: agregar con cantidad personalizada\n"
            "- Clic derecho sobre un producto: menú contextual"
        )
        messagebox.showinfo("Ayuda", ayuda)

    def _exportar_comprobante(self, cliente, metodo, items_venta, tot, recibido, cambio):
        fecha = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"venta_{fecha}.txt"
        ruta = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=nombre_archivo, filetypes=[("Texto", "*.txt")])
        if not ruta:
            return
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(f"Comprobante de venta - {fecha}\n")
                f.write(f"Cliente: {cliente}\n")
                f.write(f"Método de pago: {metodo}\n\n")
                for it in items_venta:
                    if it["precio"] is not None:
                        subtotal = _to_float(it["precio"], 0.0) * it["qty"]
                        f.write(f"{it['nombre']} x{it['qty']} = {format_currency(subtotal)}\n")
                    else:
                        f.write(f"{it['nombre']} x{it['qty']} = (sin precio)\n")
                f.write("\n")
                f.write(f"Base: {format_currency(tot['base'])}\n")
                f.write(f"Descuento: {tot['descuento']}%\n")
                f.write(f"Impuesto: {tot['impuesto']}%\n")
                f.write(f"Total: {format_currency(tot['total'])}\n")
                f.write(f"Recibido: {format_currency(recibido)}\n")
                f.write(f"Cambio: {cambio}\n")
            messagebox.showinfo("Comprobante guardado", f"Archivo guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el comprobante:\n{e}")



def ventana_ventas(owner=None):
    SalesView(owner)

if __name__ == "__main__":
    ventana_ventas()

