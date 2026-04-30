from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
import sys
from typing import Callable
import subprocess
import os

from PyQt5 import QtCore, QtGui, QtWidgets

from Lite6 import Ui_MainWindow
from dibujar_figuras import dibujar_circulo, dibujar_cuadrado, dibujar_triangulo
from dibujar_ngc import dibujar_archivo_ngc
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
        #self.camera_label.setAlignment(QtCore.Qt.AlignCenter)
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
                completion_callback=self._on_detection_complete,
                parent=self,
            )

        self._vision_controller.reset_detection()
        self._vision_controller.start()

    def _desactivar_manual(self) -> None:
        if self._vision_controller is not None:
            self._vision_controller.stop()

    def _on_detection_complete(self, positions: dict[str, tuple[float, float]]) -> None:
        order = ['triangle', 'square', 'circle']
        for shape in order:
            if shape in positions:
                grid_x, grid_y = positions[shape]
                robot_x = ROBOT_WORK[0] + grid_x * ROBOT_STEP_MM
                robot_y = ROBOT_WORK[1] + grid_y * ROBOT_STEP_MM
                self._mover_a_posicion_absoluta(robot_x, robot_y)
                self.posicion = Posicion(int(grid_x), int(grid_y))
                self._actualizar_vista()
                message = (
                    f"Figura completada: {shape} -> "
                    f"Grid: ({int(grid_x)}, {int(grid_y)}) "
                    f"Mm: ({robot_x:.1f}, {robot_y:.1f})"
                )
                print(message)
                self._actualizar_estado_robot(message)

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

    def _mover_a_posicion_absoluta(self, x: float, y: float) -> None:
        if self.arm is None:
            self._actualizar_estado_robot("modo local")
            return

        _, _, z, roll, pitch, yaw = self._robot_pose
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
            self._actualizar_estado_robot("moviendo a posicion")
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
        dibujar_archivo_ngc(self, ROBOT_WORK)

    def _dibujar_cuadrado(self) -> None:
        dibujar_cuadrado(self, ROBOT_WORK, 50)

    def _dibujar_circulo(self) -> None:
        dibujar_circulo(self, ROBOT_WORK, 50)

    def _dibujar_triangulo(self) -> None:
        dibujar_triangulo(self, ROBOT_WORK, 50)

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