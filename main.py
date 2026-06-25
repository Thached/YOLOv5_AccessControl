"""
智能门禁系统 - YOLOv5版 主程序入口
=====================================
- YOLOv5 (yolov5su.pt) 人脸检测
- LBPH 特征提取 + 人脸识别
- SQLite 数据库存储特征与通行记录
- Qt GUI（预览 / 记录查询 / 系统设置）
- 道闸控制 + 超声波测距 + 红外测温
"""
import os
import sys
import io
import time
import json
import datetime
import threading
import numpy as np
import cv2

# 将工作目录切换到项目根目录，确保所有相对路径正确
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

from core.database import Database
from core.face_detector import FaceDetector
from core.face_recognizer import FaceRecognizer
from core.hardware import create_hardware
from ui.main_window import MainWindow
from ui.login import Ui_Dialog
from utils.face_utils import (
    imwrite_unicode, put_chinese_text, _CHINESE_FONT_PATH
)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# ==================== 语音播报 ====================

_CN_NUM = {'0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
           '5': '五', '6': '六', '7': '七', '8': '八', '9': '九', '.': '点'}


import queue as _queue
import sys as _sys

_speech_queue = _queue.Queue()


def _speech_worker():
    """语音播报 worker——平台自适应：
       Windows: 直连 SAPI 绕过 pyttsx3 的引擎复用 bug
       Linux/MIPS: pyttsx3 + espeak（无此 bug，单引擎复用即可）"""
    engine = None

    if _sys.platform == 'win32':
        # Windows: 用原生 SAPI，pyttsx3 的 SAPI 驱动引擎无法复用
        try:
            import pythoncom
            pythoncom.CoInitialize()
            from win32com.client import Dispatch
            engine = Dispatch("SAPI.SpVoice")
            engine.Rate = 1
            print('[语音] Windows SAPI 就绪')
        except Exception as e:
            print(f'[语音] SAPI 不可用: {e}')
    else:
        # Linux (龙芯 MIPS64): 用 pyttsx3 + espeak，引擎可安全复用
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('voice', 'zh')
            engine.setProperty('rate', 180)
            print(f'[语音] pyttsx3 就绪 (平台: {_sys.platform})')
        except Exception as e:
            print(f'[语音] pyttsx3 不可用: {e}')

    while True:
        msg = _speech_queue.get()
        if msg is None:
            break
        print(f'[语音] 播报: {msg}')

        if engine is None:
            continue

        try:
            if _sys.platform == 'win32':
                engine.Speak(msg)
            else:
                engine.say(msg)
                engine.runAndWait()
        except Exception as e:
            print(f'[语音] 播报失败: {e}')
            # Linux 上尝试重建 pyttsx3 引擎
            if _sys.platform != 'win32':
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.setProperty('voice', 'zh')
                    engine.setProperty('rate', 180)
                except Exception:
                    engine = None


_sw = threading.Thread(target=_speech_worker, daemon=True)
_sw.start()


def say_zh(msg):
    """放入语音队列，worker 线程串行播报"""
    if _sw.is_alive():
        print(f'[语音] 入队: {msg}')
        _speech_queue.put(msg)
    else:
        print(f'[语音] worker 已死，丢弃: {msg}')


def temp_to_zh(num):
    """体温数值 → 中文读法"""
    s = str(int(num * 100))
    if len(s) == 4:
        prefix = '' if s[0] == '1' else _CN_NUM[s[0]]
        result = f"{prefix}十{_CN_NUM[s[1]]}点{_CN_NUM[s[2]]}{_CN_NUM[s[3]]}度"
    elif len(s) == 3:
        result = f"{_CN_NUM[s[0]]}点{_CN_NUM[s[1]]}{_CN_NUM[s[2]]}度"
    else:
        return "温度测量错误"
    return "体温" + result


# ==================== 全局状态 ====================

class AppState:
    def __init__(self):
        self.logged_in = False
        self.is_admin = False
        self.username = ''
        self.temperature = 0.0
        self.distance = 0.0
        self.last_result = None
        self.last_result_time = time.time()
        self.fail_count = 0
        self.locked_until = 0
        self.was_locked = False  # 用于检测锁定→解锁的转换


# ==================== 工作线程 ====================

