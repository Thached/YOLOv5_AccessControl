"""
硬件控制模块
- 道闸（舵机PWM）控制
- 超声波测距（CS100A）
- 红外测温（MLX90614）
- 支持真实硬件 + 模拟模式
"""
import time
import threading


class HardwareController:
    """
    真实硬件控制器（通过 C 动态库）
    适用于龙芯 2K1000 / Linux 平台
    """

    def __init__(self, lib_path='app/SensorControl.so'):
        self.lib_path = lib_path
        self.dll = None
        self.available = False
        self._lock = threading.Lock()
        self._try_load()

    def _try_load(self):
        try:
            from ctypes import cdll
            self.dll = cdll.LoadLibrary(self.lib_path)
            self.dll.Sensor_init()
            self.available = True
            print(f"[硬件] 传感器动态库加载成功: {self.lib_path}")
        except Exception as e:
            print(f"[硬件] 加载失败({e})，将使用模拟模式")

    # ---- 道闸控制 ----

    def gate_open(self, delay_close=3.0):
        """开门，delay_close秒后自动关门"""
        if self.available:
            with self._lock:
                try:
                    self.dll.Sensor_Control(2)  # 舵机开门
                except Exception:
                    pass
        else:
            print("[模拟] 道闸: 开门")
        if delay_close > 0:
            t = threading.Timer(delay_close, self.gate_close)
            t.daemon = True
            t.start()

    def gate_close(self):
        """关门"""
        if self.available:
            with self._lock:
                try:
                    self.dll.Sensor_Control(3)  # 舵机关门
                except Exception:
                    pass
        else:
            print("[模拟] 道闸: 关门")

    # ---- 传感器 ----

    def sensor_trigger(self):
        """触发传感器采集"""
        if self.available:
            with self._lock:
                try:
                    self.dll.Sensor_Control(3)
                except Exception:
                    pass

    def get_distance(self):
        """超声波测距，返回值单位cm"""
        if self.available:
            with self._lock:
                try:
                    return self.dll.Sensor_Control(1) / 100.0
                except Exception:
                    pass
        # 模拟：返回合理范围内的随机距离
        import random
        return random.uniform(30, 80)

    def get_temperature(self):
        """红外测温，返回值单位°C"""
        if self.available:
            with self._lock:
                try:
                    return self.dll.Sensor_Control(4) / 100.0
                except Exception:
                    pass
        # 模拟：返回正常体温
        import random
        return round(random.uniform(36.0, 36.8), 1)

    def collect_sensor_data(self):
        """一次采集：触发传感器 → 读取距离和体温"""
        self.sensor_trigger()
        time.sleep(0.1)
        distance = self.get_distance()
        temperature = self.get_temperature()
        return distance, temperature


class SimulatedHardware(HardwareController):
    """纯模拟硬件（用于Windows开发调试）"""

    def __init__(self):
        self.dll = None
        self.available = False
        self._lock = threading.Lock()
        print("[硬件] 运行在完全模拟模式")

    def gate_open(self, delay_close=3.0):
        print(f"[模拟] 道闸: 开门 (延时{delay_close}s关闭)")
        if delay_close > 0:
            t = threading.Timer(delay_close, self.gate_close)
            t.daemon = True
            t.start()

    def gate_close(self):
        print("[模拟] 道闸: 关门")

    def sensor_trigger(self):
        pass

    def get_distance(self):
        import random
        return random.uniform(30, 80)

    def get_temperature(self):
        import random
        return round(random.uniform(36.0, 36.8), 1)


def create_hardware():
    """工厂函数：尝试加载真实硬件，失败则用模拟"""
    try:
        hw = HardwareController()
        if hw.available:
            return hw
    except Exception:
        pass
    return SimulatedHardware()
