from database.db import get_connection

# ====== UTILIDAD DE VALIDACIÓN ======
def _normalizar_nombre(nombre):
    """Normaliza y valida el nombre de una categoría."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre de la categoría no puede estar vacío")
    return nombre


# ====== OBTENER CATEGORÍAS ======
def obtener_categorias():
    """
    Retorna todas las categorías como lista de tuplas (id, nombre),
    ordenadas alfabéticamente por nombre.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre
            FROM categorias
            ORDER BY nombre COLLATE NOCASE
        """)
        filas = cursor.fetchall()
    return [tuple(r) for r in filas] if filas else []


# ====== AGREGAR CATEGORÍA ======
def agregar_categoria(nombre):
    """
    Agrega una nueva categoría si no existe y el nombre no está vacío.
    Lanza ValueError si el nombre ya existe o es inválido.
    """
    nombre = _normalizar_nombre(nombre)

    with get_connection() as conn:
        cursor = conn.cursor()
        # Verificar duplicado
        cursor.execute("SELECT 1 FROM categorias WHERE LOWER(nombre) = LOWER(?)", (nombre,))
        if cursor.fetchone():
            raise ValueError(f"La categoría '{nombre}' ya existe")

        cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
        conn.commit()
    return True


# ====== ELIMINAR CATEGORÍA ======
def eliminar_categoria(id_categoria):
    """
    Elimina la categoría indicada si no está asignada a ningún producto.
    Lanza ValueError si existen productos asociados o la categoría no existe.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Verificar que exista
        cursor.execute("SELECT 1 FROM categorias WHERE id = ?", (id_categoria,))
        if not cursor.fetchone():
            raise ValueError(f"La categoría con ID {id_categoria} no existe")

        # Verificar productos asociados
        cursor.execute("SELECT COUNT(*) FROM productos WHERE categoria_id = ?", (id_categoria,))
        if cursor.fetchone()[0] > 0:
            raise ValueError("No se puede eliminar: existen productos asignados a esta categoría")

        cursor.execute("DELETE FROM categorias WHERE id = ?", (id_categoria,))
        conn.commit()
    return True
