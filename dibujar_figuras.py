from __future__ import annotations

import math


def dibujar_cuadrado(controlador, robot_work, lado) -> None:
    """Dibuja un cuadrado iniciando desde la posición de trabajo."""
    if controlador.arm is None:
        controlador._actualizar_estado_robot("modo local")
        return

    try:
        controlador._actualizar_estado_robot("dibujando cuadrado...")
        x0, y0, z0, roll0, pitch0, yaw0 = robot_work
        controlador.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        puntos = [
            (x0, y0),
            (x0 + lado, y0),
            (x0 + lado, y0 + lado),
            (x0, y0 + lado),
            (x0, y0),
        ]

        for x, y in puntos:
            controlador.arm.set_position(x=x, y=y, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        controlador._robot_pose = [x0, y0, z0, roll0, pitch0, yaw0]
        controlador._actualizar_estado_robot("cuadrado dibujado")
    except Exception as exc:
        controlador._actualizar_estado_robot(f"error: {exc}")


def dibujar_circulo(controlador, robot_work, diametro) -> None:
    """Dibuja un círculo iniciando desde la posición de trabajo."""
    if controlador.arm is None:
        controlador._actualizar_estado_robot("modo local")
        return

    try:
        controlador._actualizar_estado_robot("dibujando círculo...")
        x0, y0, z0, roll0, pitch0, yaw0 = robot_work
        controlador.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        radio = diametro / 2
        pasos = 60
        puntos = []
        for i in range(pasos + 1):
            angulo = (i * 360 / pasos) * math.pi / 180
            x = x0 + radio * math.cos(angulo)
            y = y0 + radio * math.sin(angulo)
            puntos.append((x, y))

        for x, y in puntos:
            controlador.arm.set_position(x=x, y=y, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        controlador._robot_pose = [x0, y0, z0, roll0, pitch0, yaw0]
        controlador._actualizar_estado_robot("círculo dibujado")
    except Exception as exc:
        controlador._actualizar_estado_robot(f"error: {exc}")


def dibujar_triangulo(controlador, robot_work, lado) -> None:
    """Dibuja un triángulo equilátero iniciando desde la posición de trabajo."""
    if controlador.arm is None:
        controlador._actualizar_estado_robot("modo local")
        return

    try:
        controlador._actualizar_estado_robot("dibujando triángulo...")
        x0, y0, z0, roll0, pitch0, yaw0 = robot_work
        controlador.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        altura = lado * math.sqrt(3) / 2
        puntos = [
            (x0, y0),
            (x0 + lado / 2, y0 - altura / 2),
            (x0 - lado / 2, y0 - altura / 2),
            (x0, y0),
        ]

        for x, y in puntos:
            controlador.arm.set_position(x=x, y=y, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        controlador._robot_pose = [x0, y0, z0, roll0, pitch0, yaw0]
        controlador._actualizar_estado_robot("triángulo dibujado")
    except Exception as exc:
        controlador._actualizar_estado_robot(f"error: {exc}")