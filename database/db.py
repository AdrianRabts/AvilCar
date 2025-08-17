import sqlite3
from pathlib import Path
import json

# ========================
# RUTAS Y CONEXIÓN
# ========================
def _db_path():
    base = Path(__file__).resolve().parents[1]
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
    if not _column_exists(cursor, table, column_name):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")

# ========================
# CREACIÓN DE TABLAS
# ========================
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # ========================
    # TABLAS BASE
    # ========================
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
    # Trigger updated_at
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_productos_updated_at
    AFTER UPDATE ON productos
    FOR EACH ROW
    BEGIN
        UPDATE productos SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
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
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada','salida')),
        motivo TEXT,
        fecha TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_movimientos_updated_at
    AFTER UPDATE ON movimientos_stock
    FOR EACH ROW
    BEGIN
        UPDATE movimientos_stock SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        total REAL NOT NULL,
        fecha TEXT NOT NULL,
        cliente TEXT DEFAULT 'Desconocido',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE RESTRICT
    )
    """)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_ventas_updated_at
    AFTER UPDATE ON ventas
    FOR EACH ROW
    BEGIN
        UPDATE ventas SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
    """)

    # ========================
    # TABLA DE AUDITORÍA GLOBAL
    # ========================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tabla TEXT NOT NULL,
        operacion TEXT NOT NULL CHECK(operacion IN ('INSERT','UPDATE','DELETE')),
        registro_id INTEGER,
        datos_antes TEXT,
        datos_despues TEXT,
        usuario TEXT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ========================
    # TRIGGERS DE AUDITORÍA
    # ========================
    for tabla in ["productos", "ventas", "movimientos_stock"]:
        # INSERT
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_{tabla}_insert_auditoria
        AFTER INSERT ON {tabla}
        FOR EACH ROW
        BEGIN
            INSERT INTO auditoria(tabla, operacion, registro_id, datos_antes, datos_despues, usuario)
            VALUES ('{tabla}', 'INSERT', NEW.id, NULL, json(NEW), 'Sistema');
        END;
        """)
        # UPDATE
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_{tabla}_update_auditoria
        AFTER UPDATE ON {tabla}
        FOR EACH ROW
        BEGIN
            INSERT INTO auditoria(tabla, operacion, registro_id, datos_antes, datos_despues, usuario)
            VALUES ('{tabla}', 'UPDATE', NEW.id, json(OLD), json(NEW), 'Sistema');
        END;
        """)
        # DELETE
        cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS trg_{tabla}_delete_auditoria
        AFTER DELETE ON {tabla}
        FOR EACH ROW
        BEGIN
            INSERT INTO auditoria(tabla, operacion, registro_id, datos_antes, datos_despues, usuario)
            VALUES ('{tabla}', 'DELETE', OLD.id, json(OLD), NULL, 'Sistema');
        END;
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