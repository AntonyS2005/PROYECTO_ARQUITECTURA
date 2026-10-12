import re
import threading

import cv2
import numpy as np

from ..nucleo.errores import ErrorFotografia
from .modelos import cargar_modelos


class MotorVision:
    def __init__(self, directorio):
        rutas = cargar_modelos(directorio)
        cv2.setNumThreads(2)
        self.detector = cv2.FaceDetectorYN.create(
            rutas["face_detection_yunet_2023mar.onnx"], "", (640, 480), 0.8, 0.3, 5000
        )
        self.reconocedor = cv2.FaceRecognizerSF.create(
            rutas["face_recognition_sface_2021dec.onnx"], ""
        )
        self.lector_carne = cv2.wechat_qrcode.WeChatQRCode(
            rutas["detect_2021nov.prototxt"],
            rutas["detect_2021nov.caffemodel"],
            rutas["sr_2021nov.prototxt"],
            rutas["sr_2021nov.caffemodel"],
        )
        self.bloqueo_rostro = threading.Lock()
        self.bloqueo_carne = threading.Lock()

    def leer_carne(self, imagen):
        with self.bloqueo_carne:
            identificadores, _ = self.lector_carne.detectAndDecode(imagen)
        if len(identificadores) != 1:
            raise ValueError("Presente un solo carné con el QR visible.")
        identificador = identificadores[0]
        if not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            identificador,
            re.IGNORECASE,
        ):
            raise ValueError("QR del carné no válido.")
        return {"uuid": identificador.lower(), "modeloCarne": "wechatqrcode-2021nov"}

    def extraer_vector(self, imagen):
        alto, ancho = imagen.shape[:2]
        if max(ancho, alto) > 640:
            escala = 640 / max(ancho, alto)
            imagen = cv2.resize(imagen, (round(ancho * escala), round(alto * escala)))

        with self.bloqueo_rostro:
            self.detector.setInputSize((imagen.shape[1], imagen.shape[0]))
            _, rostros = self.detector.detect(imagen)
            if rostros is None:
                reducida = cv2.resize(
                    imagen,
                    (max(40, imagen.shape[1] // 2), max(40, imagen.shape[0] // 2)),
                )
                self.detector.setInputSize((reducida.shape[1], reducida.shape[0]))
                _, rostros = self.detector.detect(reducida)
                if rostros is not None:
                    for rostro in rostros:
                        rostro[:14].reshape(-1, 2)[:] *= (
                            imagen.shape[1] / reducida.shape[1],
                            imagen.shape[0] / reducida.shape[0],
                        )
            if rostros is None:
                raise ErrorFotografia("ROSTRO_NO_DETECTADO")
            if len(rostros) != 1:
                raise ErrorFotografia("VARIOS_ROSTROS")
            rostro_alineado = self.reconocedor.alignCrop(imagen, rostros[0])
            vector = (
                self.reconocedor.feature(rostro_alineado).reshape(-1).astype(np.float64)
            )
        norma = np.linalg.norm(vector)
        if vector.size != 128 or not np.all(np.isfinite(vector)) or norma <= 0:
            raise RuntimeError("Representación facial no válida.")
        return vector / norma
