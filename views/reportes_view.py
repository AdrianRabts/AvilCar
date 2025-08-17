import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date
from collections import defaultdict

# Modelos existentes
from models.reportes import ventas_totales, ventas_por_producto, productos_bajo_stock, movimientos_recientes
from models.ventas import obtener_ventas

# Intentar habilitar gráficos (matplotlib). Si no está, degradar con aviso.
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False


def ventana_reportes(master=None):
    root_created = False
    if master is None:
        root = tk.Tk()
        root_created = True
    else:
        root = tk.Toplevel(master)

    root.title("Inventario - Reportes")
    root.geometry("1200x820")

    estilo = ttk.Style()
    try:
        estilo.theme_use("clam")
    except Exception:
        pass
    estilo.configure("TButton", padding=(6, 4))
    estilo.configure("Treeview", rowheight=24)

    # ------------- UTILIDADES UI -------------
    def build_tree(parent, columns, height=12, stretch=True):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        tv = ttk.Treeview(container, columns=columns, show="headings", height=height)
        vsb = ttk.Scrollbar(container, orient="vertical", command=tv.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=tv.xview)
        tv.configure(yscroll=vsb.set, xscroll=hsb.set)

        tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        for c in columns:
            tv.heading(c, text=c)
            tv.column(c, width=140, anchor="w", stretch=stretch)

        # Estilos de filas
        tv.tag_configure("even", background="#f6f6f6")
        tv.tag_configure("odd", background="#ffffff")
        tv.tag_configure("good", background="#dff0d8", foreground="#3c763d")
        tv.tag_configure("bad", background="#f2dede", foreground="#a94442")
        tv.tag_configure("warn", background="#fcf8e3", foreground="#8a6d3b")

        # Ordenar por columna
        for c in columns:
            tv.heading(c, text=c, command=lambda col=c, tree=tv: sort_by_column(tree, col))

        # Menú contextual copiar fila
        menu = tk.Menu(tv, tearoff=0)
        menu.add_command(label="Copiar fila", command=lambda: copy_selected_row(tv))

        def show_context_menu(event):
            try:
                rowid = tv.identify_row(event.y)
                if rowid:
                    tv.selection_set(rowid)
                    tv.focus(rowid)
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        tv.bind("<Button-3>", show_context_menu)
        return tv

    def fill_treeview(tv, rows, tag_func=None):
        tv.delete(*tv.get_children())
        for i, r in enumerate(rows):
            base_tag = "even" if i % 2 == 0 else "odd"
            tags = [base_tag]
            if tag_func:
                t = tag_func(r)
                if t:
                    tags.append(t)
            tv.insert("", tk.END, values=r, tags=tuple(tags))

    def sort_by_column(tv, col, reverse=None):
        idx = tv["columns"].index(col)

        def parse_val(x):
            s = str(x).strip()
            # número
            try:
                return float(s.replace(",", ""))
            except ValueError:
                pass
            # fechas comunes
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"):
                try:
                    return datetime.strptime(s, fmt)
                except ValueError:
                    continue
            return s.lower()

        pairs = []
        for iid in tv.get_children(""):
            vals = tv.item(iid, "values")
            pairs.append((parse_val(vals[idx]), iid))

        key = f"_sort_{col}"
        if reverse is None:
            reverse = not getattr(tv, key, False)
            setattr(tv, key, reverse)

        pairs.sort(key=lambda t: t[0], reverse=reverse)
        for pos, (_, iid) in enumerate(pairs):
            tv.move(iid, "", pos)

    def copy_selected_row(tv):
        sel = tv.focus()
        if not sel:
            return
        vals = tv.item(sel, "values")
        txt = "\t".join(str(v) for v in vals)
        root.clipboard_clear()
        root.clipboard_append(txt)

    def ask_save_csv_for_tree(tv):
        path = filedialog.asksaveasfilename(
            title="Guardar como CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(tv["columns"])
                for iid in tv.get_children(""):
                    w.writerow(tv.item(iid, "values"))
            messagebox.showinfo("Exportar", f"Exportado a:\n{path}")
        except Exception as e:
            messagebox.showerror("Exportar", f"No se pudo exportar:\n{e}")

    def get_first_tree_in(widget):
        if isinstance(widget, ttk.Treeview):
            return widget
        for ch in widget.winfo_children():
            tv = get_first_tree_in(ch)
            if tv:
                return tv
        return None

    # ------------- TOOLBAR SUPERIOR -------------
    toolbar = ttk.Frame(root)
    toolbar.pack(fill="x", padx=10, pady=8)

    btn_actualizar = ttk.Button(toolbar, text="Actualizar ahora")
    btn_actualizar.pack(side="left", padx=4)

    ttk.Label(toolbar, text="Auto-actualizar (seg):").pack(side="left", padx=(12, 4))
    spin_intervalo = ttk.Spinbox(toolbar, from_=5, to=3600, width=6)
    spin_intervalo.set("30")
    spin_intervalo.pack(side="left", padx=4)

    auto_var = tk.BooleanVar(value=True)
    chk_auto = ttk.Checkbutton(toolbar, text="Activado", variable=auto_var)
    chk_auto.pack(side="left", padx=8)

    lbl_last = ttk.Label(toolbar, text="Última actualización: --")
    lbl_last.pack(side="right", padx=4)

    btn_exportar_tabla = ttk.Button(toolbar, text="Exportar tabla visible (CSV)")
    btn_exportar_tabla.pack(side="right", padx=4)

    # ------------- NOTEBOOK -------------
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=8)

    # ----- TAB KPI + RESUMEN -----
    tab_resumen = ttk.Frame(notebook)
    notebook.add(tab_resumen, text="KPI y Resumen")

    # KPIs
    kpi_frame = ttk.Frame(tab_resumen)
    kpi_frame.pack(fill="x", pady=6)

    def kpi_label(parent, titulo):
        fr = ttk.LabelFrame(parent, text=titulo)
        val = ttk.Label(fr, text="--", font=("Segoe UI", 16, "bold"))
        val.pack(padx=10, pady=10)
        return fr, val

    kpi_hoy_f, kpi_hoy_val = kpi_label(kpi_frame, "Ventas de hoy")
    kpi_mes_f, kpi_mes_val = kpi_label(kpi_frame, "Ventas del mes")
    kpi_vs_f, kpi_vs_val = kpi_label(kpi_frame, "Vs mes anterior")

    kpi_hoy_f.pack(side="left", padx=6)
    kpi_mes_f.pack(side="left", padx=6)
    kpi_vs_f.pack(side="left", padx=6)

    # Total general
    lbl_total = ttk.Label(tab_resumen, text="Ventas Totales: --", font=("Segoe UI", 12, "bold"))
    lbl_total.pack(pady=6, anchor="w")

    cols_resumen = ("ID", "Nombre", "Unidades Vendidas", "Total Vendido")
    tv_ventas = build_tree(tab_resumen, cols_resumen, height=12)

    # ----- TAB HISTORIAL CON FILTROS -----
    tab_hist = ttk.Frame(notebook)
    notebook.add(tab_hist, text="Historial Ventas")

    filtros = ttk.LabelFrame(tab_hist, text="Filtros")
    filtros.pack(fill="x", padx=4, pady=4)

    ttk.Label(filtros, text="Desde (YYYY-MM-DD):").grid(row=0, column=0, padx=4, pady=4, sticky="w")
    entry_desde = ttk.Entry(filtros, width=12)
    entry_desde.grid(row=0, column=1, padx=4, pady=4)

    ttk.Label(filtros, text="Hasta (YYYY-MM-DD):").grid(row=0, column=2, padx=4, pady=4, sticky="w")
    entry_hasta = ttk.Entry(filtros, width=12)
    entry_hasta.grid(row=0, column=3, padx=4, pady=4)

    ttk.Label(filtros, text="Cliente:").grid(row=0, column=4, padx=4, pady=4, sticky="w")
    entry_cliente = ttk.Entry(filtros, width=18)
    entry_cliente.grid(row=0, column=5, padx=4, pady=4)

    ttk.Label(filtros, text="Buscar en nombre:").grid(row=0, column=6, padx=4, pady=4, sticky="w")
    entry_buscar = ttk.Entry(filtros, width=18)
    entry_buscar.grid(row=0, column=7, padx=4, pady=4)

    ttk.Label(filtros, text="Tamaño página:").grid(row=0, column=8, padx=4, pady=4, sticky="w")
    spin_pagsize = ttk.Spinbox(filtros, from_=10, to=500, width=5)
    spin_pagsize.set("50")
    spin_pagsize.grid(row=0, column=9, padx=4, pady=4)

    ttk.Button(filtros, text="Aplicar", command=lambda: aplicar_filtros_hist(reset_page=True)).grid(row=0, column=10, padx=4, pady=4)
    ttk.Button(filtros, text="Limpiar", command=lambda: limpiar_filtros_hist()).grid(row=0, column=11, padx=4, pady=4)

    cols_hist = ("ID", "Producto ID", "Nombre", "Cantidad", "Total", "Fecha", "Cliente")
    tv_hist = build_tree(tab_hist, cols_hist, height=18)

    pag_bar = ttk.Frame(tab_hist)
    pag_bar.pack(fill="x", pady=4)
    btn_prev = ttk.Button(pag_bar, text="⟨ Anterior", command=lambda: cambiar_pagina(-1))
    btn_prev.pack(side="left", padx=4)
    lbl_pagina = ttk.Label(pag_bar, text="Página 1/1")
    lbl_pagina.pack(side="left", padx=8)
    btn_next = ttk.Button(pag_bar, text="Siguiente ⟩", command=lambda: cambiar_pagina(1))
    btn_next.pack(side="left", padx=4)

    # ----- TAB MENSUAL (GRÁFICO) -----
    tab_mensual = ttk.Frame(notebook)
    notebook.add(tab_mensual, text="Reporte Mensual")

    controls_m = ttk.LabelFrame(tab_mensual, text="Parámetros")
    controls_m.pack(fill="x", padx=6, pady=6)

    ttk.Label(controls_m, text="Año:").pack(side="left", padx=4)
    combo_anio = ttk.Combobox(controls_m, state="readonly", width=8, values=[])
    combo_anio.pack(side="left", padx=4)

    ttk.Label(controls_m, text="Meta mensual (umbral):").pack(side="left", padx=8)
    entry_meta_mensual = ttk.Entry(controls_m, width=10)
    entry_meta_mensual.insert(0, "1000")
    entry_meta_mensual.pack(side="left", padx=4)

    ttk.Button(controls_m, text="Aplicar", command=lambda: dibujar_grafico_mensual()).pack(side="left", padx=8)

    graf_container = ttk.Frame(tab_mensual)
    graf_container.pack(fill="both", expand=True, padx=6, pady=6)

    if MATPLOTLIB_OK:
        fig = Figure(figsize=(8, 4), dpi=100)
        ax = fig.add_subplot(111)
        canvas = FigureCanvasTkAgg(fig, master=graf_container)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill="both", expand=True)
    else:
        lbl_no_mpl = ttk.Label(graf_container, text="Instala matplotlib para ver el gráfico mensual.")
        lbl_no_mpl.pack(pady=20)

    # ----- TAB MOVIMIENTOS / STOCK -----
    tab_mov = ttk.Frame(notebook)
    notebook.add(tab_mov, text="Movimientos / Stock")

    ttk.Label(tab_mov, text="Movimientos recientes").pack(pady=6, anchor="w")
    cols_m = ("ID", "Producto ID", "Nombre", "Cantidad", "Tipo", "Motivo", "Fecha")
    tv_mov = build_tree(tab_mov, cols_m, height=12)

    frame_stock = ttk.LabelFrame(tab_mov, text="Stock crítico")
    frame_stock.pack(pady=8, fill="x")
    ttk.Label(frame_stock, text="Umbral stock ≤").pack(side="left", padx=6)
    entry_umbral = ttk.Entry(frame_stock, width=6)
    entry_umbral.insert(0, "5")
    entry_umbral.pack(side="left", padx=6)
    ttk.Button(frame_stock, text="Mostrar", command=lambda: cargar_bajo_stock()).pack(side="left", padx=6)

    cols2 = ("ID", "Nombre", "Stock")
    tv_stock = build_tree(tab_mov, cols2, height=10)

    # ------------- ESTADO -------------
    ventas_hist_todas = []
    pagina_actual = 1
    total_paginas = 1
    job_auto = None

    # ------------- LÓGICA -------------
    def parse_date_safe(s):
        if not s:
            return None
        s = str(s).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    def recargar_todo():
        nonlocal ventas_hist_todas, pagina_actual
        # KPI + Totales + Resumen
        try:
            total = ventas_totales()
            lbl_total.config(text=f"Ventas Totales: {total}")
        except Exception as e:
            lbl_total.config(text="Ventas Totales: --")
            messagebox.showwarning("Resumen", f"No se pudo obtener ventas totales:\n{e}")

        try:
            filas_resumen = ventas_por_producto()
            fill_treeview(tv_ventas, filas_resumen)
        except Exception as e:
            fill_treeview(tv_ventas, [])
            messagebox.showwarning("Resumen", f"No se pudieron cargar ventas por producto:\n{e}")

        # Historial base
        try:
            ventas_hist_todas = obtener_ventas() or []
        except Exception as e:
            ventas_hist_todas = []
            messagebox.showwarning("Historial", f"No se pudo cargar el historial de ventas:\n{e}")

        # KPIs derivados del historial
        try:
            hoy = date.today()
            ventas_hoy = 0.0
            ventas_mes = 0.0
            ventas_mes_ant = 0.0
            for r in ventas_hist_todas:
                # r = ("ID","Producto ID","Nombre","Cantidad","Total","Fecha","Cliente")
                total_r = float(str(r[4]).replace(",", "")) if r[4] is not None else 0.0
                f = parse_date_safe(r[5])
                if not f:
                    continue
                if f.date() == hoy:
                    ventas_hoy += total_r
                if f.year == hoy.year and f.month == hoy.month:
                    ventas_mes += total_r
                # mes anterior
                ant_year = hoy.year if hoy.month > 1 else hoy.year - 1
                ant_month = hoy.month - 1 if hoy.month > 1 else 12
                if f.year == ant_year and f.month == ant_month:
                    ventas_mes_ant += total_r

            kpi_hoy_val.config(text=f"{ventas_hoy:,.2f}")
            kpi_mes_val.config(text=f"{ventas_mes:,.2f}")

            # Variación mes a mes
            if ventas_mes_ant > 0:
                delta = (ventas_mes - ventas_mes_ant) / ventas_mes_ant * 100.0
                signo = "▲" if delta >= 0 else "▼"
                color_tag = "good" if delta >= 0 else "bad"
                kpi_vs_val.config(text=f"{signo} {delta:+.1f}% vs. mes ant.")
                # colorear el fondo del label según resultado
                kpi_vs_f.configure(style="")
                # ttk no aplica bg directo a LabelFrame; mantenemos solo el texto
            else:
                kpi_vs_val.config(text="N/D")
        except Exception:
            kpi_hoy_val.config(text="--")
            kpi_mes_val.config(text="--")
            kpi_vs_val.config(text="--")

        # Filtros + paginación
        pagina_actual = 1
        aplicar_filtros_hist(reset_page=True)

        # Movimientos (colorear salidas)
        try:
            filas_mov = movimientos_recientes(200)
            def tag_mov(row):
                try:
                    cantidad = float(str(row[3]).replace(",", ""))
                except Exception:
                    cantidad = 0
                tipo = str(row[4]).strip().lower() if len(row) > 4 else ""
                if cantidad < 0 or tipo in ("salida", "egreso"):
                    return "bad"
                return None
            fill_treeview(tv_mov, filas_mov, tag_func=tag_mov)
        except Exception as e:
            fill_treeview(tv_mov, [])
            messagebox.showwarning("Movimientos", f"No se pudieron cargar los movimientos:\n{e}")

        # Stock crítico coloreado
        cargar_bajo_stock()

        # Gráfico mensual (siempre recalcular opciones de año)
        actualizar_anios_disponibles()
        dibujar_grafico_mensual()

        # Marcar hora
        lbl_last.config(text=f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def limpiar_filtros_hist():
        entry_desde.delete(0, tk.END)
        entry_hasta.delete(0, tk.END)
        entry_cliente.delete(0, tk.END)
        entry_buscar.delete(0, tk.END)
        aplicar_filtros_hist(reset_page=True)

    def aplicar_filtros_hist(reset_page=False):
        nonlocal pagina_actual, total_paginas
        if reset_page:
            pagina_actual = 1

        desde = parse_date_safe(entry_desde.get())
        hasta = parse_date_safe(entry_hasta.get())
        cliente_q = entry_cliente.get().strip().lower()
        texto_q = entry_buscar.get().strip().lower()

        def pasa(row):
            nombre = str(row[2]).lower()
            cliente = str(row[6]).lower() if len(row) > 6 and row[6] else ""
            if texto_q and texto_q not in nombre:
                return False
            if cliente_q and cliente_q not in cliente:
                return False
            if desde or hasta:
                f = parse_date_safe(row[5])
                if not f:
                    return False
                if desde and f < desde:
                    return False
                if hasta and f > hasta:
                    return False
            return True

        filtradas = [r for r in ventas_hist_todas if pasa(r)]

        try:
            pagsize = max(1, int(spin_pagsize.get()))
        except ValueError:
            pagsize = 50
            spin_pagsize.set("50")

        total_paginas = max(1, (len(filtradas) + pagsize - 1) // pagsize)
        pagina_actual = min(max(1, pagina_actual), total_paginas)
        ini = (pagina_actual - 1) * pagsize
        fin = ini + pagsize
        fill_treeview(tv_hist, filtradas[ini:fin])
        lbl_pagina.config(text=f"Página {pagina_actual}/{total_paginas}")
        btn_prev.configure(state=("disabled" if pagina_actual <= 1 else "normal"))
        btn_next.configure(state=("disabled" if pagina_actual >= total_paginas else "normal"))

    def cambiar_pagina(delta):
        nonlocal pagina_actual
        pagina_actual = max(1, min(pagina_actual + delta, total_paginas))
        aplicar_filtros_hist(reset_page=False)

    def cargar_bajo_stock():
        try:
            try:
                umbral = int(entry_umbral.get())
            except ValueError:
                umbral = 5
                entry_umbral.delete(0, tk.END)
                entry_umbral.insert(0, "5")
            filas = productos_bajo_stock(umbral) or []

            def tag_stock(row):
                try:
                    stock = float(str(row[2]).replace(",", ""))
                except Exception:
                    stock = 0
                return "bad" if stock <= umbral else "good"

            fill_treeview(tv_stock, filas, tag_func=tag_stock)
        except Exception as e:
            fill_treeview(tv_stock, [])
            messagebox.showwarning("Stock", f"No se pudo cargar el stock crítico:\n{e}")

    # --------- Reporte mensual (gráfico) ---------
    def actualizar_anios_disponibles():
        # Derivar años de ventas_hist_todas; fallback: año actual
        anios = set()
        for r in ventas_hist_todas:
            f = parse_date_safe(r[5])
            if f:
                anios.add(f.year)
        if not anios:
            anios = {datetime.now().year}
        valores = sorted(list(anios))
        combo_anio["values"] = valores
        if combo_anio.get() == "" or int(combo_anio.get() or 0) not in valores:
            combo_anio.set(str(valores[-1]))

    def ventas_mensuales_por_anio(anio):
        # Retorna lista de 12 totales por mes (1..12)
        totales = [0.0] * 12
        for r in ventas_hist_todas:
            f = parse_date_safe(r[5])
            if not f or f.year != anio:
                continue
            try:
                total_r = float(str(r[4]).replace(",", "")) if r[4] is not None else 0.0
            except Exception:
                total_r = 0.0
            totales[f.month - 1] += total_r
        return totales

    def dibujar_grafico_mensual():
        if not MATPLOTLIB_OK:
            return
        try:
            anio = int(combo_anio.get() or datetime.now().year)
        except ValueError:
            anio = datetime.now().year
            combo_anio.set(str(anio))
        try:
            meta = float(entry_meta_mensual.get().replace(",", "."))
        except ValueError:
            meta = 1000.0
            entry_meta_mensual.delete(0, tk.END)
            entry_meta_mensual.insert(0, "1000")

        datos = ventas_mensuales_por_anio(anio)
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        colores = ["#5cb85c" if v >= meta else "#d9534f" for v in datos]

        fig.clf()
        ax = fig.add_subplot(111)
        ax.bar(meses, datos, color=colores)
        ax.axhline(meta, color="#f0ad4e", linestyle="--", linewidth=2, label=f"Umbral {meta:,.0f}")
        ax.set_title(f"Ventas mensuales {anio}")
        ax.set_ylabel("Total vendido")
        ax.legend(loc="upper left")
        ax.grid(axis="y", alpha=0.25)
        # Etiquetas en cada barra
        for i, v in enumerate(datos):
            ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()
        canvas.draw_idle()

    # ------------- AUTO-REFRESH -------------
    def tick_auto():
        nonlocal job_auto
        if auto_var.get():
            recargar_todo()
            try:
                intervalo = max(5, int(spin_intervalo.get()))
            except ValueError:
                intervalo = 30
                spin_intervalo.set("30")
            job_auto = root.after(intervalo * 1000, tick_auto)
        else:
            job_auto = None

    def toggle_auto(*_):
        nonlocal job_auto
        if auto_var.get():
            if job_auto is None:
                tick_auto()
        else:
            if job_auto is not None:
                root.after_cancel(job_auto)
                job_auto = None

    # ------------- EVENTOS UI -------------
    btn_actualizar.config(command=recargar_todo)
    btn_exportar_tabla.config(command=lambda: exportar_tabla_visible())
    auto_var.trace_add("write", toggle_auto)

    def exportar_tabla_visible():
        curr = notebook.select()
        if not curr:
            return
        tab = root.nametowidget(curr)
        tv = get_first_tree_in(tab)
        if tv:
            ask_save_csv_for_tree(tv)
        else:
            messagebox.showinfo("Exportar", "No hay tabla visible para exportar.")

    # ------------- INICIO -------------
    recargar_todo()
    tick_auto()  # inicia auto si está activo

    # ------------- CIERRE -------------
    ttk.Button(root, text="Cerrar", command=lambda: on_close()).pack(pady=8)

    def on_close():
        nonlocal job_auto
        try:
            if job_auto is not None:
                root.after_cancel(job_auto)
        except Exception:
            pass
        root.destroy()

    if root_created:
        root.mainloop()
