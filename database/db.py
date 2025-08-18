import sqlite3
from pathlib import Path

# ========================
# RUTAS Y CONEXIÓN
# ========================
def _db_path():
    # Carpeta 'database' donde está este archivo
    base = Path(__file__).resolve().parent
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "inventario.db")

def get_connection():
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
        conn.execute("PRAGMA cache_size = 10000")
    except Exception:
        pass
    return conn

# ========================
# CREACIÓN BASE DE TABLAS
# ========================
def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        contacto TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio_costo REAL NOT NULL DEFAULT 0,
        precio_venta REAL NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0,
        sku TEXT UNIQUE,
        minimo_stock INTEGER DEFAULT 0,
        seccion TEXT DEFAULT '',
        elemento TEXT CHECK(elemento IN ('ok', NULL)),
        metal TEXT CHECK(metal IN ('ok', NULL)),
        categoria_id INTEGER,
        proveedor_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
        FOREIGN KEY(proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS compras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER,
        fecha TEXT NOT NULL,
        total REAL NOT NULL,
        FOREIGN KEY(proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS compra_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compra_id INTEGER NOT NULL,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        precio_unitario REAL NOT NULL,
        FOREIGN KEY(compra_id) REFERENCES compras(id) ON DELETE CASCADE,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada','salida')),
        motivo TEXT,
        fecha TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        total REAL NOT NULL,
        fecha TEXT NOT NULL,
        cliente TEXT DEFAULT 'Desconocido',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    """)

    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ventas_producto_fecha ON ventas(producto_id, fecha)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha ON movimientos_stock(producto_id, fecha)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_compraitems_producto ON compra_items(producto_id)")

    conn.commit()
    conn.close()

# ========================
# MIGRACIÓN: COLUMNAS Y TRIGGERS
# ========================
def migrate_schema():
    conn = get_connection()
    cur = conn.cursor()

    # 1) Eliminar triggers viejos
    cur.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    for (tname,) in cur.fetchall():
        if tname.startswith(("trg_productos", "trg_movimientos", "trg_ventas")):
            cur.execute(f"DROP TRIGGER IF EXISTS {tname}")

    # 2) Columnas necesarias
    cols_necesarias = {
        "productos": {
            "precio_costo": "REAL DEFAULT 0",
            "precio_venta": "REAL DEFAULT 0",
            "minimo_stock": "INTEGER DEFAULT 0",
            "seccion": "TEXT DEFAULT ''",
            "elemento": "TEXT CHECK(elemento IN ('ok', NULL))",
            "metal": "TEXT CHECK(metal IN ('ok', NULL))",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        },
        "movimientos_stock": {
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        },
        "ventas": {
            "cliente": "TEXT DEFAULT 'Desconocido'",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        },
    }

    for tabla, defs in cols_necesarias.items():
        existentes = {r["name"] for r in cur.execute(f"PRAGMA table_info({tabla})")}
        for col, ddl in defs.items():
            if col not in existentes:
                cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {ddl}")

    # 3) Triggers seguros para updated_at (SQLite compatible)
    cur.executescript("""
    CREATE TRIGGER IF NOT EXISTS trg_productos_updated_at
    AFTER UPDATE ON productos
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
    BEGIN
      UPDATE productos
      SET updated_at = CURRENT_TIMESTAMP
      WHERE id = NEW.id;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_movimientos_updated_at
    AFTER UPDATE ON movimientos_stock
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
    BEGIN
      UPDATE movimientos_stock
      SET updated_at = CURRENT_TIMESTAMP
      WHERE id = NEW.id;
    END;

    CREATE TRIGGER IF NOT EXISTS trg_ventas_updated_at
    AFTER UPDATE ON ventas
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
    BEGIN
      UPDATE ventas
      SET updated_at = CURRENT_TIMESTAMP
      WHERE id = NEW.id;
    END;
    """)

    conn.commit()
    conn.close()

# ========================
# INICIALIZACIÓN
# ========================
if __name__ == "__main__":
    create_tables()
    migrate_schema()
    print("Esquema de base de datos creado y migrado correctamente con triggers seguros.")
