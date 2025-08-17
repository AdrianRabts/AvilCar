# C:\Users\User\Desktop\InventarioAvilCar\AvilCar\models\categoria.py

from database.db import get_connection

def obtener_categorias():
    """
    Retorna todas las categorías como lista de tuplas (id, nombre),
    ordenadas alfabéticamente por nombre.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        filas = cursor.fetchall()
    return [tuple(r) for r in filas]

def agregar_categoria(nombre):
    """
    Agrega una nueva categoría si no existe y el nombre no está vacío.
    Lanza ValueError en caso de error.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre de la categoría no puede estar vacío")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categorias WHERE nombre = ?", (nombre,))
        if cursor.fetchone():
            raise ValueError("La categoría ya existe")
        cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
        conn.commit()

def eliminar_categoria(id_categoria):
    """
    Elimina la categoría indicada si no está asignada a ningún producto.
    Lanza ValueError si existen productos asociados.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM productos WHERE categoria_id = ?", (id_categoria,))
        if cursor.fetchone()[0] > 0:
            raise ValueError("No se puede eliminar: existen productos asignados a esta categoría")
        cursor.execute("DELETE FROM categorias WHERE id = ?", (id_categoria,))
        conn.commit()
