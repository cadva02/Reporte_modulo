# Robot Dibujante con xArm y G-code

Script en Python que controla un brazo robótico **xArm** para dibujar imágenes a partir de archivos G-code (`.ngc`). El robot lee las trayectorias del archivo, las escala a un área de trabajo y mueve el efector final para trazar el dibujo sobre una superficie.

---

## Tabla de contenidos

- [Descripción general](#descripción-general)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Uso](#uso)
- [Parámetros configurables](#parámetros-configurables)
- [Flujo de ejecución](#flujo-de-ejecución)
- [Estructura del código](#estructura-del-código)
- [Notas y limitaciones](#notas-y-limitaciones)

---

## Descripción general

El script lee un archivo G-code (formato `.ngc`) que describe las trayectorias de una imagen vectorial. A partir de esas coordenadas XY, el brazo robótico xArm dibuja la imagen sobre una superficie plana. Las características principales son:

- **Escalado automático**: las coordenadas del G-code se escalan a un área de 200 × 200 mm centrada en la posición de inicio definida por el usuario.
- **Múltiples trayectorias y colores**: el robot hace una pausa al final de cada trayectoria para que el operador pueda cambiar el color o la pluma antes de continuar.
- **Ajuste de altura (presión)**: la altura del efector varía ligeramente según la coordenada Y original del G-code para compensar diferencias de presión en el trazo.
- **Retroalimentación en consola**: muestra el progreso línea a línea durante el dibujo.

---

## Requisitos

| Dependencia | Versión recomendada |
|---|---|
| Python | 3.7 o superior |
| [xArm Python SDK](https://github.com/xArm-Developer/xArm-Python-SDK) | >= 1.11.0 |

El SDK debe estar instalado o disponible en el `PYTHONPATH`. El script asume que se encuentra tres niveles arriba en la jerarquía de directorios respecto al script:

```
raíz_del_proyecto/
├── xarm/
│   └── wrapper/        ← SDK de xArm
└── ejemplos/
    └── common
        └── demogcode.py   ← este script
```

---

## Instalación

1. Clona el repositorio del SDK de xArm y coloca este script dentro de su estructura de directorios.
2. Asegúrate de que el archivo G-code (`.ngc`) esté en el mismo directorio que el script.

```bash
git clone https://github.com/xArm-Developer/xArm-Python-SDK.git
# Copia el script en la ubicación correcta dentro del SDK
```

---

## Uso

1. Conecta el xArm a la red y anota su dirección IP.
2. Coloca el archivo G-code de tu imagen en el mismo directorio que el script. El nombre del archivo se configura en la variable `ngc_file` al comienzo del bloque principal del script (valor predeterminado: `spidermannew_0001.ngc`); cámbialo si tu archivo tiene otro nombre.
3. Ejecuta el script:

```bash
python3 demogcode.py
```

4. Sigue las instrucciones interactivas en la consola:

   - **Ingresa la IP del xArm** cuando se solicite.
   - El robot se moverá a la posición inicial.
   - **Presiona `a`** para iniciar la calibración de altura, o cualquier otra tecla para continuar con la altura predeterminada.
   - **Presiona `q`** para comenzar el dibujo.
   - Al final de cada trayectoria (cambio de color/pluma), **presiona `r`** para continuar con la siguiente.

---

## Parámetros configurables

Los siguientes valores se pueden ajustar directamente en el código fuente:

| Parámetro | Descripción | Valor predeterminado |
|---|---|---|
| `ngc_file` | Nombre del archivo G-code a dibujar | `'spidermannew_0001.ngc'` |
| `start_x`, `start_y` | Posición XY de inicio del dibujo (mm) | `215.3`, `157.2` |
| `scale_range` | Tamaño del área de dibujo (mm) | `200.0` |
| `speed` | Velocidad de movimiento del brazo (mm/s) | `20` |
| `altura` | Offset de altura base para el efector (mm) | `1` |
| `target_z` | Altura Z calculada según la zona del dibujo | Ver código |

---

## Flujo de ejecución

```
Inicio
  │
  ├─ Conectar al xArm (IP ingresada por el usuario)
  ├─ Habilitar movimiento y establecer modo 0 (posición)
  ├─ Mover a posición inicial (start_x, start_y, z=34.5)
  │
  ├─ [Esperar 'a'] Calibración de altura
  │
  ├─ Calcular min/max XY del archivo G-code
  ├─ Calcular factores de escala para área 200x200 mm
  ├─ Contar total de trayectorias (paths)
  │
  ├─ [Esperar 'q'] Iniciar dibujo
  │
  ├─ Para cada línea del G-code:
  │     ├─ Si contiene coordenadas XY → escalar y mover el brazo
  │     └─ Si es fin de trayectoria → pausar y esperar 'r' del operador
  │
  └─ Desconectar el brazo y mostrar tiempo total
```

---

## Estructura del código

```
demogcode.py
├── Configuración de conexión al xArm
├── Movimiento a posición inicial
├── Calibración interactiva de altura
├── Análisis del archivo G-code
│   ├── Cálculo de min/max de coordenadas
│   └── Cálculo de factores de escala
├── Bucle principal de dibujo
│   ├── Escalado de coordenadas
│   ├── Cálculo de altura Z
│   └── Pausa entre trayectorias
└── Desconexión y reporte de tiempo
```

---

## Notas y limitaciones

- La detección del fin de trayectoria depende de que el archivo G-code contenga la cadena `End cutting path` en las líneas de separación.
- Asegúrate de que el área de trabajo del xArm sea suficiente para los movimientos escalados antes de ejecutar el dibujo.
