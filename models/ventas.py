import datetime
from typing import Optional, List, Dict, Union
from database.db import get_connection
from models.movimientos import registrar_movimiento

# ====== REGISTRAR VENTA ======
def registrar_venta(producto_id: int, cantidad: Union[int, float], cliente: Optional[str] = None) -> Dict:
    """
    Registra una venta de un producto, actualiza el stock y guarda el movimiento.
    Retorna un diccionario con detalles de la venta y el nuevo stock.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    # Valor por defecto para cliente si no se envía
    cliente_val = cliente if cliente else "Desconocido"

    with get_connection() as conn:
        try:
            cursor = conn.cursor()

            # Obtener datos del producto
            cursor.execute("""
                SELECT precio_venta, stock, nombre 
                FROM productos 
                WHERE id = ?
            """, (producto_id,))
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Producto no encontrado.")

            precio_unitario, stock_actual, nombre_producto = fila

            if stock_actual < cantidad:
                raise ValueError("Stock insuficiente.")

            total = round(precio_unitario * cantidad, 2)
            fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Actualizar stock solo si hay suficiente (previene condiciones de carrera)
            cursor.execute("""
                UPDATE productos 
                SET stock = stock - ? 
                WHERE id = ? AND stock >= ?
            """, (cantidad, producto_id, cantidad))

            if cursor.rowcount == 0:
                raise ValueError("Stock insuficiente o producto no encontrado.")

            # Registrar la venta
            cursor.execute("""
                INSERT INTO ventas (producto_id, cantidad, total, fecha, cliente)
                VALUES (?, ?, ?, ?, ?)
            """, (producto_id, cantidad, total, fecha, cliente_val))
            id_venta = cursor.lastrowid

            # Registrar movimiento
            registrar_movimiento(
                producto_id, cantidad,
                tipo="salida",
                motivo="venta",
                conn=conn
            )

            conn.commit()

            return {
                "id_venta": id_venta,
                "producto_id": producto_id,
                "nombre_producto": nombre_producto,
                "cantidad": cantidad,
                "total": total,
                "fecha": fecha,
                "nuevo_stock": stock_actual - cantidad,
                "cliente": cliente_val
            }

        except Exception:
            conn.rollback()
            raise

# ====== OBTENER VENTAS ======
def obtener_ventas(limite: Optional[int] = None) -> List[Dict]:
    """
    Devuelve todas las ventas realizadas.
    """
    with get_connection() as conn:
        conn.row_factory = None  # si quieres usar tu conversión manual
        cursor = conn.cursor()

        sql = """
            SELECT v.id,
                   v.producto_id,
                   COALESCE(p.nombre, 'Desconocido') AS nombre_producto,
                   v.cantidad,
                   v.total,
                   v.fecha,
                   v.cliente
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            ORDER BY v.fecha DESC, v.id DESC
        """
        params = ()
        if limite and limite > 0:
            sql += " LIMIT ?"
            params = (limite,)
        cursor.execute(sql, params)

        filas = cursor.fetchall()

    # Convertir a lista de dicts
    ventas = [
        {
            "id": r[0],
            "producto_id": r[1],
            "nombre_producto": r[2],
            "cantidad": r[3],
            "total": round(r[4], 2),
            "fecha": r[5],
            "cliente": r[6] or ""
        }
        for r in filas
    ]
    return ventas
