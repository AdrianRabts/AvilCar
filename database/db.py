import sqlite3
from pathlib import Path

def _db_path():
    base = Path(__file__).resolve().parents[1]
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "inventario.db")

def get_connection():
    """
    Devuelve conexión con row_factory y FK activadas.
    """
    conn = sqlite3.connect(_db_path(), timeout=30, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # intentar optimizaciones (no críticas)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    except Exception:
        pass
    return conn

def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    return [row[1] for row in cursor.fetchall()]

def _column_exists(cursor, table, column_name):
    try:
        return column_name in _table_columns(cursor, table)
    except sqlite3.OperationalError:
        return False

def _ensure_column(cursor, table, column_def, column_name):
    """
    Añade columna si no existe. column_def debe ser una definición simple compatible con ALTER TABLE ADD COLUMN.
    Evitar constraints complejas (UNIQUE, FOREIGN KEYS) aquí.
    """
    if not _column_exists(cursor, table, column_name):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        contacto TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio REAL NOT NULL,
        stock INTEGER NOT NULL,
        sku TEXT,
        costo REAL DEFAULT 0,
        minimo_stock INTEGER DEFAULT 0,
        categoria_id INTEGER,
        proveedor_id INTEGER,
        FOREIGN KEY(categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
        FOREIGN KEY(proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS compras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER,
        fecha TEXT NOT NULL,
        total REAL NOT NULL,
        FOREIGN KEY(proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS compra_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compra_id INTEGER NOT NULL,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        precio_unitario REAL NOT NULL,
        FOREIGN KEY(compra_id) REFERENCES compras(id) ON DELETE CASCADE,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE RESTRICT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        tipo TEXT NOT NULL,
        motivo TEXT,
        fecha TEXT NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    """)

    # Tabla de ventas (si no existe se crea)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        total REAL NOT NULL,
        fecha TEXT NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE RESTRICT
    )
    """)

    # Migraciones ligeras: agregar columnas que versiones antiguas pueden no tener
    try:
        # Si la columna cliente no existe, agregarla
        _ensure_column(cursor, "ventas", "cliente TEXT", "cliente")
        # Evitar agregar UNIQUE/constraints por ALTER; si necesita UNIQUE crear índice único (si la columna existe)
        _ensure_column(cursor, "productos", "sku TEXT", "sku")
        _ensure_column(cursor, "productos", "costo REAL DEFAULT 0", "costo")
        _ensure_column(cursor, "productos", "minimo_stock INTEGER DEFAULT 0", "minimo_stock")
        _ensure_column(cursor, "productos", "categoria_id INTEGER", "categoria_id")
        _ensure_column(cursor, "productos", "proveedor_id INTEGER", "proveedor_id")
    except sqlite3.OperationalError:
        # Si una tabla no existe o ALTER falla, continuar sin abortar
        pass

    # Crear índices sólo si las columnas existen (evitar OperationalError)
    try:
        if _column_exists(cursor, "productos", "sku"):
            # índice normal sobre sku; si quieres unicidad, crear UNIQUE INDEX sólo si no hay duplicados
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku)")
    except sqlite3.OperationalError:
        pass

    try:
        if _column_exists(cursor, "movimientos_stock", "producto_id"):
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_producto ON movimientos_stock(producto_id)")
    except sqlite3.OperationalError:
        pass

    try:
        if _column_exists(cursor, "ventas", "producto_id"):
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_producto ON ventas(producto_id)")
    except sqlite3.OperationalError:
        pass

    try:
        if _column_exists(cursor, "compra_items", "producto_id"):
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_compraitems_producto ON compra_items(producto_id)")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
