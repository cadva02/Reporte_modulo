from __future__ import annotations

import os

import cv2
from PyQt5 import QtCore, QtGui, QtWidgets

try:
    from inference import get_model
except ImportError:
    get_model = None

try:
    import supervision as sv
except ImportError:
    sv = None

os.environ["QT_QPA_PLATFORM"] = "xcb"

MODEL_ID = "shapeclassifier_group_9_id_409/1"
API_KEY = "1zTntUVnABXCBtOPSfPx"
DEFAULT_PORT = 4747
DEFAULT_PATH = "/video"
DEFAULT_PHONE_IP = "10.50.120.60"


class DroidCamConfig:
    def __init__(self, ip: str = DEFAULT_PHONE_IP, port: int = DEFAULT_PORT, path: str = DEFAULT_PATH) -> None:
        self.ip = ip
        self.port = port
        self.path = path

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}{self.path}"


class VisionDetectionController(QtCore.QObject):
    def __init__(self, label: QtWidgets.QLabel, status_callback=None, completion_callback=None, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._status_callback = status_callback
        self._completion_callback = completion_callback
        self._camera_config = DroidCamConfig()
        self._camera_cap: cv2.VideoCapture | None = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._update_frame)
        self._model = self._load_model()
        self._box_annotator = sv.BoxAnnotator() if sv is not None else None
        self._label_annotator = sv.LabelAnnotator() if sv is not None else None
        self._consecutive_frames = 0
        self._saved = False

    def _set_status(self, text: str) -> None:
        if callable(self._status_callback):
            self._status_callback(text)

    def _load_model(self):
        if get_model is None:
            self._set_status("modelo no disponible")
            return None

        try:
            return get_model(model_id=MODEL_ID, api_key=API_KEY)
        except Exception as exc:
            self._set_status(f"modelo no cargado: {exc}")
            return None

    def start(self) -> None:
        if self._timer.isActive():
            return

        if self._camera_cap is None:
            self._camera_cap = cv2.VideoCapture(self._camera_config.url)

        if not self._camera_cap.isOpened():
            self._label.setText(f"No se pudo abrir la camara\n{self._camera_config.url}")
            self._set_status("camara apagada")
            return

        self._label.setText("Procesando deteccion...")
        self._set_status("camara encendida")
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        if self._camera_cap is not None:
            self._camera_cap.release()
            self._camera_cap = None
        self._label.clear()
        self._label.setText("Camara apagada")
        self._set_status("camara apagada")

    def _update_frame(self) -> None:
        if self._camera_cap is None:
            return

        ret, frame = self._camera_cap.read()
        if not ret or frame is None:
            self._label.setText("Error al leer la camara")
            return

        if self._model is not None and sv is not None and self._box_annotator is not None and self._label_annotator is not None:
            try:
                results = self._model.infer(frame)[0]
                detections = sv.Detections.from_inference(results)
                
                # Detectar formas específicas
                detected_shapes = set()
                if len(detections) > 0 and detections.class_id is not None:
                    for class_id in detections.class_id:
                        if class_id == 0:  # 0 = circle
                            detected_shapes.add("circle")
                        elif class_id == 3:  # 3 = square
                            detected_shapes.add("square")
                        elif class_id == 4:  # 4 = triangle
                            detected_shapes.add("triangle")
                
                has_triangle = "triangle" in detected_shapes
                has_circle = "circle" in detected_shapes
                has_square = "square" in detected_shapes
                
                if has_triangle and has_circle and has_square:
                    self._consecutive_frames += 1
                else:
                    self._consecutive_frames = 0
                
                if self._consecutive_frames > 4 and not self._saved:
                    # Calcular posiciones mapeadas en el sistema de movimiento 7x12
                    height, width = frame.shape[:2]
                    center_x = width / 2
                    center_y = height / 2
                    workspace_x_range = 7
                    workspace_y_range = 12
                    
                    def _clamp_grid(value: float, minimum: int, maximum: int) -> int:
                        return max(min(int(round(value)), maximum), minimum)
                    
                    positions = {}
                    if detections.class_id is not None:
                        for i, class_id in enumerate(detections.class_id):
                            x1, y1, x2, y2 = detections.xyxy[i]
                            cx_pixel = (x1 + x2) / 2
                            cy_pixel = (y1 + y2) / 2
                            grid_x = (cx_pixel - center_x) / center_x * workspace_x_range
                            grid_y = -(cy_pixel - center_y) / center_y * workspace_y_range
                            grid_x = _clamp_grid(grid_x, -7, 7)
                            grid_y = _clamp_grid(grid_y, -12, 12)
                            if class_id == 0:
                                positions['circle'] = (grid_x, grid_y)
                            elif class_id == 3:
                                positions['square'] = (grid_x, grid_y)
                            elif class_id == 4:
                                positions['triangle'] = (grid_x, grid_y)
                    
                    # Guardar el frame
                    cv2.imwrite("detected_frame.jpg", frame)
                    self._set_status("frame guardado, deteccion completada")
                    self.stop()
                    self._saved = True
                    
                    if callable(self._completion_callback):
                        self._completion_callback(positions)
                
                if len(detections) > 0:
                    self._set_status(f"detectadas: {len(detections)}")
                frame = self._box_annotator.annotate(scene=frame.copy(), detections=detections)
                frame = self._label_annotator.annotate(scene=frame, detections=detections)
            except Exception as exc:
                self._set_status(f"error deteccion: {exc}")

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = frame_rgb.shape
        bytes_per_line = channels * width
        image = QtGui.QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QtGui.QImage.Format_RGB888,
        )
        pixmap = QtGui.QPixmap.fromImage(image)
        self._label.setPixmap(
            pixmap.scaled(
                self._label.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )

    def close(self) -> None:
        self.stop()

    def reset_detection(self) -> None:
        self._consecutive_frames = 0
        self._saved = False
