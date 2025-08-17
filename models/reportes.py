# C:\Users\User\Desktop\InventarioAvilCar\AvilCar\models\reportes.py

from database.db import get_connection

# ====== REPORTES DE VENTAS ======
def ventas_totales():
    """Devuelve la suma total de todas las ventas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT IFNULL(SUM(total), 0) FROM ventas")
        total = cursor.fetchone()[0]
    return total

def ventas_por_producto():
    """
    Devuelve lista de productos con:
    (id, nombre, unidades_vendidas, total_vendido)
    Ordenado por total vendido descendente.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.nombre,
                   IFNULL(SUM(v.cantidad), 0) AS unidades_vendidas,
                   IFNULL(SUM(v.total), 0) AS total_vendido
            FROM productos p
            LEFT JOIN ventas v ON p.id = v.producto_id
            GROUP BY p.id, p.nombre
            ORDER BY total_vendido DESC
        """)
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]

def productos_bajo_stock(umbral=5):
    """Devuelve productos con stock igual o menor al umbral."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, stock
            FROM productos
            WHERE stock <= ?
            ORDER BY stock ASC
        """, (umbral,))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]


# ====== MOVIMIENTOS ======
def movimientos_recientes(limite=100):
    """
    Devuelve los últimos movimientos de stock.
    (id_movimiento, producto_id, nombre_producto, cantidad, tipo, motivo, fecha)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.producto_id, p.nombre, m.cantidad, m.tipo, m.motivo, m.fecha
            FROM movimientos_stock m
            LEFT JOIN productos p ON m.producto_id = p.id
            ORDER BY m.fecha DESC
            LIMIT ?
        """, (limite,))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]


# ====== VENTAS POR PERIODO ======
def ventas_por_periodo(fecha_inicio, fecha_fin):
    """
    Devuelve todas las ventas entre dos fechas.
    (id_venta, producto_id, nombre_producto, cantidad, total, fecha)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id, v.producto_id, p.nombre, v.cantidad, v.total, v.fecha
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            WHERE date(v.fecha) BETWEEN date(?) AND date(?)
            ORDER BY v.fecha DESC
        """, (fecha_inicio, fecha_fin))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]
