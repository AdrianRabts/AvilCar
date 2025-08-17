import sqlite3
from pathlib import Path

# ========================
# RUTAS Y CONEXIÓN
# ========================
def _db_path():
    base = Path(__file__).resolve().parents[1]
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "inventario.db")

def get_connection():
    """
    Devuelve conexión SQLite con:
    - FK activadas
    - Row factory tipo dict
    - WAL + synchronous NORMAL
    """
    conn = sqlite3.connect(
        _db_path(),
        timeout=30,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = 10000")  # mejora lectura
    except Exception:
        pass
    return conn

# ========================
# UTILIDADES INTERNAS
# ========================
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
    Añade columna si no existe. Evitar constraints complejas aquí.
    """
    if not _column_exists(cursor, table, column_name):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")

# ========================
# CREACIÓN DE TABLAS
# ========================
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # Metadata (versionamiento)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES ('version', '2')")

    # Categorías
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
    )
    """)

    # Proveedores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        contacto TEXT
    )
    """)

    # Productos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio REAL NOT NULL,
        stock INTEGER NOT NULL,
        sku TEXT UNIQUE,
        costo REAL DEFAULT 0,
        minimo_stock INTEGER DEFAULT 0,
        categoria_id INTEGER,
        proveedor_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
        FOREIGN KEY(proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
    )
    """)

    # Trigger automático para actualizar `updated_at`
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_productos_updated_at
    AFTER UPDATE ON productos
    FOR EACH ROW
    BEGIN
        UPDATE productos SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
    """)

    # Compras y compra_items
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

    # Movimientos de stock
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada','salida')),
        motivo TEXT,
        fecha TEXT NOT NULL,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    """)

    # Ventas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        total REAL NOT NULL,
        fecha TEXT NOT NULL,
        cliente TEXT DEFAULT 'Desconocido',
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE RESTRICT
    )
    """)

    # ========================
    # ÍNDICES
    # ========================
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_producto_fecha ON ventas(producto_id, fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha ON movimientos_stock(producto_id, fecha)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_compraitems_producto ON compra_items(producto_id)")

    conn.commit()
    conn.close()
    return True