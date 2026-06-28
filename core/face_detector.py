"""
YOLOv5 人脸检测模块
- 开发环境：ultralytics YOLO 加载 yolov5su.pt
- 龙芯部署：ONNX Runtime 推理（自动回退）
- 检测 person 类，从人体框估算人脸区域
"""
import os
import time
import numpy as np
import cv2


class FaceDetector:
    """YOLOv5 人脸检测器（ultralytics / ONNX 双后端自动切换）"""

    PERSON_CLASS_ID = 0
    MODEL_NAME = 'yolov5su'

    def __init__(self, confidence=0.5, nms_threshold=0.45, input_size=640):
        self.model_name = self.MODEL_NAME
        self.confidence = confidence
        self.nms_threshold = nms_threshold
        self.input_size = input_size

        self.model = None           # ultralytics YOLO 对象
        self.onnx_session = None    # onnxruntime session
        self.backend = None
        self._fps_history = []
        self._last_inference_time = 0

        self._load_model()

    # ========== 后端加载 ==========

    def _load_model(self):
        # 1. 优先 ultralytics（开发环境 / 有 PyTorch）
        if self._try_load_ultralytics():
            self.backend = 'ultralytics'
            return
        # 2. 回退 ONNX Runtime（龙芯平台）
        if self._try_load_onnx():
            self.backend = 'onnx'
            return
        raise RuntimeError(
            "无法加载 YOLOv5 模型，请安装 ultralytics 或 onnxruntime, "
            f"并确保 {self.MODEL_NAME}.pt 或 {self.MODEL_NAME}.onnx 存在")

    def _try_load_ultralytics(self):
        try:
            from ultralytics import YOLO
            model_file = f'{self.MODEL_NAME}.pt'
            self.model = YOLO(model_file)
            print(f"[YOLO] ultralytics 后端: {self.MODEL_NAME}.pt 加载成功")
            return True
        except ImportError:
            print("[YOLO] ultralytics 未安装，尝试 ONNX 后端")
        except Exception as e:
            print(f"[YOLO] 加载失败: {e}")
        return False

    def _try_load_onnx(self):
        try:
            import onnxruntime as ort
            onnx_path = f'model/{self.MODEL_NAME}.onnx'
            if not os.path.exists(onnx_path):
                onnx_path = f'{self.MODEL_NAME}.onnx'
            if not os.path.exists(onnx_path):
                print(f"[ONNX] 模型文件不存在: {onnx_path}")
                return False
            self.onnx_session = ort.InferenceSession(
                onnx_path, providers=['CPUExecutionProvider'])
            print(f"[ONNX] onnxruntime 后端: {onnx_path} 加载成功")
            return True
        except ImportError:
            print("[ONNX] onnxruntime 未安装")
        except Exception as e:
            print(f"[ONNX] 加载失败: {e}")
        return False

    @property
    def fps(self):
        if not self._fps_history:
            return 0
        return 1.0 / (sum(self._fps_history) / max(len(self._fps_history), 1))

    # ========== 统一检测接口 ==========

    def detect(self, img):
        """检测图像中的所有人脸区域，返回 [(x, y, w, h, confidence), ...]"""
        t0 = time.time()
        if self.backend == 'ultralytics':
            faces = self._detect_ultralytics(img)
        else:
            faces = self._detect_onnx(img)
        dt = time.time() - t0
        self._last_inference_time = dt
        self._fps_history.append(dt)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)
        return faces

    # ========== ultralytics 后端 ==========

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
                face = self._box_to_face(box, w, h, float(conf))
                if face:
                    faces.append(face)
        return faces

    # ========== ONNX 后端 ==========

    def _detect_onnx(self, img):
        if self.onnx_session is None:
            return []
        h, w = img.shape[:2]

        # 预处理：resize → RGB → normalize → NCHW
        input_img = cv2.resize(img, (self.input_size, self.input_size))
        input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
        input_img = input_img.transpose(2, 0, 1).astype(np.float32) / 255.0
        input_img = np.expand_dims(input_img, axis=0)

        # ONNX 推理
        outputs = self.onnx_session.run(None, {'images': input_img})
        predictions = outputs[0]  # [1, N, 85]

        return self._postprocess_onnx(predictions, w, h)

    def _postprocess_onnx(self, predictions, img_w, img_h):
        """ONNX 输出后处理：筛选 person 类 + NMS + 人脸估算"""
        predictions = predictions[0]  # [N, 85]

        # 提取 person 类的置信度
        person_conf = predictions[:, 4] * predictions[:, 5 + self.PERSON_CLASS_ID]
        mask = person_conf > self.confidence
        predictions = predictions[mask]
        person_conf = person_conf[mask]

        if len(predictions) == 0:
            return []

        # 解码边界框 (cx, cy, w, h → x1, y1, x2, y2)
        boxes = predictions[:, :4].copy()
        boxes[:, 0] = (predictions[:, 0] - predictions[:, 2] / 2) * img_w / self.input_size
        boxes[:, 1] = (predictions[:, 1] - predictions[:, 3] / 2) * img_h / self.input_size
        boxes[:, 2] = (predictions[:, 0] + predictions[:, 2] / 2) * img_w / self.input_size
        boxes[:, 3] = (predictions[:, 1] + predictions[:, 3] / 2) * img_h / self.input_size

        # NMS
        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(), person_conf.tolist(),
            self.confidence, self.nms_threshold)

        faces = []
        if len(indices) > 0:
            for i in indices.flatten():
                face = self._box_to_face(boxes[i], img_w, img_h, float(person_conf[i]))
                if face:
                    faces.append(face)
        return faces

    # ========== 共用：人体框 → 人脸区域估算 ==========

    def _box_to_face(self, box, img_w, img_h, conf):
        """从人体边界框估算人脸 ROI"""
        x1, y1, x2, y2 = box
        fw, fh = x2 - x1, y2 - y1
        face_x = int(x1 + fw * 0.15)
        face_y = int(y1 + fh * 0.03)
        face_w = int(fw * 0.65)
        face_h = int(face_w * 1.25)
        face_x = max(0, face_x)
        face_y = max(0, face_y)
        face_w = min(face_w, img_w - face_x)
        face_h = min(face_h, img_h - face_y)
        if face_w > 20 and face_h > 20:
            return (face_x, face_y, face_w, face_h, conf)
        return None

    # ========== ROI 过滤 ==========

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

    # ========== 标注 ==========

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
