from database.db import get_connection

def ventas_totales():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IFNULL(SUM(total), 0) FROM ventas")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def ventas_por_producto():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.nombre, IFNULL(SUM(v.cantidad),0) AS unidades_vendidas, IFNULL(SUM(v.total),0) AS total_vendido
        FROM productos p
        LEFT JOIN ventas v ON p.id = v.producto_id
        GROUP BY p.id, p.nombre
        ORDER BY total_vendido DESC
    """)
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]

def productos_bajo_stock(umbral=5):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, stock FROM productos WHERE stock <= ? ORDER BY stock ASC", (umbral,))
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]

# Nuevos reportes
def movimientos_recientes(limite=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT m.id, m.producto_id, p.nombre, m.cantidad, m.tipo, m.motivo, m.fecha FROM movimientos_stock m LEFT JOIN productos p ON m.producto_id = p.id ORDER BY m.fecha DESC LIMIT ?", (limite,))
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]

def ventas_por_periodo(fecha_inicio, fecha_fin):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.producto_id, p.nombre, v.cantidad, v.total, v.fecha
        FROM ventas v
        LEFT JOIN productos p ON v.producto_id = p.id
        WHERE date(v.fecha) BETWEEN date(?) AND date(?)
        ORDER BY v.fecha DESC
    """, (fecha_inicio, fecha_fin))
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]
