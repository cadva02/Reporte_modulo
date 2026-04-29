from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
import sys
from typing import Callable
import math
import subprocess
from pathlib import Path
import os
import re

from PyQt5 import QtCore, QtGui, QtWidgets

from Lite6 import Ui_MainWindow
from movimientos import Abajo, Arriba, Derecha, Izquierda, Posicion
from vision_detection import VisionDetectionController

try:
    from xarm.wrapper import XArmAPI
except ImportError:
    XArmAPI = None

os.environ["QT_QPA_PLATFORMTHEME"] = "xdgdesktopportal"
ROBOT_HOME = (281.7, 0.80, 121.8, 171.0, 6.7, 125.9)
ROBOT_WORK = (303.2, -17, 87.5, 174.4, 1.2, 88.3)
ROBOT_STEP_MM = 10.0

# Dimensiones de las figuras en mm (convertidas de cm)
CUADRADO_LADO = 50  # 15 cm
CIRCULO_DIAMETRO = 50  # 10 cm (radio = 50)
TRIANGULO_LADO = 50  # 10 cm


class VentanaControl(QtWidgets.QMainWindow):
    def __init__(self, ip_robot: str) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.posicion = Posicion(0, 0)
        self._robot_pose = list(ROBOT_HOME)
        self.arm = None
        self._archivo_ngc: str | None = None
        self._movimiento_activo: tuple[str, Callable[[Posicion], Posicion]] | None = None
        self._vision_controller: VisionDetectionController | None = None
        self._hold_timer = QtCore.QTimer(self)
        self._hold_timer.setInterval(100)
        self._hold_timer.timeout.connect(self._ejecutar_continuo)

        self._hold_delay = QtCore.QTimer(self)
        self._hold_delay.setSingleShot(True)
        self._hold_delay.setInterval(300)
        self._hold_delay.timeout.connect(self._iniciar_repeticion)

        self._crear_indicadores()
        self._crear_vista_camara()
        self.arm = self._conectar_robot(ip_robot)
        self._conectar_botones()
        self._actualizar_vista()

    def _crear_indicadores(self) -> None:
        self.lbl_posicion = QtWidgets.QLabel("Posicion: (0, 0)", self.ui.centralwidget)
        self.lbl_posicion.setGeometry(30, 225, 300, 24)
        self.lbl_posicion.setStyleSheet("color: white; font-weight: bold;")

        self.lbl_robot = QtWidgets.QLabel("Robot: desconectado", self.ui.centralwidget)
        self.lbl_robot.setGeometry(30, 250, 380, 24)
        self.lbl_robot.setStyleSheet("color: white; font-weight: bold;")

    def _crear_vista_camara(self) -> None:
        self.camera_label = QtWidgets.QLabel(self.ui.frame)
        self.camera_label.setGeometry(0, 0, self.ui.frame.width(), self.ui.frame.height())
        self.camera_label.setAlignment(QtCore.Qt.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #000; color: white;")
        self.camera_label.setText("Camara apagada")

    def _conectar_botones(self) -> None:
        self.ui.B_arriba.pressed.connect(
            lambda: self._iniciar_movimiento_continuo("arriba", Arriba().ejecutar)
        )
        self.ui.B_der.pressed.connect(
            lambda: self._iniciar_movimiento_continuo("derecha", Derecha().ejecutar)
        )
        self.ui.B_abaj.pressed.connect(
            lambda: self._iniciar_movimiento_continuo("abajo", Abajo().ejecutar)
        )
        self.ui.B_Izq.pressed.connect(
            lambda: self._iniciar_movimiento_continuo("izquierda", Izquierda().ejecutar)
        )

        self.ui.B_arriba.released.connect(self._detener_movimiento_continuo)
        self.ui.B_der.released.connect(self._detener_movimiento_continuo)
        self.ui.B_abaj.released.connect(self._detener_movimiento_continuo)
        self.ui.B_Izq.released.connect(self._detener_movimiento_continuo)

        self.ui.TrianguloButton.clicked.connect(self._dibujar_triangulo)
        self.ui.CuadradoButton.clicked.connect(self._dibujar_cuadrado)
        self.ui.CirculoButton.clicked.connect(self._dibujar_circulo)

        self.ui.SubirButton.clicked.connect(self._seleccionar_archivo)
        self.ui.DibujarButton_2.clicked.connect(self._dibujar_archivo_ngc)
        self.ui.pushButton_2.clicked.connect(self._activar_auto)
        self.ui.pushButton.clicked.connect(self._desactivar_manual)

    def _activar_auto(self) -> None:
        if self._vision_controller is None:
            self._vision_controller = VisionDetectionController(
                self.camera_label,
                status_callback=self._actualizar_estado_robot,
                parent=self,
            )

        self._vision_controller.start()

    def _desactivar_manual(self) -> None:
        if self._vision_controller is not None:
            self._vision_controller.stop()

    def _iniciar_movimiento_continuo(
        self, nombre: str, accion: Callable[[Posicion], Posicion]
    ) -> None:
        self._movimiento_activo = (nombre, accion)
        self._ejecutar(nombre, accion)
        self._hold_delay.start()

    def _iniciar_repeticion(self) -> None:
        if self._movimiento_activo is not None:
            self._hold_timer.start()

    def _ejecutar_continuo(self) -> None:
        if self._movimiento_activo is None:
            return

        nombre, accion = self._movimiento_activo
        self._ejecutar(nombre, accion)

    def _detener_movimiento_continuo(self) -> None:
        self._hold_delay.stop()
        self._hold_timer.stop()
        self._movimiento_activo = None

    def _ejecutar(self, nombre: str, accion: Callable[[Posicion], Posicion]) -> None:
        self.posicion = accion(self.posicion)
        self._mover_robot(nombre)
        self._actualizar_vista()

    def _obtener_ip_robot(self) -> str | None:
        if len(sys.argv) >= 2 and sys.argv[1].strip():
            return sys.argv[1].strip()

        ruta_config = Path(__file__).resolve().parents[2] / "robot.conf"
        if ruta_config.exists():
            parser = ConfigParser()
            parser.read(ruta_config)
            if parser.has_option("xArm", "ip"):
                return parser.get("xArm", "ip").strip()

        return None

    def _conectar_robot(self, ip: str):
        if XArmAPI is None:
            self._actualizar_estado_robot("modo local: xArm API no disponible")
            return None

        try:
            arm = XArmAPI(ip)
            arm.motion_enable(enable=True)
            arm.set_mode(0)
            arm.set_state(state=0)
            arm.set_position(*ROBOT_HOME, speed=20, wait=True)
            self._robot_pose = list(ROBOT_HOME)
            self._actualizar_estado_robot(f"conectado: {ip}")
            return arm
        except Exception as exc:
            self._actualizar_estado_robot(f"modo local: {exc}")
            return None

    def _actualizar_estado_robot(self, texto: str) -> None:
        if hasattr(self, "lbl_robot"):
            self.lbl_robot.setText(f"Robot: {texto}")

    def _mover_robot(self, nombre: str) -> None:
        if self.arm is None:
            self._actualizar_estado_robot("modo local")
            return

        x, y, z, roll, pitch, yaw = self._robot_pose
        if nombre == "arriba":
            y += ROBOT_STEP_MM
        elif nombre == "abajo":
            y -= ROBOT_STEP_MM
        elif nombre == "derecha":
            x += ROBOT_STEP_MM
        elif nombre == "izquierda":
            x -= ROBOT_STEP_MM

        try:
            self.arm.set_position(
                x=x,
                y=y,
                z=z,
                roll=roll,
                pitch=pitch,
                yaw=yaw,
                speed=20,
                wait=True,
            )
            self._robot_pose = [x, y, z, roll, pitch, yaw]
            self._actualizar_estado_robot("moviendo")
        except Exception as exc:
            self._actualizar_estado_robot(f"error: {exc}")

    def _actualizar_vista(self) -> None:
        self.lbl_posicion.setText(f"Posicion: ({self.posicion.x}, {self.posicion.y})")

    def _seleccionar_archivo(self) -> None:
        """Abre un diálogo de selección de archivos nativo del OS"""
        archivo, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo NGC",
            str(Path.home()),
            "Archivos NGC (*.ngc);;Todos los archivos (*)"
        )

        if archivo:
            self._archivo_ngc = archivo
            nombre_archivo = Path(archivo).name
            self.ui.archivo_texto.setText(nombre_archivo)
            self._actualizar_estado_robot(f"archivo cargado: {nombre_archivo}")

    def _dibujar_archivo_ngc(self) -> None:
        """Dibuja la trayectoria del archivo NGC seleccionado"""
        if self._archivo_ngc is None:
            self._actualizar_estado_robot("error: no hay archivo seleccionado")
            return

        if self.arm is None:
            self._actualizar_estado_robot("modo local")
            return

        try:
            self._actualizar_estado_robot("dibujando archivo...")
            x0, y0, z0, roll0, pitch0, yaw0 = ROBOT_WORK
            self.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)
            
            # Leer el archivo NGC y extraer las coordenadas X, Y
            lineas_procesadas = 0
            try:
                with open(self._archivo_ngc, 'r') as gcode:
                    origen_archivo = None  # punto inicial del archivo NGC
                    for line in gcode:
                        line = line.strip()
                        # Extraer coordenadas X, Y del formato "X123.45 Y67.89"
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
                                    # El primer punto del archivo se alinea con ROBOT_WORK
                                    origen_archivo = (xx, yy)
                                    target_x = x0
                                    target_y = y0
                                else:
                                    # Mover relativo al primer punto del archivo
                                    dx = xx - origen_archivo[0]
                                    dy = yy - origen_archivo[1]
                                    target_x = x0 + dx
                                    target_y = y0 + dy

                                # Ejecutar movimiento manteniendo Z y orientación de ROBOT_WORK
                                self.arm.set_position(
                                    x=target_x,
                                    y=target_y,
                                    z=z0,
                                    roll=roll0,
                                    pitch=pitch0,
                                    yaw=yaw0,
                                    speed=100,
                                    wait=True,
                                )
                                self._robot_pose = [target_x, target_y, z0, roll0, pitch0, yaw0]
                                lineas_procesadas += 1

                self._actualizar_estado_robot(f"archivo dibujado: {lineas_procesadas} puntos")
                # Volver a la posición de trabajo al terminar
                try:
                    if self.arm is not None:
                        self.arm.set_position(*ROBOT_WORK, speed=20, wait=True)
                        self._robot_pose = list(ROBOT_WORK)
                        # Limpiar selección de archivo para permitir cargar uno nuevo
                        self._archivo_ngc = None
                        try:
                            self.ui.archivo_texto.setText("")
                        except Exception:
                            pass
                        self._actualizar_estado_robot("regresado a ROBOT_WORK")
                except Exception as exc:
                    self._actualizar_estado_robot(f"error al regresar a ROBOT_WORK: {exc}")
            except FileNotFoundError:
                self._actualizar_estado_robot(f"error: archivo no encontrado")
            except Exception as exc:
                self._actualizar_estado_robot(f"error leyendo archivo: {exc}")
        except Exception as exc:
            self._actualizar_estado_robot(f"error: {exc}")

    def _dibujar_cuadrado(self) -> None:
        """Dibuja un cuadrado de 15x15 cm iniciando desde ROBOT_WORK"""
        if self.arm is None:
            self._actualizar_estado_robot("modo local")
            return

        try:
            self._actualizar_estado_robot("dibujando cuadrado...")
            # Volver a posición de trabajo (0, 0)
            x0, y0, z0, roll0, pitch0, yaw0 = ROBOT_WORK
            self.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

            # Puntos del cuadrado (0,0), (150,0), (150,150), (0,150), (0,0)
            puntos = [
                (x0, y0),
                (x0 + CUADRADO_LADO, y0),
                (x0 + CUADRADO_LADO, y0 + CUADRADO_LADO),
                (x0, y0 + CUADRADO_LADO),
                (x0, y0),
            ]

            for x, y in puntos:
                self.arm.set_position(x=x, y=y, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

            self._robot_pose = [x0, y0, z0, roll0, pitch0, yaw0]
            self._actualizar_estado_robot("cuadrado dibujado")
        except Exception as exc:
            self._actualizar_estado_robot(f"error: {exc}")

    def _dibujar_circulo(self) -> None:
        """Dibuja un círculo de 10 cm de diámetro iniciando desde ROBOT_WORK"""
        if self.arm is None:
            self._actualizar_estado_robot("modo local")
            return

        try:
            self._actualizar_estado_robot("dibujando círculo...")
            x0, y0, z0, roll0, pitch0, yaw0 = ROBOT_WORK
            self.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

            # Generar puntos del círculo (radio = 50 mm)
            radio = CIRCULO_DIAMETRO / 2
            pasos = 60  # 10 grados por paso
            puntos = []
            for i in range(pasos + 1):
                angulo = (i * 360 / pasos) * math.pi / 180
                x = x0 + radio * math.cos(angulo)
                y = y0 + radio * math.sin(angulo)
                puntos.append((x, y))

            for x, y in puntos:
                self.arm.set_position(x=x, y=y, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

            self._robot_pose = [x0, y0, z0, roll0, pitch0, yaw0]
            self._actualizar_estado_robot("círculo dibujado")
        except Exception as exc:
            self._actualizar_estado_robot(f"error: {exc}")

    def _dibujar_triangulo(self) -> None:
        """Dibuja un triángulo equilátero de 10 cm de lado iniciando desde ROBOT_WORK"""
        if self.arm is None:
            self._actualizar_estado_robot("modo local")
            return

        try:
            self._actualizar_estado_robot("dibujando triángulo...")
            x0, y0, z0, roll0, pitch0, yaw0 = ROBOT_WORK
            self.arm.set_position(x=x0, y=y0, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

            # Triángulo equilátero: altura = lado * sqrt(3)/2
            lado = TRIANGULO_LADO
            altura = lado * math.sqrt(3) / 2

            # Puntos del triángulo equilátero con vértice de inicio en ROBOT_WORK
            puntos = [
                (x0, y0),  # vértice superior (inicio)
                (x0 + lado / 2, y0 - altura / 2),  # vértice abajo derecha
                (x0 - lado / 2, y0 - altura / 2),  # vértice abajo izquierda
                (x0, y0),  # regresa al vértice inicial
            ]

            for x, y in puntos:
                self.arm.set_position(x=x, y=y, z=z0, roll=roll0, pitch=pitch0, yaw=yaw0, speed=20, wait=True)

            self._robot_pose = [x0, y0, z0, roll0, pitch0, yaw0]
            self._actualizar_estado_robot("triángulo dibujado")
        except Exception as exc:
            self._actualizar_estado_robot(f"error: {exc}")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._vision_controller is not None:
            self._vision_controller.close()
        if self.arm is not None:
            try:
                self.arm.set_position(*ROBOT_HOME, speed=20, wait=True)
                self.arm.disconnect()
            except Exception:
                pass
        super().closeEvent(event)


def _solicitar_ip_robot() -> str:
    return "172.23.254.182"


def main() -> None:
    ip_robot = _solicitar_ip_robot()
    app = QtWidgets.QApplication(sys.argv)
    ventana = VentanaControl(ip_robot)
    ventana.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()