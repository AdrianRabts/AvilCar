import datetime
from typing import Optional, List, Tuple, Dict, Union
from database.db import get_connection
from models.movimientos import registrar_movimiento


# ====== REGISTRAR VENTA ======
def registrar_venta(producto_id: int, cantidad: Union[int, float], cliente: Optional[str] = None) -> Dict:
    """
    Registra una venta de un producto y actualiza el stock.
    Retorna un diccionario con detalles de la venta y nuevo stock.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Obtener precio y stock actual
            cursor.execute(
                "SELECT precio, stock FROM productos WHERE id = ?",
                (producto_id,)
            )
            fila = cursor.fetchone()
            if fila is None:
                raise ValueError("Producto no encontrado.")
            precio_unitario, stock_actual = fila

            if stock_actual < cantidad:
                raise ValueError("Stock insuficiente.")

            total = precio_unitario * cantidad
            fecha = datetime.datetime.now().isoformat(timespec='seconds')

            # Actualizar stock
            nuevo_stock = stock_actual - cantidad
            cursor.execute(
                "UPDATE productos SET stock = ? WHERE id = ?",
                (nuevo_stock, producto_id)
            )

            # Registrar venta
            cursor.execute("""
                INSERT INTO ventas (producto_id, cantidad, total, fecha, cliente)
                VALUES (?, ?, ?, ?, ?)
            """, (producto_id, cantidad, total, fecha, cliente))

            # Registrar movimiento de salida para trazabilidad
            registrar_movimiento(
                producto_id, cantidad,
                tipo="salida",
                motivo="venta",
                conn=conn
            )

            conn.commit()
            return {
                "producto_id": producto_id,
                "cantidad": cantidad,
                "total": total,
                "fecha": fecha,
                "nuevo_stock": nuevo_stock
            }
        except Exception as e:
            conn.rollback()
            raise e


# ====== OBTENER VENTAS ======
def obtener_ventas(limite: Optional[int] = None) -> List[Tuple]:
    """
    Devuelve todas las ventas realizadas.
    Cada fila: (id_venta, producto_id, nombre_producto, cantidad, total, fecha, cliente)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = """
            SELECT v.id,
                   v.producto_id,
                   p.nombre,
                   v.cantidad,
                   v.total,
                   v.fecha,
                   v.cliente
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            ORDER BY v.fecha DESC, v.id DESC
        """
        if limite and limite > 0:
            sql += " LIMIT ?"
            cursor.execute(sql, (limite,))
        else:
            cursor.execute(sql)

        filas = cursor.fetchall()
    return [tuple(r) for r in filas] if filas else []
