"""
人脸识别模块
- 基于 YOLOv5 检测的人脸区域进行特征提取
- LBPH 直方图特征 + 相似度比对
- 支持从 SQLite 加载/存储特征
"""
import os
import pickle
import numpy as np
import cv2


def imread_unicode(filepath, flags=cv2.IMREAD_GRAYSCALE):
    with open(filepath, 'rb') as f:
        data = f.read()
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), flags)


class FaceRecognizer:
    """
    人脸特征提取与识别
    - 使用 LBPH 算法提取人脸纹理特征直方图
    - 特征向量存储在 SQLite 数据库中
    - 推理时计算待测人脸与库中各人脸的直方图距离
    """

    def __init__(self, model_path='model/model.xml', db=None):
        self.model_path = model_path
        self.db = db
        self.lbph = None
        self.names = []
        self._init_lbph()

    def _init_lbph(self):
        try:
            self.lbph = cv2.face.LBPHFaceRecognizer_create(
                radius=1, neighbors=8, grid_x=8, grid_y=8, threshold=100.0)
        except AttributeError:
            try:
                self.lbph = cv2.face.LBPHFaceRecognizer_create()
            except AttributeError:
                raise RuntimeError(
                    "需要 opencv-contrib-python: pip install opencv-contrib-python")

    # ========== 训练 ==========

    def train_from_dataset(self, dataset_path='dataset', progress_cb=None):
        """
        从 dataset 目录训练 LBPH 模型
        dataset/
          ├── 张三/  (20张人脸)
          └── 李四/  (20张人脸)
        """
        self.names = sorted([
            d for d in os.listdir(dataset_path)
            if os.path.isdir(os.path.join(dataset_path, d))
        ])
        X, y = self._load_images(dataset_path, sz=(200, 200))

        if len(X) == 0:
            raise ValueError("未找到训练数据")

        if progress_cb:
            progress_cb('模型训练中，请勿操作...')

        self.lbph.train(np.array(X), np.array(y))
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.lbph.save(self.model_path)

        # 同时为每个人提取特征直方图存入 SQLite
        if self.db is not None:
            self._save_features_to_db(X, y)

        if progress_cb:
            progress_cb(f'训练完成: {len(self.names)}人, {len(X)}张')

        return len(self.names), len(X)

    def _load_images(self, path, sz=None):
        X, y = [], []
        for idx, name in enumerate(self.names):
            subject_path = os.path.join(path, name)
            if not os.path.isdir(subject_path):
                continue
            for fname in os.listdir(subject_path):
                fpath = os.path.join(subject_path, fname)
                if not fname.lower().endswith(('.jpg', '.png', '.jpeg')):
                    continue
                try:
                    im = imread_unicode(fpath, cv2.IMREAD_GRAYSCALE)
                    if sz:
                        im = cv2.resize(im, sz)
                    X.append(np.asarray(im, dtype=np.uint8))
                    y.append(idx)
                except Exception:
                    continue
        return X, y

    def _save_features_to_db(self, X, y):
        """将每个人的特征向量存入SQLite"""
        if self.db is None:
            return
        for idx, name in enumerate(self.names):
            person_imgs = [X[i] for i in range(len(X)) if y[i] == idx]
            if person_imgs:
                # 用 LBPH 提取该人的平均直方图作为特征
                histograms = []
                for img in person_imgs:
                    hist = self._extract_lbph_histogram(img)
                    histograms.append(hist)
                avg_hist = np.mean(histograms, axis=0)
                self.db.save_face_features(name, avg_hist, len(person_imgs))

    def _extract_lbph_histogram(self, gray_img):
        """提取单张灰度人脸图的LBPH直方图特征"""
        gray = cv2.resize(gray_img, (200, 200))
        # 计算 LBP 特征
        radius, neighbors = 1, 8
        grid_x, grid_y = 8, 8
        lbp = np.zeros_like(gray)
        for i in range(radius, gray.shape[0] - radius):
            for j in range(radius, gray.shape[1] - radius):
                center = int(gray[i, j])
                code = 0
                for n in range(neighbors):
                    angle = 2 * np.pi * n / neighbors
                    x = int(j + radius * np.cos(angle))
                    y = int(i - radius * np.sin(angle))
                    if int(gray[y, x]) >= center:
                        code |= (1 << n)
                lbp[i, j] = code

        # 分 grid 统计直方图
        h_step = gray.shape[0] // grid_y
        w_step = gray.shape[1] // grid_x
        histograms = []
        for gy in range(grid_y):
            for gx in range(grid_x):
                cell = lbp[gy * h_step:(gy + 1) * h_step,
                           gx * w_step:(gx + 1) * w_step]
                hist, _ = np.histogram(cell.ravel(), bins=256, range=(0, 256))
                histograms.append(hist.astype(np.float32))
        feature = np.concatenate(histograms)
        feature /= (np.linalg.norm(feature) + 1e-7)
        return feature

    # ========== 加载模型 ==========

    def load_model(self, model_path=None):
        if model_path is None:
            model_path = self.model_path
        if os.path.exists(model_path):
            self.lbph.read(model_path)
            return True
        return False

    def load_names(self, dataset_path='dataset'):
        if os.path.isdir(dataset_path):
            self.names = sorted([
                d for d in os.listdir(dataset_path)
                if os.path.isdir(os.path.join(dataset_path, d))
            ])
        return self.names

    # ========== 识别 ==========

    def predict(self, face_roi):
        """
        对单个人脸ROI进行识别
        返回: (name, confidence) 或 (None, confidence)
        """
        if self.lbph is None:
            return None, 999
        try:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        except Exception:
            gray = face_roi
        if gray.size == 0:
            return None, 999
        gray = cv2.resize(gray, (200, 200))
        label, confidence = self.lbph.predict(gray)
        threshold = 70.0
        if self.db is not None:
            threshold = self.db.get_setting_float('recognition_threshold', 70.0)
        if confidence < threshold and label < len(self.names):
            return self.names[label], confidence
        return None, confidence

    def predict_by_features(self, face_roi):
        """
        使用特征向量比对方式进行识别（备选方案）
        提取待测人脸的LBPH直方图，与数据库中的人脸特征计算余弦相似度
        """
        if self.db is None:
            return None, 999
        try:
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        except Exception:
            gray = face_roi
        if gray.size == 0:
            return None, 999

        query_hist = self._extract_lbph_histogram(gray)
        all_features = self.db.load_face_features()

        best_name = None
        best_similarity = -1
        for name, data in all_features.items():
            stored_hist = data['feature_data']
            # 余弦相似度
            dot = np.dot(query_hist, stored_hist)
            norm = np.linalg.norm(query_hist) * np.linalg.norm(stored_hist)
            similarity = dot / (norm + 1e-7)
            if similarity > best_similarity:
                best_similarity = similarity
                best_name = name

        threshold = 0.5
        if self.db is not None:
            threshold = self.db.get_setting_float('recognition_threshold', 70.0) / 100.0
        if best_similarity > threshold:
            confidence = (1 - best_similarity) * 100
            return best_name, confidence
        return None, (1 - best_similarity) * 100
