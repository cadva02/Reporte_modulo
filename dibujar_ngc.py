from __future__ import annotations

import re


def dibujar_archivo_ngc(controlador, robot_work) -> None:
    """Dibuja la trayectoria del archivo NGC seleccionado."""
    if controlador._archivo_ngc is None:
        controlador._actualizar_estado_robot("error: no hay archivo seleccionado")
        return

    if controlador.arm is None:
        controlador._actualizar_estado_robot("modo local")
        return

    try:
        controlador._actualizar_estado_robot("dibujando archivo...")
        x0, y0, z0, roll0, pitch0, yaw0 = robot_work
        controlador.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

        lineas_procesadas = 0
        try:
            with open(controlador._archivo_ngc, 'r') as gcode:
                origen_archivo = None
                for line in gcode:
                    line = line.strip()
                    coord = re.findall(r'[XY]-?\d+\.?\d*', line)
                    if coord:
                        xx = None
                        yy = None

                        for c in coord:
                            if c.startswith('X'):
                                xx = float(c[1:])
                            elif c.startswith('Y'):
                                yy = float(c[1:])

                        if xx is not None and yy is not None:
                            if origen_archivo is None:
                                origen_archivo = (xx, yy)
                                target_x = x0
                                target_y = y0
                            else:
                                dx = xx - origen_archivo[0]
                                dy = yy - origen_archivo[1]
                                target_x = x0 + dx
                                target_y = y0 + dy

                            controlador.arm.set_position(
                                x=target_x,
                                y=target_y,
                                z=z0,
                                roll=roll0,
                                pitch=pitch0,
                                yaw=yaw0,
                                speed=100,
                                wait=True,
                            )
                            controlador._robot_pose = [target_x, target_y, z0, roll0, pitch0, yaw0]
                            lineas_procesadas += 1

            controlador._actualizar_estado_robot(f"archivo dibujado: {lineas_procesadas} puntos")
            try:
                if controlador.arm is not None:
                    controlador.arm.set_position(*robot_work, speed=20, wait=True)
                    controlador._robot_pose = list(robot_work)
                    controlador._archivo_ngc = None
                    try:
                        controlador.ui.archivo_texto.setText("")
                    except Exception:
                        pass
                    controlador._actualizar_estado_robot("regresado a ROBOT_WORK")
            except Exception as exc:
                controlador._actualizar_estado_robot(f"error al regresar a ROBOT_WORK: {exc}")
        except FileNotFoundError:
            controlador._actualizar_estado_robot("error: archivo no encontrado")
        except Exception as exc:
            controlador._actualizar_estado_robot(f"error leyendo archivo: {exc}")
    except Exception as exc:
        controlador._actualizar_estado_robot(f"error: {exc}")