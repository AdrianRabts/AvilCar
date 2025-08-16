from database.db import get_connection
from models.movimientos import registrar_movimiento

# ====== AGREGAR ======
def agregar_producto(nombre, precio, stock, sku=None, costo=0, minimo_stock=0, categoria_id=None, proveedor_id=None):
    # Validaciones de duplicado
    if sku and existe_producto_por_codigo(sku):
        raise ValueError(f"Código '{sku}' ya existe")
    if nombre and existe_producto_por_nombre(nombre):
        raise ValueError(f"Producto con nombre '{nombre}' ya existe")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO productos (nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id)
    )
    conn.commit()
    conn.close()

# ====== OBTENER ======
def obtener_productos():
    """
    Devuelve lista de productos como tuplas:
    (id, nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id, categoria_nombre)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.nombre, p.precio, p.stock, p.sku, p.costo, p.minimo_stock,
               p.categoria_id, p.proveedor_id, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.nombre
    """)
    datos = cursor.fetchall()
    conn.close()
    # Convertir sqlite3.Row a tuplas simples
    return [tuple(r) for r in datos]

# ====== ELIMINAR ======
def eliminar_producto(id_producto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id_producto,))
    conn.commit()
    conn.close()

# ====== EDITAR ======
def editar_producto(id_producto, nombre, precio, stock, sku=None, costo=0, minimo_stock=0, categoria_id=None, proveedor_id=None):
    # Validar que el nuevo nombre o codigo no pertenezcan a otro producto
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM productos WHERE sku = ? AND id != ?", (sku, id_producto))
    if sku and cursor.fetchone():
        conn.close()
        raise ValueError(f"Código '{sku}' ya asignado a otro producto")
    cursor.execute("SELECT id FROM productos WHERE nombre = ? AND id != ?", (nombre, id_producto))
    if cursor.fetchone():
        conn.close()
        raise ValueError(f"Nombre '{nombre}' ya asignado a otro producto")
    cursor.execute("""
        UPDATE productos
        SET nombre = ?, precio = ?, stock = ?, sku = ?, costo = ?, minimo_stock = ?, categoria_id = ?, proveedor_id = ?
        WHERE id = ?
    """, (nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id, id_producto))
    conn.commit()
    conn.close()

# ====== NUEVAS FUNCIONES ======
def obtener_producto_por_id(id_producto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos WHERE id = ?", (id_producto,))
    producto = cursor.fetchone()
    conn.close()
    return tuple(producto) if producto is not None else None

def obtener_producto_por_sku(sku):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos WHERE sku = ?", (sku,))
    producto = cursor.fetchone()
    conn.close()
    return tuple(producto) if producto is not None else None

# Nuevo: nombre lógico y claro para la API
def obtener_producto_por_codigo(codigo):
    """
    Wrapper lógico: busca por 'sku' en la BD pero expone la API como 'codigo'.
    Acepta None o cadena.
    """
    return obtener_producto_por_sku(codigo)

# Mantener compatibilidad: alias
# (self-assignment removed — no alias needed because both names are defined)

# Mejorar reducción/aumento de stock usando registro de movimiento para trazabilidad
def reducir_stock(id_producto, cantidad, motivo="venta"):
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT stock FROM productos WHERE id = ?", (id_producto,))
        fila = cursor.fetchone()
        if fila is None:
            raise ValueError("Producto no encontrado")
        stock_actual = fila[0]
        if stock_actual < cantidad:
            raise ValueError("Stock insuficiente")
        nuevo_stock = stock_actual - cantidad
        cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, id_producto))
        # registrar movimiento dentro de la misma conexión
        registrar_movimiento(id_producto, cantidad, "salida", motivo, conn=conn)
        conn.commit()
        return nuevo_stock
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def aumentar_stock(id_producto, cantidad, motivo="compra"):
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT stock FROM productos WHERE id = ?", (id_producto,))
        fila = cursor.fetchone()
        if fila is None:
            raise ValueError("Producto no encontrado")
        nuevo_stock = fila[0] + cantidad
        cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, id_producto))
        registrar_movimiento(id_producto, cantidad, "entrada", motivo, conn=conn)
        conn.commit()
        return nuevo_stock
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Búsqueda simple por nombre o SKU
def buscar_productos(termino):
    termino_like = f"%{termino}%"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.nombre, p.precio, p.stock, p.sku, p.costo, p.minimo_stock,
               p.categoria_id, p.proveedor_id, c.nombre as categoria_nombre
        FROM productos p
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.nombre LIKE ? OR p.sku LIKE ?
        ORDER BY p.nombre
    """, (termino_like, termino_like))
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]

# Productos con stock bajo (umbral configurable)
def productos_criticos(umbral=5):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, stock, minimo_stock FROM productos WHERE stock <= ? ORDER BY stock ASC", (umbral,))
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]

def existe_producto_por_codigo(codigo):
    if not codigo:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM productos WHERE sku = ?", (codigo,))
    existe = cursor.fetchone() is not None
    conn.close()
    return existe

def existe_producto_por_nombre(nombre):
    if not nombre:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,))
    existe = cursor.fetchone() is not None
    conn.close()
    return existe
