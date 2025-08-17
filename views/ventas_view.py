import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

# Módulos de datos (tus mismos modelos)
from models.producto import (
    obtener_productos,
    obtener_producto_por_codigo,
    obtener_producto_por_sku,
)
from models.ventas import registrar_venta

# Configuración UI/negocio
UMBRAL_STOCK_BAJO = 5
DEBOUNCE_MS = 220
ROW_HEIGHT = 26


def ventana_ventas():
    root = tk.Tk()
    root.title("Inventario - Ventas")
    root.geometry("1200x720")

    # ---- Estilos y colores ----
    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass

    estilo.configure("Treeview", rowheight=ROW_HEIGHT, font=("Segoe UI", 10))
    estilo.configure("TLabel", font=("Segoe UI", 10))
    estilo.configure("TButton", padding=(10, 6), font=("Segoe UI", 10))
    estilo.configure("Accent.TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))
    estilo.map("Accent.TButton", background=[("active", "#2e7d32")], foreground=[("active", "white")])
    estilo.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
    estilo.configure("Muted.TLabel", foreground="#666")

    COLOR_BG_OK = "#e8f5e9"
    COLOR_BG_LOW = "#ffebee"
    COLOR_TXT_OK = "#2e7d32"
    COLOR_TXT_LOW = "#c62828"
    COLOR_BADGE_NEUTRO = "#9e9e9e"

    # ---- Estado ----
    productos_all = []  # lista cruda desde la BD
    sort_state: Dict[str, bool] = {}
    search_job: Optional[str] = None

    # Mapa de filas visibles: iid -> info y key
    visible_by_iid: Dict[str, Dict[str, Any]] = {}

    # Selección persistente por clave (id preferido, si no código)
    # key -> {info, qty, precio (opcional cache)}
    selected_by_key: Dict[str, Dict[str, Any]] = {}

    last_focus_key: Optional[str] = None  # para panel de detalle

    # Variables de descuento e impuesto
    descuento_var = tk.StringVar(value="0")
    impuesto_var = tk.StringVar(value="0")

    # ---- Utilidades de datos ----
    def parse_producto(p):
        """
        Esquema real (SQLite productos):
        0: id, 1: nombre, 2: precio, 3: stock, 4: sku (código)
        """
        pid = p[0] if len(p) > 0 else None
        nombre = p[1] if len(p) > 1 else ""
        precio = p[2] if len(p) > 2 else None
        stock_raw = p[3] if len(p) > 3 else 0
        codigo = p[4] if len(p) > 4 and p[4] not in (None, "") else pid
        try:
            stock = float(str(stock_raw))
        except Exception:
            stock = 0.0
        try:
            precio_v = float(precio) if precio is not None else None
        except Exception:
            precio_v = None
        return {"id": pid, "nombre": str(nombre), "stock": stock, "codigo": codigo, "precio": precio_v}

    def product_key(info: Dict[str, Any]) -> str:
        if info.get("id") not in (None, ""):
            return f"id:{info['id']}"
        return f"cod:{info.get('codigo')}"

    def extraer_precio(prod):
        """
        Precio en índice 2 según tu esquema.
        """
        if len(prod) > 2:
            try:
                val = float(prod[2])
                return val
            except Exception:
                return None
        return None

    def find_producto_en_bd(codigo_o_id: Any):
        """
        Busca por código (sku), luego por SKU explícito, luego intenta ID.
        Devuelve el registro crudo de BD (tupla/lista original) o None.
        """
        prod = None
        # Por código (sku)
        try:
            prod = obtener_producto_por_codigo(str(codigo_o_id))
        except Exception:
            prod = None
        # Por SKU si no encontró (segundo intento explícito)
        if not prod:
            try:
                prod = obtener_producto_por_sku(str(codigo_o_id))
            except Exception:
                prod = None
        if prod:
            return prod
        # Buscar por ID en memoria y como cadena en código
        try:
            pid = int(str(codigo_o_id))
            for p in productos_all:
                if len(p) > 0 and p[0] == pid:
                    return p
            prod = obtener_producto_por_codigo(str(pid))
            if prod:
                return prod
        except Exception:
            pass
        return None

    def prod_to_fields(prod):
        """Extrae campos seguros desde un registro crudo de BD."""
        pid = prod[0] if len(prod) > 0 else None
        nombre = prod[1] if len(prod) > 1 else ""
        precio = extraer_precio(prod)
        stock_raw = prod[3] if len(prod) > 3 else 0
        codigo = prod[4] if len(prod) > 4 and prod[4] not in (None, "") else pid
        try:
            stock = float(str(stock_raw))
        except Exception:
            stock = 0.0
        return pid, nombre, stock, codigo, precio

    # ---- Carga y filtrado ----
    def cargar_productos():
        nonlocal productos_all
        try:
            productos_all = obtener_productos() or []
        except Exception as e:
            productos_all = []
            messagebox.showerror("Productos", f"No se pudieron cargar los productos:\n{e}")
        aplicar_filtro()

    def aplicar_filtro(*_):
        nonlocal search_job
        texto = entry_buscar.get().strip().lower()
        # Limpia tabla
        tv.delete(*tv.get_children())
        visible_by_iid.clear()

        count = 0
        for p in productos_all:
            info = parse_producto(p)
            if texto and not (
                texto in info["nombre"].lower()
                or texto in str(info["codigo"]).lower()
                or texto in str(info["id"]).lower()
            ):
                continue
            tag = "ok" if info["stock"] > UMBRAL_STOCK_BAJO else "low"

            key = product_key(info)
            marcado = "☑" if key in selected_by_key else "☐"
            precio_txt = "-" if info["precio"] is None else f"{info['precio']:,.2f}"

            iid = tv.insert(
                "",
                "end",
                values=(marcado, info["codigo"], info["nombre"], f"{info['stock']:.0f}", precio_txt, info["id"]),
                tags=(tag,),
            )
            visible_by_iid[iid] = {"info": info, "key": key}
            count += 1

        if count == 0:
            lbl_empty.place(relx=0.5, rely=0.5, anchor="center")
            status("Sin resultados")
        else:
            lbl_empty.place_forget()
            status(f"{count} producto(s) encontrados")

        # Mantener foco sobre último key si existe
        if last_focus_key:
            for iid, meta in visible_by_iid.items():
                if meta["key"] == last_focus_key:
                    tv.selection_set(iid)
                    tv.focus(iid)
                    break

        actualizar_panel_detalle()
        actualizar_panel_seleccion()
        actualizar_totales()  # totales al refrescar

    def debounce_filtro(*_):
        nonlocal search_job
        if search_job:
            try:
                root.after_cancel(search_job)
            except Exception:
                pass
        search_job = root.after(DEBOUNCE_MS, aplicar_filtro)

    # ---- Ordenación ----
    def ordenar_por(col):
        col_index = {"Sel.": 0, "Código": 1, "Nombre": 2, "Stock": 3, "Precio": 4, "ID": 5}[col]
        reverse = sort_state.get(col, False)
        filas = [(tv.item(iid, "values"), iid) for iid in tv.get_children("")]
        def parse(v):
            s = str(v).strip()
            try:
                # soporta 1,234.56
                return float(s.replace(",", ""))
            except ValueError:
                return s.lower()
        filas.sort(key=lambda t: parse(t[0][col_index]), reverse=reverse)
        for i, (_, iid) in enumerate(filas):
            tv.move(iid, "", i)
        sort_state[col] = not reverse

    # ---- Selección (checkbox múltiple) ----
    def toggle_row_selection(iid):
        nonlocal last_focus_key
        if not iid or iid not in visible_by_iid:
            return
        info = visible_by_iid[iid]["info"]
        key = visible_by_iid[iid]["key"]
        vals = list(tv.item(iid, "values"))

        if key in selected_by_key:
            # Quitar
            selected_by_key.pop(key, None)
            vals[0] = "☐"
        else:
            # Agregar con cantidad inicial 1 (limitada por stock)
            qty = 1
            try:
                qty = min(1, int(info["stock"])) if info["stock"] < 1 else 1
            except Exception:
                qty = 1
            selected_by_key[key] = {"info": info, "qty": qty, "precio": info.get("precio")}
            vals[0] = "☑"
            last_focus_key = key

        tv.item(iid, values=vals)
        actualizar_panel_detalle()
        actualizar_panel_seleccion()
        actualizar_totales()

    def on_tree_click(event):
        region = tv.identify("region", event.x, event.y)
        if region not in ("cell", "tree"):
            return
        rowid = tv.identify_row(event.y)
        if not rowid:
            return
        toggle_row_selection(rowid)
        if rowid in visible_by_iid:
            last_focus_key = visible_by_iid[rowid]["key"]

    def on_tree_double_click(event):
        on_tree_click(event)

    # ---- Panel de detalle (producto enfocado o resumen) ----
    def actualizar_panel_detalle():
        if len(selected_by_key) == 1:
            key = next(iter(selected_by_key.keys()))
            info = selected_by_key[key]["info"]
            # Sincroniza con BD para stock/precio frescos
            prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") not in (None, "") else info.get("id"))
            if prod_db:
                pid, nombre, stock, codigo, precio = prod_to_fields(prod_db)
            else:
                pid, nombre, stock, codigo, precio = info.get("id"), info.get("nombre"), info.get("stock", 0), info.get("codigo"), info.get("precio")
            lbl_p_nombre.config(text=str(nombre) if nombre else f"ID {pid}")
            lbl_p_codigo.config(text=str(codigo))
            lbl_p_id.config(text=str(pid))
            ok = stock > UMBRAL_STOCK_BAJO
            stock_badge.config(text=f"{int(stock)}", bg=(COLOR_TXT_OK if ok else COLOR_TXT_LOW), fg="white")
            lbl_p_precio.config(text=("-" if precio is None else f"{precio:,.2f}"))
        elif len(selected_by_key) == 0:
            # vacío
            lbl_p_nombre.config(text="—")
            lbl_p_codigo.config(text="—")
            lbl_p_id.config(text="—")
            lbl_p_precio.config(text="—")
            stock_badge.config(text="—", bg=COLOR_BADGE_NEUTRO, fg="white")
        else:
            # resumen
            total = len(selected_by_key)
            bajos = sum(1 for k in selected_by_key.values() if k["info"].get("stock", 0) <= UMBRAL_STOCK_BAJO)
            lbl_p_nombre.config(text=f"{total} productos seleccionados")
            lbl_p_codigo.config(text=f"Stock bajo: {bajos}")
            lbl_p_id.config(text="—")
            lbl_p_precio.config(text="—")
            stock_badge.config(text="—", bg=COLOR_BADGE_NEUTRO, fg="white")

    # ---- Panel de selección (lista con cantidades y subtotales) ----
    def vaciar_frame(f):
        for w in f.winfo_children():
            w.destroy()

    def actualizar_panel_seleccion():
        vaciar_frame(sel_inner)
        if not selected_by_key:
            ttk.Label(sel_inner, text="Sin productos seleccionados", foreground="#666").grid(row=0, column=0, sticky="w")
            btn_vender.state(["disabled"])
            btn_clear_sel.state(["disabled"])
            btn_act_totales.state(["disabled"])
            return

        btn_vender.state(["!disabled"])
        btn_clear_sel.state(["!disabled"])
        btn_act_totales.state(["!disabled"])

        # Encabezados
        ttk.Label(sel_inner, text="#", width=3).grid(row=0, column=0, sticky="w")
        ttk.Label(sel_inner, text="Código", width=16).grid(row=0, column=1, sticky="w")
        ttk.Label(sel_inner, text="Nombre").grid(row=0, column=2, sticky="w")
        ttk.Label(sel_inner, text="Stock", width=8).grid(row=0, column=3, sticky="e")
        ttk.Label(sel_inner, text="Precio", width=10).grid(row=0, column=4, sticky="e")
        ttk.Label(sel_inner, text="Cant.", width=8).grid(row=0, column=5, sticky="e")
        ttk.Label(sel_inner, text="Subtotal", width=12).grid(row=0, column=6, sticky="e")
        ttk.Label(sel_inner, text="").grid(row=0, column=7, sticky="e")

        for r, (key, data) in enumerate(selected_by_key.items(), start=1):
            info = data["info"]
            # Refrescar desde BD (stock/precio) para mostrar datos al día
            prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") not in (None, "") else info.get("id"))
            if prod_db:
                pid, nombre, stock, codigo, precio = prod_to_fields(prod_db)
                info["stock"] = stock
                info["nombre"] = nombre or info["nombre"]
                info["codigo"] = codigo or info["codigo"]
                data["precio"] = precio
            else:
                pid, nombre, stock, codigo, precio = info.get("id"), info.get("nombre"), info.get("stock", 0), info.get("codigo"), info.get("precio")

            ok = stock > UMBRAL_STOCK_BAJO
            color_fg = COLOR_TXT_OK if ok else COLOR_TXT_LOW

            ttk.Label(sel_inner, text=str(r)).grid(row=r, column=0, sticky="w")
            ttk.Label(sel_inner, text=str(codigo)).grid(row=r, column=1, sticky="w")
            ttk.Label(sel_inner, text=str(nombre)).grid(row=r, column=2, sticky="w")
            ttk.Label(sel_inner, text=f"{int(stock)}", foreground=color_fg).grid(row=r, column=3, sticky="e")

            # Precio unitario
            ttk.Label(sel_inner, text=("-" if precio is None else f"{precio:,.2f}")).grid(row=r, column=4, sticky="e")

            # Spinbox de cantidad (limitado por stock)
            qty_val = max(1, min(int(data.get("qty", 1)), int(stock) if stock >= 1 else 1))
            data["qty"] = qty_val
            qty_var = tk.StringVar(value=str(qty_val))

            def make_on_change(k=key, var=qty_var, max_stock=stock):
                def _on_change(*_):
                    try:
                        val = int(var.get())
                        if val < 1:
                            val = 1
                        if max_stock >= 1 and val > int(max_stock):
                            val = int(max_stock)
                        selected_by_key[k]["qty"] = val
                        var.set(str(val))
                        actualizar_totales()
                    except Exception:
                        selected_by_key[k]["qty"] = 1
                        var.set("1")
                        actualizar_totales()
                return _on_change

            qty_var.trace_add("write", make_on_change())
            qty_box = ttk.Spinbox(sel_inner, from_=1, to=max(1, int(stock)) if stock >= 1 else 1, textvariable=qty_var, width=6, justify="right")
            qty_box.grid(row=r, column=5, sticky="e", padx=(6, 0))

            # Subtotal (si hay precio)
            if precio is not None:
                try:
                    subtotal = float(precio) * int(qty_var.get())
                    lbl_st = ttk.Label(sel_inner, text=f"{subtotal:,.2f}")
                except Exception:
                    lbl_st = ttk.Label(sel_inner, text="-", foreground="#B00020")
            else:
                lbl_st = ttk.Label(sel_inner, text="Sin precio", foreground="#B00020")
            lbl_st.grid(row=r, column=6, sticky="e", padx=(6, 0))

            # Botón quitar
            def make_remove(k=key):
                return lambda: (selected_by_key.pop(k, None), aplicar_filtro(), actualizar_totales())
            btn_rm = ttk.Button(sel_inner, text="Quitar", command=make_remove())
            btn_rm.grid(row=r, column=7, sticky="e", padx=(6, 0))

        # Ajustar scrollregion
        sel_inner.update_idletasks()
        sel_canvas.configure(scrollregion=sel_canvas.bbox("all"))
        actualizar_totales()

    # ---- Totales y validaciones de acciones ----
    def _leer_descuento_impuesto():
        # Devuelve (descuento, impuesto) como floats no negativos
        try:
            d = float(descuento_var.get() or "0")
            if d < 0:
                d = 0
        except ValueError:
            d = 0
        try:
            i = float(impuesto_var.get() or "0")
            if i < 0:
                i = 0
        except ValueError:
            i = 0
        return d, i

    def actualizar_totales():
        total_precio = 0.0
        total_unidades = 0
        omitidos_sin_precio = 0

        for key, data in selected_by_key.items():
            info = data["info"]
            qty = int(data.get("qty", 1))
            total_unidades += qty
            precio = data.get("precio", None)
            if precio is None:
                # si no hay precio cacheado, intentar leer de BD
                prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") not in (None, "") else info.get("id"))
                if prod_db:
                    _, _, _, _, precio = prod_to_fields(prod_db)
                    data["precio"] = precio
            if precio is None:
                omitidos_sin_precio += 1 if qty > 0 else 0
                continue
            try:
                total_precio += float(precio) * qty
            except Exception:
                omitidos_sin_precio += 1

        # Aplicar descuento e impuesto
        descuento, impuesto = _leer_descuento_impuesto()
        total_con_descuento = total_precio * (1 - descuento / 100)
        total_final = total_con_descuento * (1 + impuesto / 100)

        lbl_resumen_sel.config(text=f"{len(selected_by_key)} prod / {total_unidades} uds")
        lbl_total_precio.config(
            text=f"Total: {total_final:,.2f}  (Base: {total_precio:,.2f}, Desc: {descuento}%, Imp: {impuesto}%)"
        )
        lbl_omitidos.config(text=("Omitidos sin precio: " + str(omitidos_sin_precio)) if omitidos_sin_precio > 0 else "")

    def limpiar_seleccion():
        if not selected_by_key:
            return
        if not messagebox.askyesno("Limpiar selección", "¿Deseas quitar todos los productos seleccionados?"):
            return
        selected_by_key.clear()
        aplicar_filtro()
        actualizar_totales()

    # ---- Venta ----
    def vender_seleccionados(event=None):
        cliente = (entry_cliente.get() or "").strip()
        if not cliente:
            messagebox.showwarning("Cliente requerido", "Debe ingresar el nombre del cliente antes de vender.")
            return

        if not selected_by_key:
            messagebox.showinfo("Sin selección", "No hay productos seleccionados para vender.")
            return

        # Validaciones y lectura fresca desde BD
        items_venta = []
        errores = []
        for key, data in selected_by_key.items():
            info = data["info"]
            qty = int(data.get("qty", 1))
            if qty <= 0:
                continue

            prod_db = find_producto_en_bd(info.get("codigo") if info.get("codigo") not in (None, "") else info.get("id"))
            if not prod_db:
                errores.append(f"{info.get('codigo') or info.get('id')}: no encontrado")
                continue

            pid, nombre, stock, codigo, precio = prod_to_fields(prod_db)
            if qty > stock:
                errores.append(f"{codigo}: stock insuficiente (disp {int(stock)}, pedido {qty})")
                continue

            items_venta.append({"pid": pid, "nombre": nombre, "codigo": codigo, "qty": qty, "precio": precio})

        if not items_venta:
            if errores:
                messagebox.showerror("No se puede vender", "Problemas detectados:\n- " + "\n- ".join(errores))
            else:
                messagebox.showinfo("Sin ítems", "No hay cantidades válidas para vender.")
            return

        # Confirmación con detalle y total estimado (si hay precios)
        total_estimado = 0.0
        det_lineas = []
        for it in items_venta:
            if it["precio"] is not None:
                subtotal = float(it["precio"]) * it["qty"]
                total_estimado += subtotal
                det_lineas.append(f"- {it['nombre']} x{it['qty']} = {subtotal:,.2f}")
            else:
                det_lineas.append(f"- {it['nombre']} x{it['qty']} = (sin precio)")

        # Aplicar descuentos e impuestos al total estimado
        descuento, impuesto = _leer_descuento_impuesto()
        total_con_descuento = total_estimado * (1 - descuento / 100)
        total_final = total_con_descuento * (1 + impuesto / 100)

        msg = f"Cliente: {cliente}\n\nDetalle:\n" + "\n".join(det_lineas)
        if total_estimado > 0:
            msg += f"\n\nBase: {total_estimado:,.2f}"
            if descuento > 0:
                msg += f"\nDescuento {descuento}% → {total_con_descuento:,.2f}"
            if impuesto > 0:
                msg += f"\nImpuesto {impuesto}% → {total_final:,.2f}"
            msg += f"\n\nTotal final: {total_final:,.2f}"
        if errores:
            msg += "\n\nAdvertencias:\n- " + "\n- ".join(errores)
        msg += "\n\n¿Confirmar venta?"

        if not messagebox.askyesno("Confirmar venta", msg):
            return

        # Ejecutar ventas una a una contra tu backend
        ok_count = 0
        totales_backend = []
        nuevos_stocks = {}
        errores_exec = []

        for it in items_venta:
            try:
                res = registrar_venta(it["pid"], it["qty"], cliente)
                ok_count += 1
                totales_backend.append(res.get("total"))
                nuevos_stocks[it["codigo"]] = res.get("nuevo_stock")
            except Exception as e:
                errores_exec.append(f"{it['codigo']}: {e}")

        # Resumen final
        resumen = [f"Ventas registradas: {ok_count}"]
        if totales_backend and all(t is not None for t in totales_backend):
            try:
                suma = sum(float(t) for t in totales_backend)
                resumen.append(f"Total backend: {suma:,.2f}")
            except Exception:
                pass
        if nuevos_stocks:
            resumen.append("Nuevos stocks: " + ", ".join(f"{k}→{v}" for k, v in nuevos_stocks.items()))
        if errores or errores_exec:
            resumen.append("Errores: " + "; ".join(errores + errores_exec))

        if ok_count > 0:
            messagebox.showinfo("Resultado de ventas", "\n".join(resumen))
        else:
            messagebox.showerror("No se completaron ventas", "\n".join(resumen))

        # Refrescar UI manteniendo la búsqueda
        current_search = entry_buscar.get()
        cargar_productos()
        entry_buscar.delete(0, tk.END)
        entry_buscar.insert(0, current_search)
        aplicar_filtro()
        actualizar_totales()

        # Limpiar selección de los que quedaron en 0 stock (si se conoce)
        keys_to_remove = []
        for key, data in selected_by_key.items():
            info = data["info"]
            codigo = info.get("codigo")
            if codigo in nuevos_stocks and (nuevos_stocks[codigo] is not None):
                try:
                    if float(nuevos_stocks[codigo]) <= 0:
                        keys_to_remove.append(key)
                except Exception:
                    pass
        for k in keys_to_remove:
            selected_by_key.pop(k, None)
        aplicar_filtro()
        actualizar_totales()
        status("Proceso de venta finalizado")

    # ---- UI ----
    # Header
    header = ttk.Frame(root, padding=(12, 10))
    header.pack(fill="x")
    ttk.Label(header, text="Panel de ventas", style="Header.TLabel").pack(side="left")

    # Búsqueda
    search_frame = ttk.Frame(header)
    search_frame.pack(side="right")
    ttk.Label(search_frame, text="Buscar:").pack(side="left")
    entry_buscar = ttk.Entry(search_frame, width=36)
    entry_buscar.pack(side="left", padx=(6, 0))
    ttk.Button(search_frame, text="Limpiar", command=lambda: (entry_buscar.delete(0, tk.END), aplicar_filtro())).pack(side="left", padx=(6, 0))

    # Cuerpo dividido
    body = ttk.Frame(root)
    body.pack(fill="both", expand=True, padx=12, pady=6)
    body.columnconfigure(0, weight=3)
    body.columnconfigure(1, weight=2)
    body.rowconfigure(0, weight=1)

    # Izquierda: Tabla productos
    tabla_frame = ttk.LabelFrame(body, text="Productos", padding=6)
    tabla_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    tabla_frame.rowconfigure(0, weight=1)
    tabla_frame.columnconfigure(0, weight=1)

    cols = ("Sel.", "Código", "Nombre", "Stock", "Precio", "ID")
    tv = ttk.Treeview(tabla_frame, columns=cols, show="headings", height=18)
    tv.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(tabla_frame, orient="vertical", command=tv.yview)
    vsb.grid(row=0, column=1, sticky="ns")
    tv.configure(yscroll=vsb.set)

    tv.tag_configure("ok", background=COLOR_BG_OK)
    tv.tag_configure("low", background=COLOR_BG_LOW)

    widths = {"Sel.": 54, "Código": 140, "Nombre": 340, "Stock": 90, "Precio": 110, "ID": 90}
    for c in cols:
        tv.heading(c, text=c, command=lambda cc=c: ordenar_por(cc))
        anchor = "w" if c in ("Sel.", "Código", "Nombre") else "e"
        tv.column(c, width=widths[c], anchor=anchor, stretch=(c == "Nombre"))

    lbl_empty = ttk.Label(tabla_frame, text="Sin resultados", foreground="#666")

    # Derecha: Detalle + Selección + Acciones
    right = ttk.Frame(body)
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(1, weight=1)

    # Detalle
    card = ttk.LabelFrame(right, text="Detalle", padding=10)
    card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    card.columnconfigure(1, weight=1)

    ttk.Label(card, text="Nombre:").grid(row=0, column=0, sticky="w", pady=2)
    lbl_p_nombre = ttk.Label(card, text="—", font=("Segoe UI", 11, "bold"))
    lbl_p_nombre.grid(row=0, column=1, sticky="w")

    ttk.Label(card, text="Código:").grid(row=1, column=0, sticky="w", pady=2)
    lbl_p_codigo = ttk.Label(card, text="—")
    lbl_p_codigo.grid(row=1, column=1, sticky="w")

    ttk.Label(card, text="ID:").grid(row=2, column=0, sticky="w", pady=2)
    lbl_p_id = ttk.Label(card, text="—")
    lbl_p_id.grid(row=2, column=1, sticky="w")

    ttk.Label(card, text="Stock:").grid(row=3, column=0, sticky="w", pady=2)
    # Usamos tk.Label para poder cambiar bg dinámicamente
    stock_badge = tk.Label(card, text="—", bg=COLOR_BADGE_NEUTRO, fg="white", padx=8, pady=2)
    stock_badge.grid(row=3, column=1, sticky="w")

    ttk.Label(card, text="Precio:").grid(row=4, column=0, sticky="w", pady=2)
    lbl_p_precio = ttk.Label(card, text="—")
    lbl_p_precio.grid(row=4, column=1, sticky="w")

    # Selección (scrollable)
    sel_frame = ttk.LabelFrame(right, text="Selección", padding=8)
    sel_frame.grid(row=1, column=0, sticky="nsew")
    sel_frame.rowconfigure(0, weight=1)
    sel_frame.columnconfigure(0, weight=1)

    sel_canvas = tk.Canvas(sel_frame, highlightthickness=0)
    sel_vsb = ttk.Scrollbar(sel_frame, orient="vertical", command=sel_canvas.yview)
    sel_inner = ttk.Frame(sel_canvas)

    sel_canvas.create_window((0, 0), window=sel_inner, anchor="nw")
    sel_canvas.configure(yscrollcommand=sel_vsb.set)

    sel_canvas.grid(row=0, column=0, sticky="nsew")
    sel_vsb.grid(row=0, column=1, sticky="ns")

    def _on_frame_configure(event):
        sel_canvas.configure(scrollregion=sel_canvas.bbox("all"))
        try:
            sel_canvas.itemconfig(1, width=sel_canvas.winfo_width())
        except Exception:
            pass

    sel_inner.bind("<Configure>", _on_frame_configure)

    # Acciones
    actions = ttk.LabelFrame(right, text="Acciones de venta", padding=10)
    actions.grid(row=2, column=0, sticky="ew", pady=(6, 0))
    actions.columnconfigure(0, weight=0)
    actions.columnconfigure(1, weight=1)
    actions.columnconfigure(2, weight=0)
    actions.columnconfigure(3, weight=1)

    ttk.Label(actions, text="Cliente (obligatorio):").grid(row=0, column=0, sticky="w", pady=(6, 0))
    entry_cliente = ttk.Entry(actions)
    entry_cliente.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(6, 0))

    lbl_resumen_sel = ttk.Label(actions, text="—", style="Muted.TLabel")
    lbl_resumen_sel.grid(row=0, column=2, sticky="e", padx=(0, 6), pady=(6, 0))

    ttk.Label(actions, text="Descuento %:").grid(row=1, column=0, sticky="w")
    entry_descuento = ttk.Entry(actions, width=10, textvariable=descuento_var)
    entry_descuento.grid(row=1, column=1, sticky="w", padx=(6, 6))

    ttk.Label(actions, text="Impuesto %:").grid(row=1, column=2, sticky="w")
    entry_impuesto = ttk.Entry(actions, width=10, textvariable=impuesto_var)
    entry_impuesto.grid(row=1, column=3, sticky="w", padx=(6, 6))

    lbl_total_precio = ttk.Label(actions, text="Total: 0.00  (Base: 0.00, Desc: 0%, Imp: 0%)", font=("Segoe UI", 10, "bold"))
    lbl_total_precio.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 6))

    lbl_omitidos = ttk.Label(actions, text="", style="Muted.TLabel")
    lbl_omitidos.grid(row=2, column=2, sticky="e", padx=(0, 6))

    btn_act_totales = ttk.Button(actions, text="Actualizar totales")
    btn_act_totales.grid(row=2, column=3, sticky="e", padx=(0, 6))

    btn_clear_sel = ttk.Button(actions, text="Limpiar selección")
    btn_clear_sel.grid(row=3, column=3, sticky="e", pady=(0, 8))

    btn_vender = ttk.Button(actions, text="Vender seleccionados", style="Accent.TButton")
    btn_vender.grid(row=3, column=0, columnspan=3, sticky="ew", padx=(0, 8), pady=(0, 8))

    # Barra de estado
    statusbar = ttk.Frame(root)
    statusbar.pack(fill="x", side="bottom")
    lbl_status = ttk.Label(statusbar, text="Listo", anchor="w")
    lbl_status.pack(fill="x", padx=10, pady=4)

    def status(msg):
        lbl_status.config(text=msg)

    # ---- Eventos ----
    entry_buscar.bind("<KeyRelease>", debounce_filtro)
    tv.bind("<Button-1>", on_tree_click)
    tv.bind("<Double-1>", on_tree_double_click)

    btn_vender.config(command=vender_seleccionados)
    btn_clear_sel.config(command=limpiar_seleccion)
    btn_act_totales.config(command=actualizar_totales)

    descuento_var.trace_add("write", lambda *_: actualizar_totales())
    impuesto_var.trace_add("write", lambda *_: actualizar_totales())

    root.bind("<Return>", vender_seleccionados)
    root.bind("<Delete>", lambda e: limpiar_seleccion())
    root.bind("<Escape>", lambda e: root.destroy())
    root.bind("<Control-r>", lambda e: cargar_productos())
    root.bind("<Control-f>", lambda e: (entry_buscar.focus_set(), entry_buscar.select_range(0, tk.END)))

    # ---- Inicio ----
    cargar_productos()
    entry_buscar.focus_set()
    root.mainloop()


if __name__ == "__main__":
    ventana_ventas()
