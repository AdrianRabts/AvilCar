from database.db import get_connection

# ====== REPORTES DE VENTAS ======
def ventas_totales() -> float:
    """Devuelve la suma total de todas las ventas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM ventas")
        total = cursor.fetchone()[0]
    return float(total or 0)


def ventas_por_producto() -> list[tuple]:
    """
    Devuelve lista de productos con:
    (id, nombre, unidades_vendidas, total_vendido)
    Ordenado por total vendido descendente y nombre.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id,
                   p.nombre,
                   COALESCE(SUM(v.cantidad), 0) AS unidades_vendidas,
                   COALESCE(SUM(v.total), 0)    AS total_vendido
            FROM productos p
            LEFT JOIN ventas v ON p.id = v.producto_id
            GROUP BY p.id, p.nombre
            ORDER BY total_vendido DESC, p.nombre ASC
        """)
        filas = cursor.fetchall()
    return [tuple(r) for r in filas] if filas else []


def productos_bajo_stock(umbral: int = 5) -> list[tuple]:
    """Devuelve productos con stock igual o menor al umbral."""
    if umbral < 0:
        raise ValueError("El umbral debe ser mayor o igual a cero.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, stock
            FROM productos
            WHERE stock <= ?
            ORDER BY stock ASC, nombre ASC
        """, (umbral,))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas] if filas else []


# ====== MOVIMIENTOS ======
def movimientos_recientes(limite: int = 100) -> list[tuple]:
    """
    Devuelve los últimos movimientos de stock.
    (id_movimiento, producto_id, nombre_producto, cantidad, tipo, motivo, fecha)
    """
    if limite <= 0:
        raise ValueError("El límite debe ser mayor que cero.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id,
                   m.producto_id,
                   p.nombre,
                   m.cantidad,
                   m.tipo,
                   m.motivo,
                   m.fecha
            FROM movimientos_stock m
            LEFT JOIN productos p ON m.producto_id = p.id
            ORDER BY m.fecha DESC, m.id DESC
            LIMIT ?
        """, (limite,))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas] if filas else []


# ====== VENTAS POR PERIODO ======
def ventas_por_periodo(fecha_inicio: str, fecha_fin: str) -> list[tuple]:
    """
    Devuelve todas las ventas entre dos fechas.
    (id_venta, producto_id, nombre_producto, cantidad, total, fecha)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id,
                   v.producto_id,
                   p.nombre,
                   v.cantidad,
                   v.total,
                   v.fecha
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            WHERE date(v.fecha) BETWEEN date(?) AND date(?)
            ORDER BY v.fecha DESC, v.id DESC
        """, (fecha_inicio, fecha_fin))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas] if filas else []
