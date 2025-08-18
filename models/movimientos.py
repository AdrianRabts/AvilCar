import datetime
from database.db import get_connection

TIPOS_VALIDOS = ("entrada", "salida")


# ====== VALIDACIÓN ======
def _validar_movimiento(producto_id, cantidad, tipo):
    """Valida y normaliza los datos del movimiento."""
    if not producto_id or not isinstance(producto_id, int):
        raise ValueError("El ID del producto debe ser un entero válido.")

    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero.")

    tipo = (tipo or "").strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo inválido: '{tipo}'. Debe ser 'entrada' o 'salida'.")

    return tipo


# ====== REGISTRAR MOVIMIENTO ======
def registrar_movimiento(producto_id, cantidad, tipo, motivo=None, conn=None):
    """
    Registra un movimiento de stock.

    Args:
        producto_id (int): ID del producto.
        cantidad (int|float): Cantidad a mover (> 0).
        tipo (str): 'entrada' o 'salida'.
        motivo (str, opcional): Motivo del movimiento.
        conn (Connection, opcional): Conexión SQLite existente.

    Returns:
        int: ID del movimiento registrado.
    """
    tipo = _validar_movimiento(producto_id, cantidad, tipo)

    cerrar_conexion = False
    if conn is None:
        conn = get_connection()
        cerrar_conexion = True

    fecha = datetime.datetime.now().isoformat(timespec="seconds")

    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO movimientos_stock (producto_id, cantidad, tipo, motivo, fecha)
            VALUES (?, ?, ?, ?, ?)
        """, (producto_id, cantidad, tipo, motivo, fecha))
        movimiento_id = cursor.lastrowid

    if cerrar_conexion:
        conn.commit()
        conn.close()

    return movimiento_id


# ====== OBTENER MOVIMIENTOS ======
def obtener_movimientos(producto_id=None, limite=100):
    """
    Obtiene los movimientos de stock más recientes.

    Args:
        producto_id (int, opcional): Filtrar por ID de producto.
        limite (int): Máximo número de registros a devolver.

    Returns:
        list[tuple]: Lista de movimientos como tuplas.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if producto_id is not None:
            cursor.execute("""
                SELECT id, producto_id, cantidad, tipo, motivo, fecha, created_at, updated_at
                FROM movimientos_stock
                WHERE producto_id = ?
                ORDER BY fecha DESC, id DESC
                LIMIT ?
            """, (producto_id, limite))
        else:
            cursor.execute("""
                SELECT id, producto_id, cantidad, tipo, motivo, fecha, created_at, updated_at
                FROM movimientos_stock
                ORDER BY fecha DESC, id DESC
                LIMIT ?
            """, (limite,))
        filas = cursor.fetchall()

    return [tuple(r) for r in filas] if filas else []
