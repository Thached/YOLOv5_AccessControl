"""
YOLOv5人脸检测模块
- ONNX Runtime 推理 (龙芯平台部署方案)
- PyTorch Hub 推理 (Windows开发环境)
- Haar级联 回退 (通用后备)
"""
import os
import sys
import time
import threading
import numpy as np
import cv2


class FaceDetector:
    """
    YOLOv5 人脸检测器，三级回退策略：
    1. ONNX Runtime → 龙芯2K1000部署方案
    2. PyTorch Hub → Windows开发环境
    3. Haar Cascade → 通用后备
    """

    # COCO 数据集中 person 类 ID
    PERSON_CLASS_ID = 0

    def __init__(self, onnx_path='model/yolov5s.onnx', model_name='yolov5s',
                 confidence=0.5, nms_threshold=0.45, input_size=640,
                 haar_path='data/haarcascade_frontalface_default.xml'):
        self.onnx_path = onnx_path
        self.model_name = model_name
        self.confidence = confidence
        self.nms_threshold = nms_threshold
        self.input_size = input_size

        # 各后端状态
        self.onnx_session = None
        self.ultralytics_model = None
        self.torch_model = None
        self.haar_cascade = None
        self.backend = 'haar'  # 当前使用的后端

        self._load_lock = threading.Lock()
        self._fps_history = []
        self._last_inference_time = 0

        # 按优先级尝试加载
        self._init_backends(haar_path)

    def _init_backends(self, haar_path):
        # 1. 尝试 ONNX Runtime（本地模型文件）
        if self._try_load_onnx():
            self.backend = 'onnx'
            return
        # 2. 尝试 ultralytics YOLO（推荐，自动处理下载）
        if self._try_load_ultralytics():
            self.backend = 'ultralytics'
            return
        # 3. 尝试 PyTorch Hub（传统方式）
        if self._try_load_torch():
            self.backend = 'torch'
            return
        # 4. 加载 Haar 级联（兜底）
        self._try_load_haar(haar_path)

    def _try_load_onnx(self):
        try:
            import onnxruntime as ort
            if os.path.exists(self.onnx_path):
                self.onnx_session = ort.InferenceSession(
                    self.onnx_path,
                    providers=['CPUExecutionProvider'])
                print(f"[ONNX] 模型加载成功: {self.onnx_path}")
                return True
            else:
                print(f"[ONNX] 模型文件不存在: {self.onnx_path}")
                return False
        except ImportError:
            print("[ONNX] onnxruntime 未安装")
            return False
        except Exception as e:
            print(f"[ONNX] 加载失败: {e}")
            return False

    def _try_load_ultralytics(self):
        try:
            from ultralytics import YOLO
            model_file = f'{self.model_name}.pt'
            self.ultralytics_model = YOLO(model_file)
            print(f"[Ultralytics] YOLOv5 '{self.model_name}' 加载成功")
            return True
        except ImportError:
            print("[Ultralytics] ultralytics 包未安装")
            return False
        except Exception as e:
            print(f"[Ultralytics] 加载失败: {e}")
            return False

    def _try_load_torch(self):
        try:
            import torch
            self.torch_model = torch.hub.load(
                'ultralytics/yolov5', self.model_name,
                pretrained=True, verbose=False)
            self.torch_model.conf = self.confidence
            print(f"[Torch] YOLOv5 '{self.model_name}' 加载成功")
            return True
        except Exception as e:
            print(f"[Torch] 加载失败: {e}")
            return False

    def _try_load_haar(self, haar_path):
        if os.path.exists(haar_path):
            self.haar_cascade = cv2.CascadeClassifier(haar_path)
            self.backend = 'haar'
            print("[Haar] 级联分类器加载成功")
        else:
            print("[Haar] 级联文件不存在!")

    @property
    def fps(self):
        if not self._fps_history:
            return 0
        return 1.0 / (sum(self._fps_history) / max(len(self._fps_history), 1))

    def detect(self, img):
        """
        检测图像中的所有人脸区域
        返回: [(x, y, w, h, confidence), ...]
        """
        t0 = time.time()

        if self.backend == 'onnx':
            faces = self._detect_onnx(img)
        elif self.backend == 'ultralytics':
            faces = self._detect_ultralytics(img)
        elif self.backend == 'torch':
            faces = self._detect_torch(img)
        else:
            faces = self._detect_haar(img)

        dt = time.time() - t0
        self._last_inference_time = dt
        self._fps_history.append(dt)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)

        return faces

    def _detect_onnx(self, img):
        """ONNX Runtime 推理"""
        if self.onnx_session is None:
            return self._detect_haar(img)

        h, w = img.shape[:2]
        # 预处理：resize + normalize
        input_img = cv2.resize(img, (self.input_size, self.input_size))
        input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
        input_img = input_img.transpose(2, 0, 1).astype(np.float32) / 255.0
        input_img = np.expand_dims(input_img, axis=0)

        # ONNX 推理
        outputs = self.onnx_session.run(None, {'images': input_img})
        predictions = outputs[0]  # [1, 25200, 85]

        return self._postprocess_onnx(predictions, w, h)

    def _postprocess_onnx(self, predictions, img_w, img_h):
        """ONNX 输出的后处理：筛选 person 类 + NMS"""
        predictions = predictions[0]  # [25200, 85]

        # 提取 person 类的置信度（class 0）
        person_conf = predictions[:, 4] * predictions[:, 5 + self.PERSON_CLASS_ID]
        mask = person_conf > self.confidence
        predictions = predictions[mask]
        person_conf = person_conf[mask]

        if len(predictions) == 0:
            return []

        # 解码边界框（cx, cy, w, h → x1, y1, x2, y2）
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
                x1, y1, x2, y2 = boxes[i]
                fw, fh = x2 - x1, y2 - y1
                # 从人体框估算面部区域（上半身35%）
                face_x = int(x1 + fw * 0.2)
                face_y = int(y1)
                face_w = int(fw * 0.6)
                face_h = int(fh * 0.35)
                face_x = max(0, face_x)
                face_y = max(0, face_y)
                face_w = min(face_w, img_w - face_x)
                face_h = min(face_h, img_h - face_y)
                if face_w > 20 and face_h > 20:
                    faces.append((face_x, face_y, face_w, face_h, float(person_conf[i])))
        return faces

    def _detect_ultralytics(self, img):
        """Ultralytics YOLO 推理"""
        if self.ultralytics_model is None:
            return self._detect_haar(img)

        h, w = img.shape[:2]
        results = self.ultralytics_model(img, conf=self.confidence, verbose=False)
        detections = results[0].boxes
        if detections is None:
            return []

        faces = []
        boxes = detections.xyxy.cpu().numpy()
        confs = detections.conf.cpu().numpy()
        cls_ids = detections.cls.cpu().numpy()

        for i, (box, conf, cls_id) in enumerate(zip(boxes, confs, cls_ids)):
            if int(cls_id) == self.PERSON_CLASS_ID:
                x1, y1, x2, y2 = box
                fw, fh = x2 - x1, y2 - y1
                face_x = int(x1 + fw * 0.2)
                face_y = int(y1)
                face_w = int(fw * 0.6)
                face_h = int(fh * 0.35)
                face_x = max(0, face_x)
                face_y = max(0, face_y)
                face_w = min(face_w, w - face_x)
                face_h = min(face_h, h - face_y)
                if face_w > 20 and face_h > 20:
                    faces.append((face_x, face_y, face_w, face_h, float(conf)))
        return faces

    def _detect_torch(self, img):
        """PyTorch Hub 推理"""
        if self.torch_model is None:
            return self._detect_haar(img)

        h, w = img.shape[:2]
        results = self.torch_model(img)
        detections = results.xyxy[0].cpu().numpy()

        faces = []
        for det in detections:
            x1, y1, x2, y2, conf, cls = det
            if int(cls) == self.PERSON_CLASS_ID:
                fw, fh = x2 - x1, y2 - y1
                face_x = int(x1 + fw * 0.2)
                face_y = int(y1)
                face_w = int(fw * 0.6)
                face_h = int(fh * 0.35)
                face_x = max(0, face_x)
                face_y = max(0, face_y)
                face_w = min(face_w, w - face_x)
                face_h = min(face_h, h - face_y)
                if face_w > 20 and face_h > 20:
                    faces.append((face_x, face_y, face_w, face_h, float(conf)))
        return faces

    def _detect_haar(self, img):
        """Haar级联检测（后备）"""
        if self.haar_cascade is None:
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        results = self.haar_cascade.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=5, minSize=(60, 60))
        return [(x, y, w, h, 1.0) for (x, y, w, h) in results]

    def detect_in_roi(self, img, x_min, y_min, x_max, y_max):
        """检测ROI区域内的人脸"""
        all_faces = self.detect(img)
        valid = []
        for face in all_faces:
            x, y, w, h, conf = face
            if x > x_min and y > y_min and x + w < x_max and y + h < y_max:
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
