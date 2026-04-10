#!/usr/bin/env python3
import os
import sys
import time
import re

sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))
from xarm.wrapper import XArmAPI

# ... (Mantenemos la sección de configuración de IP igual) ...
ip = input('Please input the xArm ip address:')
if not ip:
    sys.exit(1)

arm = XArmAPI(ip)
arm.motion_enable(enable=True)
arm.set_mode(0)
arm.set_state(state=0)

# arm.move_gohome(wait=True)

# Posiciones iniciales de prueba
# arm.set_position(x=100, y=-50, z=250, roll=180, pitch=0, yaw=0, speed=100, wait=True)
arm.set_position(x=215.3, y=157.2, z=34.5, roll=180, pitch=0, yaw=0, speed=20, wait=True)

cont = 0
x = 's'
print("Presiona 'a' para iniciar la calibración de altura o cualquier tecla para continuar")
while x != "a":
    x = input()

start_time = time.time()
altura = 1

# Archivo a procesar
ngc_file = 'spidermannew_0001.ngc'

# Calcular total de líneas
with open(ngc_file, 'r') as fp:
    total_lines = sum(1 for line in fp)
print(f'Total Number of lines: {total_lines}')

# Posición inicial deseada
start_x, start_y = 215.3, 157.2

print("Presiona 'q' para comenzar el dibujo.")
input_key = 's'
while input_key != "q":
    input_key = input()

print("--- Iniciando dibujo ---")

# Calcular min/max de coordenadas en el archivo
min_x = float('inf')
max_x = float('-inf')
min_y = float('inf')
max_y = float('-inf')
with open(ngc_file) as gcode:
    for line in gcode:
        coords = re.findall(r'[XY][+-]?\d+\.\d+', line)
        if len(coords) >= 2:
            xx = float(re.findall(r'[+-]?\d+\.\d+', coords[0])[0])
            yy = float(re.findall(r'[+-]?\d+\.\d+', coords[1])[0])
            min_x = min(min_x, xx)
            max_x = max(max_x, xx)
            min_y = min(min_y, yy)
            max_y = max(max_y, yy)

# Escalar a un área de 200x200 mm centrada en start_x, start_y
scale_range = 200.0
x_range = max_x - min_x if max_x > min_x else 1
y_range = max_y - min_y if max_y > min_y else 1
scale_x = scale_range / x_range
scale_y = scale_range / y_range

# Contar total de paths
total_paths = 0
with open(ngc_file) as gcode:
    for line in gcode:
        if "End cutting path" in line:
            total_paths += 1
print(f'Total paths: {total_paths}')

# Procesar el archivo
current_path = 1
skip_mode = (current_path == total_paths)
with open(ngc_file) as gcode:
    for line in gcode:
        line = line.strip()
        
        # --- NUEVA LÓGICA DE DETECCIÓN DE FIN DE PATH ---
        if "End cutting path" in line:
            if current_path < total_paths:
                print("\n[PAUSA] Fin de trayectoria detectado.")
                
                # Esperar interacción del usuario
                wait_key = ""
                while wait_key.lower() != 'r':
                    wait_key = input(">>> Trayectoria terminada. Cambia el color/pluma y presiona 'r' para continuar: ")
                
                print("Siguiente trayectoria iniciada...")
            current_path += 1
            skip_mode = (current_path == total_paths)
            continue # Saltar a la siguiente línea del archivo
        
        # --- PROCESAMIENTO DE COORDENADAS ---
        if not skip_mode:
            coord = re.findall(r'[XY][+-]?\d+\.\d+', line)
            if len(coord) >= 2: # Aseguramos que existan al menos X e Y
                # Extraer valores numéricos
                xx = re.findall(r'[+-]?\d+\.\d+', coord[0])[0]
                yy = re.findall(r'[+-]?\d+\.\d+', coord[1])[0]
                
                # Lógica de dibujo según altura definida previamente
                scaled_x = (float(xx) - min_x) * scale_x - scale_range / 2 + start_x
                scaled_y = (float(yy) - min_y) * scale_y - scale_range / 2 + start_y
                target_x = scaled_x
                target_y = scaled_y
                if float(yy) > 150:
                    target_z = 31 - altura
                elif 50 < float(yy) <= 150:
                    target_z = 31 - altura - 1
                else:
                    target_z = 31 - altura - 2
                
                arm.set_position(x=target_x, y=target_y, z=target_z, roll=180, pitch=0, yaw=0, speed=20, wait=True)
                
                cont += 1
                if cont % 100 == 0:
                    print(f"{cont} líneas procesadas. Restan: {total_lines - cont}", end="\r")

print("\n--- Dibujo Finalizado ---")
print("Tiempo total: %s segundos" % (time.time() - start_time))

arm.disconnect()