"""
YOLOv5 人脸检测模块
- 统一使用 yolov5su.pt 模型
- 检测 person 类，从人体框估算人脸区域
"""
import time
import numpy as np
import cv2


class FaceDetector:
    """YOLOv5 人脸检测器（仅使用 yolov5su.pt）"""

    PERSON_CLASS_ID = 0
    MODEL_NAME = 'yolov5su'

    def __init__(self, confidence=0.5, nms_threshold=0.45, input_size=640):
        self.model_name = self.MODEL_NAME
        self.confidence = confidence
        self.nms_threshold = nms_threshold
        self.input_size = input_size

        self.model = None
        self.backend = 'ultralytics'
        self._fps_history = []
        self._last_inference_time = 0

        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            model_file = f'{self.MODEL_NAME}.pt'
            self.model = YOLO(model_file)
            print(f"[YOLO] {self.MODEL_NAME}.pt 加载成功")
        except ImportError:
            raise ImportError("请安装 ultralytics: pip install ultralytics")
        except Exception as e:
            raise RuntimeError(f"加载 {self.MODEL_NAME}.pt 失败: {e}")

    @property
    def fps(self):
        if not self._fps_history:
            return 0
        return 1.0 / (sum(self._fps_history) / max(len(self._fps_history), 1))

    def detect(self, img):
        """检测图像中的所有人脸区域，返回 [(x, y, w, h, confidence), ...]"""
        t0 = time.time()
        faces = self._detect_ultralytics(img)
        dt = time.time() - t0
        self._last_inference_time = dt
        self._fps_history.append(dt)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)
        return faces

    def _detect_ultralytics(self, img):
        if self.model is None:
            return []

        h, w = img.shape[:2]
        results = self.model(img, conf=self.confidence, verbose=False)
        detections = results[0].boxes
        if detections is None:
            return []

        faces = []
        boxes = detections.xyxy.cpu().numpy()
        confs = detections.conf.cpu().numpy()
        cls_ids = detections.cls.cpu().numpy()

        for box, conf, cls_id in zip(boxes, confs, cls_ids):
            if int(cls_id) == self.PERSON_CLASS_ID:
                x1, y1, x2, y2 = box
                fw, fh = x2 - x1, y2 - y1
                # 从人体框估算面部区域：宽度由肩宽推算，高度由人脸宽高比计算
                face_x = int(x1 + fw * 0.15)
                face_y = int(y1 + fh * 0.03)
                face_w = int(fw * 0.65)
                face_h = int(face_w * 1.25)
                face_x = max(0, face_x)
                face_y = max(0, face_y)
                face_w = min(face_w, w - face_x)
                face_h = min(face_h, h - face_y)
                if face_w > 20 and face_h > 20:
                    faces.append((face_x, face_y, face_w, face_h, float(conf)))
        return faces

    def detect_in_roi(self, img, x_min, y_min, x_max, y_max):
        """检测ROI区域内的人脸（以人脸中心点判断）"""
        all_faces = self.detect(img)
        valid = []
        for face in all_faces:
            x, y, w, h, conf = face
            cx, cy = x + w // 2, y + h // 2
            if x_min < cx < x_max and y_min < cy < y_max:
                valid.append(face)
        return valid, all_faces

    def annotate(self, img, faces, names=None, color=(0, 255, 0)):
        """在图像上标注检测结果"""
        from utils.face_utils import put_chinese_text
        for i, face in enumerate(faces):
            x, y, w, h, conf = face[:5]
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
            if names and i < len(names) and names[i]:
                label = f'{names[i]} {conf:.2f}'
                put_chinese_text(img, label, (x, y - 30),
                                 font_size=22, color=(0, 255, 0))
        return img
