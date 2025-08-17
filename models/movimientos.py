# C:\Users\User\Desktop\InventarioAvilCar\AvilCar\models\movimientos.py

import datetime
from database.db import get_connection

TIPOS_VALIDOS = ('entrada', 'salida')

def registrar_movimiento(producto_id, cantidad, tipo, motivo=None, conn=None):
    """
    Registra un movimiento de stock.
    
    Args:
        producto_id (int): ID del producto.
        cantidad (int|float): Cantidad a mover.
        tipo (str): 'entrada' o 'salida'.
        motivo (str, opcional): Motivo del movimiento.
        conn (Connection, opcional): Conexión existente para manejar transacción externamente.

    Returns:
        int: ID del movimiento registrado.

    Raises:
        ValueError: Si el tipo no es válido o cantidad <= 0.
    """
    tipo = (tipo or "").lower()
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo inválido: {tipo}. Debe ser 'entrada' o 'salida'.")
    
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")
    
    cerrar = False
    if conn is None:
        conn = get_connection()
        cerrar = True

    fecha = datetime.datetime.now().isoformat(timespec='seconds')
    
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO movimientos_stock (producto_id, cantidad, tipo, motivo, fecha)
            VALUES (?, ?, ?, ?, ?)
        """, (producto_id, cantidad, tipo, motivo, fecha))
        movimiento_id = cursor.lastrowid
        if cerrar:
            conn.commit()
            conn.close()
    return movimiento_id

def obtener_movimientos(producto_id=None, limite=100):
    """
    Obtiene movimientos de stock.
    
    Args:
        producto_id (int, opcional): Filtrar por producto.
        limite (int): Cantidad máxima de registros a obtener.
    
    Returns:
        list[tuple]: Lista de movimientos.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if producto_id:
            cursor.execute("""
                SELECT * FROM movimientos_stock
                WHERE producto_id = ?
                ORDER BY fecha DESC
                LIMIT ?
            """, (producto_id, limite))
        else:
            cursor.execute("""
                SELECT * FROM movimientos_stock
                ORDER BY fecha DESC
                LIMIT ?
            """, (limite,))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]
