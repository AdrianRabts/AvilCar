import os
import sqlite3
import shutil
from pathlib import Path

APP_NAME = "AvilCar"

# ========================
# RUTAS Y CONEXIÓN
# ========================
def _db_path():
    # Carpeta de datos del usuario
    base = Path(os.getenv("APPDATA")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)

    db_file = base / "inventario.db"

    # Si no existe la BD en AppData, copiamos una plantilla
    plantilla = Path(__file__).resolve().parent / "inventario.db"
    if not db_file.exists():
        if plantilla.exists():
            shutil.copy(plantilla, db_file)
        else:
            # Crea un archivo vacío si no hay plantilla
            db_file.touch()

    return str(db_file)


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
        producto_id INTEGER,
        producto_nombre TEXT DEFAULT '',
        producto_sku TEXT DEFAULT '',
        cantidad INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada','salida')),
        motivo TEXT,
        fecha TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE SET NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        producto_nombre TEXT DEFAULT '',
        producto_sku TEXT DEFAULT '',
        cantidad INTEGER NOT NULL,
        total REAL NOT NULL,
        fecha TEXT NOT NULL,
        cliente TEXT DEFAULT 'Desconocido',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE SET NULL
    )
    """)

    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ventas_producto_fecha ON ventas(producto_id, fecha)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha ON movimientos_stock(producto_id, fecha)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_compraitems_producto ON compra_items(producto_id)")

    conn.commit()
    conn.close()


def _has_fk_set_null(cur: sqlite3.Cursor, table_name: str) -> bool:
    fks = cur.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    for fk in fks:
        # id, seq, table, from, to, on_update, on_delete, match
        if fk[2] == "productos" and fk[3] == "producto_id":
            return str(fk[6]).upper() == "SET NULL"
    return False


def _column_is_nullable(cur: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cols = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    for col in cols:
        # cid, name, type, notnull, dflt_value, pk
        if col[1] == column_name:
            return int(col[3]) == 0
    return False


def _rebuild_ventas_table(cur: sqlite3.Cursor):
    cur.executescript("""
    ALTER TABLE ventas RENAME TO ventas_old;
    CREATE TABLE ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        producto_nombre TEXT DEFAULT '',
        producto_sku TEXT DEFAULT '',
        cantidad INTEGER NOT NULL,
        total REAL NOT NULL,
        fecha TEXT NOT NULL,
        cliente TEXT DEFAULT 'Desconocido',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE SET NULL
    );
    """)

    old_cols = {r["name"] for r in cur.execute("PRAGMA table_info(ventas_old)")}
    has_nombre = "producto_nombre" in old_cols
    has_sku = "producto_sku" in old_cols

    nombre_expr = "COALESCE(v.producto_nombre, p.nombre, 'Producto eliminado')" if has_nombre else "COALESCE(p.nombre, 'Producto eliminado')"
    sku_expr = "COALESCE(v.producto_sku, p.sku, '')" if has_sku else "COALESCE(p.sku, '')"

    cur.execute(f"""
        INSERT INTO ventas (
            id, producto_id, producto_nombre, producto_sku,
            cantidad, total, fecha, cliente, created_at, updated_at
        )
        SELECT
            v.id,
            v.producto_id,
            {nombre_expr},
            {sku_expr},
            v.cantidad,
            v.total,
            v.fecha,
            COALESCE(v.cliente, 'Desconocido'),
            COALESCE(v.created_at, CURRENT_TIMESTAMP),
            COALESCE(v.updated_at, CURRENT_TIMESTAMP)
        FROM ventas_old v
        LEFT JOIN productos p ON p.id = v.producto_id
        ORDER BY v.id
    """)

    cur.execute("DROP TABLE ventas_old")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ventas_producto_fecha ON ventas(producto_id, fecha)")


def _rebuild_movimientos_table(cur: sqlite3.Cursor):
    cur.executescript("""
    ALTER TABLE movimientos_stock RENAME TO movimientos_stock_old;
    CREATE TABLE movimientos_stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER,
        producto_nombre TEXT DEFAULT '',
        producto_sku TEXT DEFAULT '',
        cantidad INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('entrada','salida')),
        motivo TEXT,
        fecha TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE SET NULL
    );
    """)

    old_cols = {r["name"] for r in cur.execute("PRAGMA table_info(movimientos_stock_old)")}
    has_nombre = "producto_nombre" in old_cols
    has_sku = "producto_sku" in old_cols

    nombre_expr = "COALESCE(m.producto_nombre, p.nombre, 'Producto eliminado')" if has_nombre else "COALESCE(p.nombre, 'Producto eliminado')"
    sku_expr = "COALESCE(m.producto_sku, p.sku, '')" if has_sku else "COALESCE(p.sku, '')"

    cur.execute(f"""
        INSERT INTO movimientos_stock (
            id, producto_id, producto_nombre, producto_sku,
            cantidad, tipo, motivo, fecha, created_at, updated_at
        )
        SELECT
            m.id,
            m.producto_id,
            {nombre_expr},
            {sku_expr},
            m.cantidad,
            m.tipo,
            m.motivo,
            m.fecha,
            COALESCE(m.created_at, CURRENT_TIMESTAMP),
            COALESCE(m.updated_at, CURRENT_TIMESTAMP)
        FROM movimientos_stock_old m
        LEFT JOIN productos p ON p.id = m.producto_id
        ORDER BY m.id
    """)

    cur.execute("DROP TABLE movimientos_stock_old")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha ON movimientos_stock(producto_id, fecha)")


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
            "producto_nombre": "TEXT DEFAULT ''",
            "producto_sku": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
        },
        "ventas": {
            "producto_nombre": "TEXT DEFAULT ''",
            "producto_sku": "TEXT DEFAULT ''",
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

    # 3) Rebuild tablas históricas para conservar ventas/movimientos cuando se elimina un producto
    #    y dejar FK como ON DELETE SET NULL.
    needs_rebuild_ventas = (not _has_fk_set_null(cur, "ventas")) or (not _column_is_nullable(cur, "ventas", "producto_id"))
    needs_rebuild_movs = (not _has_fk_set_null(cur, "movimientos_stock")) or (not _column_is_nullable(cur, "movimientos_stock", "producto_id"))

    if needs_rebuild_ventas or needs_rebuild_movs:
        cur.execute("PRAGMA foreign_keys = OFF")
        try:
            if needs_rebuild_ventas:
                _rebuild_ventas_table(cur)
            if needs_rebuild_movs:
                _rebuild_movimientos_table(cur)
        finally:
            cur.execute("PRAGMA foreign_keys = ON")

    # 4) Backfill nombres/SKU históricos faltantes (sin sobreescribir datos ya guardados)
    cur.execute("""
        UPDATE ventas
        SET producto_nombre = COALESCE(NULLIF(producto_nombre, ''), (
                SELECT COALESCE(nombre, 'Producto eliminado')
                FROM productos p WHERE p.id = ventas.producto_id
            ), 'Producto eliminado'),
            producto_sku = COALESCE(NULLIF(producto_sku, ''), (
                SELECT COALESCE(sku, '')
                FROM productos p WHERE p.id = ventas.producto_id
            ), '')
    """)

    cur.execute("""
        UPDATE movimientos_stock
        SET producto_nombre = COALESCE(NULLIF(producto_nombre, ''), (
                SELECT COALESCE(nombre, 'Producto eliminado')
                FROM productos p WHERE p.id = movimientos_stock.producto_id
            ), 'Producto eliminado'),
            producto_sku = COALESCE(NULLIF(producto_sku, ''), (
                SELECT COALESCE(sku, '')
                FROM productos p WHERE p.id = movimientos_stock.producto_id
            ), '')
    """)

    # 5) Triggers seguros para updated_at
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
    print("Esquema de base de datos creado y migrado correctamente en AppData.")