class CameraThread(QThread):
    """摄像头实时预览线程"""
    signal_frame = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        cam = cv2.VideoCapture(0)
        while cam.isOpened() and self.running:
            ret, img = cam.read()
            if ret:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, c = img.shape
                qimg = QImage(img.data, w, h, w * 3, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                if self.running:
                    self.signal_frame.emit(pixmap)
            else:
                self.msleep(10)
        cam.release()

    def stop(self):
        self.running = False


class FaceDetectThread(QThread):
    """人脸检测 + 识别线程（使用 yolov5su.pt）"""
    signal_frame = pyqtSignal(object)

    def __init__(self, detector, recognizer):
        super().__init__()
        self.running = True
        self.detector = detector
        self.recognizer = recognizer

    def run(self):
        cam = cv2.VideoCapture(0)
        while cam.isOpened() and self.running:
            ret, img = cam.read()
            if not ret:
                continue
            try:
                faces = self.detector.detect(img)
                names = []
                for (x, y, w, h, conf) in faces:
                    cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    face_roi = img[y:y + h, x:x + w]
                    if face_roi.size > 0:
                        name, score = self.recognizer.predict(face_roi)
                        label = f'{name} {score:.1f}' if name else 'Unknown'
                        put_chinese_text(img, label, (x, y - 25),
                                         font_size=22, color=(0, 0, 255))
                        names.append(name)
                self.detector.annotate(img, faces, names, color=(0, 255, 0))

                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, c = img.shape
                qimg = QImage(img.data, w, h, w * 3, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                if self.running:
                    self.signal_frame.emit(pixmap)
            except Exception:
                continue
        cam.release()

    def stop(self):
        self.running = False


class EnrollThread(QThread):
    """人脸录入线程（使用 yolov5su.pt 检测人脸 + 采集20张）"""
    signal_frame = pyqtSignal(object)
    signal_status = pyqtSignal(str)

    def __init__(self, name, detector, db):
        super().__init__()
        self.running = True
        self.name = name
        self.detector = detector
        self.db = db

    def run(self):
        import datetime
        dataset_dir = os.path.join('dataset', self.name)
        os.makedirs(dataset_dir, exist_ok=True)

        cam = cv2.VideoCapture(0)
        count = 0
        start_time = datetime.datetime.now()
        last_capture = time.time()

        while cam.isOpened() and self.running and count < 20:
            elapsed = (datetime.datetime.now() - start_time).seconds
            ret, img = cam.read()
            if not ret:
                continue

            try:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                h, w = img.shape[:2]
                x_min, y_min = int(w * 0.2), int(h * 0.15)
                x_max, y_max = int(w * 0.8), int(h * 0.85)

                # 引导圆
                cv2.circle(img, (w // 2, h // 2), int(h / 2.5), (0, 255, 0), 3)

                # 使用 yolov5su.pt 检测人脸
                faces, _ = self.detector.detect_in_roi(
                    img, x_min, y_min, x_max, y_max)

                if elapsed <= 5:
                    self.signal_status.emit(f'{5 - elapsed}秒后开始录入...')
                elif len(faces) > 0:
                    x, y, fw, fh, _ = faces[0]
                    cv2.rectangle(img, (x, y), (x + fw, y + fh), (0, 0, 255), 2)
                    gray_roi = cv2.resize(
                        gray[y:y + fh, x:x + fw], (200, 200),
                        interpolation=cv2.INTER_LINEAR)

                    if time.time() - last_capture > 0.6:
                        count += 1
                        save_path = os.path.join(dataset_dir, f'{count}.jpg')
                        imwrite_unicode(save_path, gray_roi)
                        self.signal_status.emit(f'保存第{count}张，还剩{20 - count}张')
                        last_capture = time.time()
                else:
                    if elapsed > 5:
                        self.signal_status.emit('未检测到人脸，请对准摄像头')

                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, c = img.shape
                qimg = QImage(img.data, w, h, w * 3, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                if self.running:
                    self.signal_frame.emit(pixmap)
            except Exception:
                continue

        cam.release()
        if count >= 20:
            self.signal_status.emit('model done')
            self.signal_status.emit(f'录入完成：{self.name}，共{count}张')
        else:
            self.signal_status.emit('录入中断')

    def stop(self):
        self.running = False


class TrainThread(QThread):
    """模型训练线程"""
    signal_status = pyqtSignal(str)

    def __init__(self, recognizer, db):
        super().__init__()
        self.recognizer = recognizer
        self.db = db

    def run(self):
        try:
            n, m = self.recognizer.train_from_dataset(
                progress_cb=lambda msg: self.signal_status.emit(msg))
            self.signal_status.emit(f'训练完成：{n}人，{m}张图片')
            time.sleep(2)
            self.signal_status.emit('model done')
        except Exception as e:
            self.signal_status.emit(f'训练失败：{e}')


class AutoRunThread(QThread):
    """自动运行线程（门禁核心，使用 yolov5su.pt）"""
    signal_frame = pyqtSignal(object)
    signal_status = pyqtSignal(str)

    def __init__(self, detector, recognizer, hardware, db, state):
        super().__init__()
        self.running = True
        self.detector = detector
        self.recognizer = recognizer
        self.hw = hardware
        self.db = db
        self.state = state

    def run(self):
        temp_limit = self.db.get_setting_float('temp_limit', 37.2)
        dist_min = self.db.get_setting_float('dist_min', 10)
        dist_max = self.db.get_setting_float('dist_max', 120)
        interval = self.db.get_setting_int('auto_interval', 4)
        gate_delay = self.db.get_setting_float('gate_delay', 3)
        retry_limit = self.db.get_setting_int('retry_limit', 3)
        lockout_dur = self.db.get_setting_int('lockout_duration', 30)
        snapshot_strangers = self.db.get_setting_bool('stranger_snapshot', True)

        cam = cv2.VideoCapture(0)
        last_check = time.time()

        while cam.isOpened() and self.running:
            ret, img = cam.read()
            if not ret:
                continue

            try:
                h, w = img.shape[:2]
                x_min, y_min = int(w * 0.2), int(h * 0.15)
                x_max, y_max = int(w * 0.8), int(h * 0.85)
                cv2.circle(img, (w // 2, h // 2), int(h / 2.5), (0, 255, 0), 3)

                # 每 interval 秒执行一次识别
                if time.time() - last_check > interval:
                    last_check = time.time()

                    # 检查锁定状态
                    if time.time() < self.state.locked_until:
                        remaining = int(self.state.locked_until - time.time())
                        self.signal_status.emit(f'已锁定，{remaining}秒后重试')
                        self.state.was_locked = True
                    else:
                        if self.state.was_locked:
                            say_zh('锁定已解除，识别已恢复')
                            self.state.was_locked = False
                        self._do_identify(img, x_min, y_min, x_max, y_max,
                                          temp_limit, dist_min, dist_max,
                                          gate_delay, retry_limit, lockout_dur,
                                          snapshot_strangers)

                # 超过30秒无结果则清空
                if time.time() - self.state.last_result_time > 30:
                    self.signal_status.emit('')
                else:
                    if self.state.last_result:
                        self.signal_status.emit(self.state.last_result)

                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                h, w, c = img.shape
                qimg = QImage(img.data, w, h, w * 3, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                if self.running:
                    self.signal_frame.emit(pixmap)
            except Exception:
                continue
        cam.release()

    def _do_identify(self, img, x_min, y_min, x_max, y_max,
                     temp_limit, dist_min, dist_max,
                     gate_delay, retry_limit, lockout_dur,
                     snapshot_strangers):
        distance, temperature = self.hw.collect_sensor_data()
        self.state.temperature = temperature
        self.state.distance = distance

        # 使用 yolov5su.pt 检测人脸
        faces, _ = self.detector.detect_in_roi(img, x_min, y_min, x_max, y_max)

        rid = None
        if distance < dist_min:
            rid = '距离太近，请站远点！'
        elif distance > dist_max:
            rid = '距离太远，请靠近点！'
        elif temperature >= temp_limit:
            rid = f'体温异常：{temperature:.1f}°C'
            say_zh(f'体温异常，{temp_to_zh(temperature)}')
            self.state.fail_count = 0
        elif len(faces) > 0:
            x, y, fw, fh, _ = faces[0]
            face_roi = img[y:y + fh, x:x + fw]
            if face_roi.size > 0:
                name, confidence = self.recognizer.predict(face_roi)
                if name is not None:
                    rid = f'{name}  {temperature:.1f}°C  {distance:.0f}cm'
                    self.state.fail_count = 0
                    # 体温正常 → 开门，识别成功不播报
                    if temperature < temp_limit:
                        self.hw.gate_open(gate_delay)
                    # 记录通行成功
                    username = self.state.username or name
                    self.db.add_access_record(
                        username, name, 'success', confidence,
                        temperature, distance, img)
                else:
                    rid = '无法识别身份！'
                    self.state.fail_count += 1
                    if snapshot_strangers:
                        self.db.add_access_record(
                            self.state.username or 'unknown', 'unknown',
                            'fail', confidence, temperature, distance, img)
                    say_zh('陌生人出现，请注意')
            else:
                rid = '超出检测范围！'
        else:
            self.state.last_result = None
            self.state.last_result_time = time.time()
            return

        self.state.last_result = rid
        self.state.last_result_time = time.time()

        if self.state.fail_count >= retry_limit:
            self.state.locked_until = time.time() + lockout_dur
            self.signal_status.emit(
                f'识别失败{retry_limit}次，锁定{lockout_dur}秒')
            say_zh('识别失败次数过多，系统已锁定')
            self.state.fail_count = 0

    def stop(self):
        self.running = False


# ==================== 对话框 ====================

class LoginDialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle('用户登录')


class RegisterDialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle('用户注册')


class SignoutDialog(QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle('用户注销')
        self.lineEdit_2.setVisible(False)


# ==================== 应用程序 ====================

class AccessControlApp:
    """应用程序主控制器"""

    def __init__(self):
        self.db = Database()
        self.hw = create_hardware()
        self.state = AppState()
        self._active_thread = None

        # 初始化人脸检测器和识别器（统一使用 yolov5su.pt）
        conf = self.db.get_setting_float('confidence_threshold', 0.5)
        self.detector = FaceDetector(confidence=conf)
        self.recognizer = FaceRecognizer(db=self.db)
        self.recognizer.load_names()
        model_path = self.db.get_setting('model_path') or './model/model.xml'
        if os.path.exists(model_path):
            self.recognizer.load_model(model_path)

        # 创建UI
        self.window = MainWindow(self.db, self.hw)
        self._bind_callbacks()
        self._update_backend_label()

    def _bind_callbacks(self):
        w = self.window
        w.login_callback = self._handle_login
        w.register_callback = self._handle_register
        w.signout_callback = self._handle_signout
        w.auto_run_callback = self._handle_auto_run
        w.camera_callback = self._handle_camera
        w.face_detect_callback = self._handle_face_detect
        w.enroll_callback = self._handle_enroll
        w.train_callback = self._handle_train

    def _update_backend_label(self):
        self.window.set_backend_label('检测: YOLOv5su')
        self.window.backend_label.setStyleSheet(
            'color: #a6e3a1; font-size: 13px;')

    # ---- 管理操作 ----

    def _handle_login(self):
        w = self.window
        if w.act_login.text() == '退出':
            # 登出
            w.act_login.setText('登录')
            self.state.logged_in = False
            self.state.is_admin = False
            self.state.username = ''
            w.set_user_label('未登录')
            w.act_register.setEnabled(False)
            w.act_signout.setEnabled(False)
            w.act_auto_run.setEnabled(False)
            return

        dlg = LoginDialog(w)
        if dlg.exec_() == QDialog.Accepted:
            account = dlg.lineEdit.text()
            password = dlg.lineEdit_2.text()
            user = self.db.verify_user(account, password)
            if user:
                self.state.logged_in = True
                self.state.is_admin = (user['role'] == 'admin')
                self.state.username = account
                w.act_login.setText('退出')
                w.set_user_label(f'当前用户: {account} ({user["role"]})')
                w.act_auto_run.setEnabled(True)
                if self.state.is_admin:
                    w.act_register.setEnabled(True)
                    w.act_signout.setEnabled(True)
                QMessageBox.about(w, '提示', f'用户 {account} 登录成功！')
            else:
                QMessageBox.critical(w, '错误', '账号或密码错误！')

    def _handle_register(self):
        w = self.window
        if not self.state.is_admin:
            QMessageBox.critical(w, '错误', '仅管理员可注册新用户！')
            return
        dlg = RegisterDialog(w)
        if dlg.exec_() == QDialog.Accepted:
            account = dlg.lineEdit.text().strip()
            password = dlg.lineEdit_2.text()
            if not account or not password:
                QMessageBox.critical(w, '错误', '账号密码不能为空！')
                return
            if self.db.add_user(account, password):
                QMessageBox.about(w, '成功', f'用户 {account} 注册成功！')
            else:
                QMessageBox.critical(w, '失败', '该用户已存在！')

    def _handle_signout(self):
        w = self.window
        if not self.state.is_admin:
            QMessageBox.critical(w, '错误', '仅管理员可注销用户！')
            return
        dlg = SignoutDialog(w)
        # 显示用户列表
        users = self.db.get_all_users()
        dlg.label_2.setText('用户列表')
        dlg.label_2.setStyleSheet('background: yellow')
        dlg.label_2.setToolTip('  '.join([u['username'] for u in users]))
        if dlg.exec_() == QDialog.Accepted:
            account = dlg.lineEdit.text().strip()
            if not account:
                return
            if account == 'admin':
                QMessageBox.critical(w, '错误', 'admin不可注销！')
                return
            if self.db.delete_user(account):
                self.db.delete_face_features(account)
                QMessageBox.about(w, '成功', f'用户 {account} 已注销')
            else:
                QMessageBox.critical(w, '失败', f'用户 {account} 不存在')

    # ---- 功能操作 ----

    def _handle_auto_run(self):
        w = self.window
        if w.act_auto_run.text() == '自动运行':
            if not self.state.logged_in:
                QMessageBox.critical(w, '错误', '请先登录！')
                return
            w.act_auto_run.setText('停止运行')
            self._active_thread = AutoRunThread(
                self.detector, self.recognizer, self.hw, self.db, self.state)
            self._active_thread.start()
            self._active_thread.signal_frame.connect(w.set_video_pixmap)
            self._active_thread.signal_status.connect(w.set_result_text)
            w._disable_all()
        else:
            if self._active_thread:
                self._active_thread.stop()
            w.act_auto_run.setText('自动运行')
            w._restore_all_buttons()
            w.video_label.clear()
            w.video_label.setText('摄像头未启动')

    def _handle_camera(self):
        w = self.window
        if w.act_camera.text() == '开启摄像头':
            w.act_camera.setText('关闭摄像头')
            w.video_label.setText('相机启动中...')
            self._active_thread = CameraThread()
            self._active_thread.start()
            self._active_thread.signal_frame.connect(w.set_video_pixmap)
            w._disable_fn_buttons(except_act=w.act_camera)
        else:
            if self._active_thread:
                self._active_thread.stop()
            w.act_camera.setText('开启摄像头')
            w._restore_all_buttons()
            w.video_label.clear()
            w.video_label.setText('摄像头未启动')

    def _handle_face_detect(self):
        w = self.window
        if w.act_face_detect.text() == '启动人脸识别':
            w.act_face_detect.setText('关闭人脸识别')
            w.video_label.setText('模型加载中...')
            self._active_thread = FaceDetectThread(self.detector, self.recognizer)
            self._active_thread.start()
            self._active_thread.signal_frame.connect(w.set_video_pixmap)
            w._disable_fn_buttons(except_act=w.act_face_detect)
        else:
            if self._active_thread:
                self._active_thread.stop()
            w.act_face_detect.setText('启动人脸识别')
            w._restore_all_buttons()
            w.video_label.clear()
            w.video_label.setText('摄像头未启动')

    def _handle_enroll(self):
        w = self.window
        if w.act_enroll.text() == '录入人脸数据':
            w.act_enroll.setText('停止录入')
            name, ok = QInputDialog.getText(w, '录入人脸', '请输入姓名:')
            if ok and name.strip():
                self._active_thread = EnrollThread(name.strip(), self.detector, self.db)
                self._active_thread.start()
                self._active_thread.signal_frame.connect(w.set_video_pixmap)
                self._active_thread.signal_status.connect(w.set_result_text)
                w._disable_fn_buttons(except_act=w.act_enroll)
            else:
                w.act_enroll.setText('录入人脸数据')
        else:
            if self._active_thread:
                self._active_thread.stop()
            w.act_enroll.setText('录入人脸数据')
            w._restore_all_buttons()
            w.video_label.clear()
            w.video_label.setText('摄像头未启动')

    def _handle_train(self):
        w = self.window
        self._active_thread = TrainThread(self.recognizer, self.db)
        self._active_thread.start()
        self._active_thread.signal_status.connect(w.set_result_text)
        w._disable_all()

    # ---- 启动 ----

    def run(self):
        self.window.show()
        self.window.update_statistics()


# ==================== 预留：admin 初始化 ====================

def init_admin_user(db):
    """首次运行时初始化admin账号"""
    if not db.user_exists('admin'):
        db.add_user('admin', 'admin123', 'admin')
        print("[初始化] 已创建 admin 账号 (密码: admin123)")


# ==================== 入口 ====================

if __name__ == '__main__':
    app = QApplication(sys.argv)
    db = Database()
    init_admin_user(db)
    ctrl = AccessControlApp()
    ctrl.run()
    sys.exit(app.exec())
