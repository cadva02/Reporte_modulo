import cv2
import os
import argparse
from dataclasses import dataclass
from typing import Optional
from inference import get_model
import supervision as sv

# 1. FORZAR COMPATIBILIDAD CON EL ENTORNO GRÁFICO (X11)
# Esto soluciona el error de Wayland en Ubuntu
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "1"  # Activa debug para ver si la cámara falla

# Tus credenciales por defecto
MODEL_ID = "shapeclassifier_group_9_id_409/1"
API_KEY = "1zTntUVnABXCBtOPSfPx"

DEFAULT_PORT = 4747
DEFAULT_PATH = "/video"
DEFAULT_PHONE_IP = "10.50.120.60"


@dataclass(frozen=True)
class DroidCamConfig:
    ip: str
    port: int = DEFAULT_PORT
    path: str = DEFAULT_PATH

    @property
    def url(self) -> str:
        return f"http://{self.ip}:{self.port}{self.path}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Roboflow detection reading from a DroidCam stream (IP)."
    )
    parser.add_argument("ip", nargs="?", help="Phone IP address on the local network")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="DroidCam port")
    parser.add_argument(
        "--path",
        default=DEFAULT_PATH,
        help="DroidCam stream path (default: /video)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ip = args.ip or DEFAULT_PHONE_IP
    config = DroidCamConfig(ip=ip, port=args.port, path=args.path)

    try:
        print("Cargando modelo...")
        model = get_model(model_id=MODEL_ID, api_key=API_KEY)

        # Abrir stream de DroidCam por URL (igual que droidcam_ip.py)
        cap = cv2.VideoCapture(config.url)
        if not cap.isOpened():
            print(f"Error: No se pudo abrir el stream en {config.url}. Revisa la IP y que DroidCam esté corriendo en el teléfono.")
            return 1

        # Anotadores
        box_annotator = sv.BoxAnnotator()
        label_annotator = sv.LabelAnnotator()

        print(f"Conectado con éxito al modelo: {MODEL_ID}")
        print(f"Conectado al stream: {config.url}")
        print("Iniciando bucle de video... Presiona 'q' para salir.")

        # Crear la ventana antes del bucle
        cv2.namedWindow("Deteccion Roboflow", cv2.WINDOW_NORMAL)

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("Error al leer el frame del stream.")
                break

            # Inferencia
            results = model.infer(frame)[0]
            detections = sv.Detections.from_inference(results)

            # DEBUG: Imprimir si detecta algo
            if len(detections) > 0:
                print(f"¡Detectado! Objetos: {len(detections)}")

            # Dibujar resultados
            annotated_frame = box_annotator.annotate(scene=frame.copy(), detections=detections)
            annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections)

            # Mostrar en pantalla
            cv2.imshow("Deteccion Roboflow", annotated_frame)

            # El waitKey es VITAL en Linux para que la ventana se procese
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()
        # Un pequeño hack para asegurar que las ventanas se cierren en Linux
        for i in range(1, 5):
            cv2.waitKey(1)

    except Exception as e:
        print(f"Error detectado: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())