import datetime
from database.db import get_connection

def registrar_movimiento(producto_id, cantidad, tipo, motivo=None, conn=None):
    """
    Registra un movimiento de stock.
    tipo: 'entrada' o 'salida'
    Si se pasa `conn`, no realiza commit ni close (deja al llamador manejar transacción).
    """
    cerrar = False
    if conn is None:
        conn = get_connection()
        cerrar = True
    cursor = conn.cursor()
    fecha = datetime.datetime.now().isoformat(timespec='seconds')
    cursor.execute("""
        INSERT INTO movimientos_stock (producto_id, cantidad, tipo, motivo, fecha)
        VALUES (?, ?, ?, ?, ?)
    """, (producto_id, cantidad, tipo, motivo, fecha))
    if cerrar:
        conn.commit()
        conn.close()
    return True

def obtener_movimientos(producto_id=None, limite=100):
    conn = get_connection()
    cursor = conn.cursor()
    if producto_id:
        cursor.execute(
            "SELECT * FROM movimientos_stock WHERE producto_id = ? ORDER BY fecha DESC LIMIT ?",
            (producto_id, limite)
        )
    else:
        cursor.execute(
            "SELECT * FROM movimientos_stock ORDER BY fecha DESC LIMIT ?",
            (limite,)
        )
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]
