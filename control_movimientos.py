from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
import sys
from typing import Callable
import math 

from PyQt5 import QtCore, QtGui, QtWidgets

from Lite6 import Ui_MainWindow
from movimientos import Abajo, Arriba, Derecha, Izquierda, Posicion

try:
    from xarm.wrapper import XArmAPI
except ImportError:
    XArmAPI = None


ROBOT_HOME = (417.2, 176.0, 200.2, -176, -15.1, 14.02)
ROBOT_WORK = (309.2, -34.5, 88.9, -179.9, -1.2, 8.6)
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
        self._robot_pose = list(ROBOT_WORK)
        self.arm = None
        self._movimiento_activo: tuple[str, Callable[[Posicion], Posicion]] | None = None
        self._hold_timer = QtCore.QTimer(self)
        self._hold_timer.setInterval(100)
        self._hold_timer.timeout.connect(self._ejecutar_continuo)

        self._hold_delay = QtCore.QTimer(self)
        self._hold_delay.setSingleShot(True)
        self._hold_delay.setInterval(300)
        self._hold_delay.timeout.connect(self._iniciar_repeticion)

        self._crear_indicadores()
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
            raise RuntimeError("xArm API no disponible")

        try:
            arm = XArmAPI(ip)
            arm.motion_enable(enable=True)
            arm.set_mode(0)
            arm.set_state(state=0)
            arm.move_gohome(wait=True)
            arm.set_position(*ROBOT_WORK, speed=20, wait=True)
            self._robot_pose = list(ROBOT_WORK)
            self._actualizar_estado_robot(f"conectado: {ip}")
            return arm
        except Exception as exc:
            raise RuntimeError(f"no fue posible conectar al robot: {exc}") from exc

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
        if self.arm is not None:
            try:
                self.arm.move_gohome(wait=True)
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
