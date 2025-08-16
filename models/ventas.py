import datetime
from database.db import get_connection
from models.producto import obtener_producto_por_id

def registrar_venta(producto_id, cantidad, cliente=None):
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Obtener precio y verificar existencia
        cursor.execute("SELECT precio, stock FROM productos WHERE id = ?", (producto_id,))
        fila = cursor.fetchone()
        if fila is None:
            raise ValueError("Producto no encontrado")
        precio_unitario, stock_actual = fila
        if stock_actual < cantidad:
            raise ValueError("Stock insuficiente")

        total = precio_unitario * cantidad
        fecha = datetime.datetime.now().isoformat(timespec='seconds')

        # Realizar actualización de stock y registro de venta en la misma conexión
        nuevo_stock = stock_actual - cantidad
        cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, producto_id))

        cursor.execute(
            "INSERT INTO ventas (producto_id, cantidad, total, fecha, cliente) VALUES (?, ?, ?, ?, ?)",
            (producto_id, cantidad, total, fecha, cliente)
        )

        # registrar movimiento usando el mismo cursor/conn
        from models.movimientos import registrar_movimiento
        registrar_movimiento(producto_id, cantidad, "salida", motivo="venta", conn=conn)

        conn.commit()
        return {
            "producto_id": producto_id,
            "cantidad": cantidad,
            "total": total,
            "fecha": fecha,
            "nuevo_stock": nuevo_stock
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def obtener_ventas():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.id, v.producto_id, p.nombre, v.cantidad, v.total, v.fecha, v.cliente
        FROM ventas v
        LEFT JOIN productos p ON v.producto_id = p.id
        ORDER BY v.fecha DESC
    """)
    datos = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in datos]
