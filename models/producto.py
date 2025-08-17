# C:\Users\User\Desktop\InventarioAvilCar\AvilCar\models\producto.py

from database.db import get_connection
from models.movimientos import registrar_movimiento

# ====== AGREGAR PRODUCTO ======
def agregar_producto(nombre, precio, stock, sku=None, costo=0, minimo_stock=0, categoria_id=None, proveedor_id=None):
    """Agrega un nuevo producto a la base de datos."""
    if sku and existe_producto_por_codigo(sku):
        raise ValueError(f"Código '{sku}' ya existe")
    if nombre and existe_producto_por_nombre(nombre):
        raise ValueError(f"Producto con nombre '{nombre}' ya existe")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO productos (nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id))
        conn.commit()


# ====== OBTENER PRODUCTOS ======
def obtener_productos():
    """Devuelve todos los productos como tuplas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.nombre, p.precio, p.stock, p.sku, p.costo, p.minimo_stock,
                   p.categoria_id, p.proveedor_id, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            ORDER BY p.nombre
        """)
        datos = cursor.fetchall()
    return [tuple(r) for r in datos]


# ====== ELIMINAR PRODUCTO ======
def eliminar_producto(id_producto):
    """Elimina un producto por ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM productos WHERE id = ?", (id_producto,))
        conn.commit()


# ====== EDITAR PRODUCTO ======
def editar_producto(id_producto, nombre, precio, stock, sku=None, costo=0, minimo_stock=0, categoria_id=None, proveedor_id=None):
    """Edita un producto existente validando duplicados."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if sku:
            cursor.execute("SELECT id FROM productos WHERE sku = ? AND id != ?", (sku, id_producto))
            if cursor.fetchone():
                raise ValueError(f"Código '{sku}' ya asignado a otro producto")
        cursor.execute("SELECT id FROM productos WHERE nombre = ? AND id != ?", (nombre, id_producto))
        if cursor.fetchone():
            raise ValueError(f"Nombre '{nombre}' ya asignado a otro producto")
        
        cursor.execute("""
            UPDATE productos
            SET nombre = ?, precio = ?, stock = ?, sku = ?, costo = ?, minimo_stock = ?, categoria_id = ?, proveedor_id = ?
            WHERE id = ?
        """, (nombre, precio, stock, sku, costo, minimo_stock, categoria_id, proveedor_id, id_producto))
        conn.commit()


# ====== OBTENER POR ID O CÓDIGO ======
def obtener_producto_por_id(id_producto):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE id = ?", (id_producto,))
        producto = cursor.fetchone()
    return tuple(producto) if producto else None

def obtener_producto_por_sku(sku):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE sku = ?", (sku,))
        producto = cursor.fetchone()
    return tuple(producto) if producto else None

def obtener_producto_por_codigo(codigo):
    """Wrapper lógico para buscar por SKU como 'codigo'."""
    return obtener_producto_por_sku(codigo)


# ====== MANEJO DE STOCK CON TRAZABILIDAD ======
def reducir_stock(id_producto, cantidad, motivo="venta"):
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock FROM productos WHERE id = ?", (id_producto,))
        fila = cursor.fetchone()
        if not fila:
            raise ValueError("Producto no encontrado")
        stock_actual = fila[0]
        if stock_actual < cantidad:
            raise ValueError("Stock insuficiente")
        nuevo_stock = stock_actual - cantidad
        cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, id_producto))
        registrar_movimiento(id_producto, cantidad, "salida", motivo, conn=conn)
        conn.commit()
    return nuevo_stock

def aumentar_stock(id_producto, cantidad, motivo="compra"):
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que cero")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT stock FROM productos WHERE id = ?", (id_producto,))
        fila = cursor.fetchone()
        if not fila:
            raise ValueError("Producto no encontrado")
        nuevo_stock = fila[0] + cantidad
        cursor.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, id_producto))
        registrar_movimiento(id_producto, cantidad, "entrada", motivo, conn=conn)
        conn.commit()
    return nuevo_stock


# ====== BÚSQUEDAS Y REPORTES ======
def buscar_productos(termino):
    """Busca productos por nombre o SKU."""
    termino_like = f"%{termino}%"
    with get_connection() as conn:
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
    return [tuple(r) for r in filas]

def productos_criticos(umbral=5):
    """Devuelve productos con stock por debajo de umbral."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, stock, minimo_stock
            FROM productos
            WHERE stock <= ?
            ORDER BY stock ASC
        """, (umbral,))
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]


# ====== EXISTENCIA ======
def existe_producto_por_codigo(codigo):
    if not codigo:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM productos WHERE sku = ?", (codigo,))
        return cursor.fetchone() is not None

def existe_producto_por_nombre(nombre):
    if not nombre:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,))
        return cursor.fetchone() is not None
    sys.excepthook = report_callback_exception