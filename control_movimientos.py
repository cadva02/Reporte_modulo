from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
import sys
from typing import Callable

from PyQt5 import QtCore, QtGui, QtWidgets

from Lite6 import Ui_MainWindow
from movimientos import Abajo, Arriba, Derecha, Izquierda, Posicion

try:
    from xarm.wrapper import XArmAPI
except ImportError:
    XArmAPI = None


ROBOT_HOME = (417.2, 176.0, 200.2, -176, -15.1, 14.02)
ROBOT_WORK = (417.2, 176.0, 126.75, -176, -15.1, 14.02)
ROBOT_STEP_MM = 10.0


class LienzoFigura(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._figura: str | None = None
        self.setStyleSheet("background-color: white;")

    def set_figura(self, figura: str) -> None:
        self._figura = figura
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        if self._figura is None:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#2c3e50"), 4))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#c9d6df")))

        ancho = self.width()
        alto = self.height()

        if self._figura == "cuadrado":
            lado = min(ancho, alto) // 3
            x = (ancho - lado) // 2
            y = (alto - lado) // 2
            painter.drawRect(x, y, lado, lado)
        elif self._figura == "circulo":
            diametro = min(ancho, alto) // 3
            x = (ancho - diametro) // 2
            y = (alto - diametro) // 2
            painter.drawEllipse(x, y, diametro, diametro)
        elif self._figura == "triangulo":
            base = min(ancho, alto) // 2
            centro_x = ancho // 2
            centro_y = alto // 2
            altura = int(base * 0.866)
            puntos = [
                QtCore.QPointF(centro_x, centro_y - altura // 2),
                QtCore.QPointF(centro_x - base // 2, centro_y + altura // 2),
                QtCore.QPointF(centro_x + base // 2, centro_y + altura // 2),
            ]
            painter.drawPolygon(QtGui.QPolygonF(puntos))


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

        self.lienzo = LienzoFigura(self.ui.frame)
        self.lienzo.setGeometry(0, 0, self.ui.frame.width(), self.ui.frame.height())
        self.lienzo.show()

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

        self.ui.TrianguloButton.clicked.connect(lambda: self.lienzo.set_figura("triangulo"))
        self.ui.CuadradoButton.clicked.connect(lambda: self.lienzo.set_figura("cuadrado"))
        self.ui.CirculoButton.clicked.connect(lambda: self.lienzo.set_figura("circulo"))

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

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.arm is not None:
            try:
                self.arm.move_gohome(wait=True)
                self.arm.disconnect()
            except Exception:
                pass
        super().closeEvent(event)


def _solicitar_ip_robot() -> str:
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        return sys.argv[1].strip()

    ruta_config = Path(__file__).resolve().parents[2] / "robot.conf"
    if ruta_config.exists():
        parser = ConfigParser()
        parser.read(ruta_config)
        if parser.has_option("xArm", "ip"):
            ip_guardada = parser.get("xArm", "ip").strip()
            if ip_guardada:
                respuesta = input(f"IP del robot [{ip_guardada}]: ").strip()
                return respuesta or ip_guardada

    while True:
        ip = input("Ingrese la IP del robot xArm: ").strip()
        if ip:
            return ip
        print("La IP no puede estar vacia.")


def main() -> None:
    ip_robot = _solicitar_ip_robot()
    app = QtWidgets.QApplication(sys.argv)
    ventana = VentanaControl(ip_robot)
    ventana.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
