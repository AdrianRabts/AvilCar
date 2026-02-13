# AvilCar

## Ejecutar en modo desarrollo

> Sí, después de hacer cambios conviene correr `main.py` para probar que todo funciona antes de generar el `.exe`.

```bash
# 1) Instalar dependencias (una vez)
py -m pip install --upgrade pip
py -m pip install matplotlib pyinstaller

# 2) Ejecutar la app en desarrollo
py main.py
```

## Generar el `.exe` para entregar al cliente

```bash
# Desde la raíz del proyecto
py -m PyInstaller --onefile --windowed main.py
```

El ejecutable queda en:

- `dist/main.exe`

## Flujo recomendado cada vez que hagas cambios

1. Editar código.
2. Probar con `py main.py`.
3. Si todo está bien, regenerar `.exe` con PyInstaller.
4. Probar `dist/main.exe`.

## Datos de inventario (persistencia)

La base de datos **no** se guarda dentro del `.exe`.
Se guarda en `%APPDATA%\AvilCar\inventario.db`, por lo que el cliente mantiene sus datos entre ejecuciones.


## Si GitHub bloquea el merge por conflictos

Puedes resolverlo desde GitHub si aparece **Resolve conflicts**. Si no aparece, hazlo local:

```bash
git fetch origin
git checkout work
git merge origin/main
# Resolver conflictos en archivos, luego:
git add .
git commit -m "Resolve merge conflicts with main"
git push origin work
```

> Si tu rama destino es `master`, cambia `origin/main` por `origin/master`.
