from database.db import get_connection

def obtener_categorias():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
    filas = cursor.fetchall()
    conn.close()
    return [tuple(r) for r in filas]

def agregar_categoria(nombre):
    if not nombre or not nombre.strip():
        raise ValueError("Nombre de categoría vacío")
    conn = get_connection()
    cursor = conn.cursor()
    # comprobar duplicado
    cursor.execute("SELECT id FROM categorias WHERE nombre = ?", (nombre.strip(),))
    if cursor.fetchone():
        conn.close()
        raise ValueError("La categoría ya existe")
    cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre.strip(),))
    conn.commit()
    conn.close()

def eliminar_categoria(id_categoria):
    conn = get_connection()
    cursor = conn.cursor()
    # antes de eliminar, opcional: comprobar si productos usan esta categoría
    cursor.execute("SELECT COUNT(*) FROM productos WHERE categoria_id = ?", (id_categoria,))
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        raise ValueError("No se puede eliminar: existen productos asignados a esta categoría")
    cursor.execute("DELETE FROM categorias WHERE id = ?", (id_categoria,))
    conn.commit()
    conn.close()
