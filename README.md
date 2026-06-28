# 智能门禁系统 — YOLOv5 Access Control

基于 YOLOv5 人脸检测 + LBPH 人脸识别的智能门禁系统，支持 **x86_64 开发** 与 **龙芯 2K1000 (MIPS64el) 部署**。

## 功能

- **YOLOv5 人脸检测** — 双后端自动切换（ultralytics / ONNX Runtime）
- **LBPH 人脸识别** — 特征直方图比对，支持 SQLite 存储特征
- **门禁控制** — 超声波测距 + 红外测温 + 舵机道闸 + 语音播报
- **PyQt5 图形界面** — 摄像头预览、通行记录查询、系统设置
- **跨平台** — Ubuntu 24 (x86_64) 开发，龙芯 2K1000 (MIPS64el) 部署

## 项目结构

```
YOLOv5_AccessControl/
├── main.py                  # 主程序入口
├── core/                    # 核心模块
│   ├── face_detector.py     # YOLOv5 人脸检测 (ultralytics / ONNX 双后端)
│   ├── face_recognizer.py   # LBPH 人脸特征提取与识别
│   ├── database.py          # SQLite 数据库 (用户/特征/记录/设置)
│   └── hardware.py          # 硬件抽象层 (C 驱动 / 模拟回退)
├── ui/                      # PyQt5 界面
│   ├── main_window.py       # 主窗口 (3 标签页 + 暗色主题)
│   └── login.py             # 登录对话框
├── utils/face_utils.py      # 中文渲染、中文路径支持
├── scripts/convert_yolo.py  # 模型转换: .pt → ONNX → INT8 量化
├── model/                   # 模型文件
│   ├── yolov5su.onnx        # ONNX 模型 (FP32, 640×640)
│   ├── yolov5su_int8.onnx   # ONNX 模型 (INT8 量化, 320×320)
│   └── onnxruntime-*.whl    # MIPS64el 交叉编译 onnxruntime
├── C_driver/                # C 硬件驱动源码 (GPIO / I2C / PWM)
├── docs/                    # 文档
│   └── 龙芯2K1000部署指南.md  # 详细部署指南
└── dataset/                 # 人脸数据集 (录入时自动生成)
```

## 快速开始 (开发环境)

### 环境要求

- Ubuntu 24.04 / Windows 10+
- Python 3.8+
- USB 摄像头

### 安装

```bash
# 安装系统依赖
sudo apt-get install -y python3-pyqt5 python3-opencv espeak

# 安装 Python 包
pip install ultralytics opencv-contrib-python numpy pillow pyttsx3

# 克隆项目
git clone https://github.com/Thached/YOLOv5_AccessControl.git
cd YOLOv5_AccessControl

# 运行
python main.py
```

首次运行会自动下载 `yolov5su.pt`、创建数据库、初始化 admin 账号（密码: `admin123`）。

## 龙芯 2K1000 部署

### 流程概览

```
Ubuntu 24 (x86_64)                    龙芯 2K1000 (MIPS64el)
─────────────────                     ──────────────────────
① 导出 ONNX 模型    ──── scp ───→   Python 3.x
② 交叉编译 ORT      ──── scp ───→   onnxruntime wheel
③ 交叉编译 C 驱动   ──── scp ───→   SensorControl.so
④ 传输源码          ──── scp ───→   main.py / core / ui / utils
```

### 步骤一：导出 ONNX 模型

```bash
# 标准导出
python scripts/convert_yolo.py --model yolov5su

# 龙芯推荐：低分辨率 + INT8 量化
python scripts/convert_yolo.py --model yolov5su --img-size 320 --quantize
```

产物：`model/yolov5su.onnx` (FP32) 和 `model/yolov5su_int8.onnx` (INT8)。

### 步骤二：安装 MIPS64 交叉编译工具链

```bash
# Ubuntu 24 一键安装
sudo apt-get install -y gcc-mips64el-linux-gnuabi64 g++-mips64el-linux-gnuabi64
```

### 步骤三：交叉编译 onnxruntime

```bash
git clone --depth 1 --branch v1.18.0 https://github.com/microsoft/onnxruntime.git
cd onnxruntime

# 创建工具链文件 ~/mips64el_toolchain.cmake (见部署指南)

# 编译（注意：需要代理访问 GitHub）
./build.sh \
    --config MinSizeRel \
    --build_shared_lib \
    --enable_pybind \
    --build_wheel \
    --parallel $(nproc) \
    --compile_no_warning_as_error \
    --skip_tests \
    --cmake_extra_defines CMAKE_TOOLCHAIN_FILE=~/mips64el_toolchain.cmake \
    --build_dir build_mips64
```

产物：`build_mips64/MinSizeRel/dist/onnxruntime-*.whl`

> 也可直接使用仓库中预编译的 `model/onnxruntime-1.18.0-cp311-cp311-linux_mips64el.whl`。

### 步骤四：交叉编译硬件驱动

```bash
cd C_driver
mips64el-linux-gnuabi64-gcc -shared -fPIC -O2 -o SensorControl.so \
    gpio.c i2c/smbus.c i2c/i2cbusses.c \
    src/SensorControl.c src/MLX90614.c src/cs100a.c src/servo.c \
    -I. -Isrc -Ii2c
mips64el-linux-gnuabi64-strip SensorControl.so
mv SensorControl.so ../app/
```

### 步骤五：传输到龙芯

```bash
LOONGSON_IP="192.168.1.100"
ssh root@$LOONGSON_IP "mkdir -p ~/YOLOv5_AccessControl/{core,ui,utils,model,app,data}"

scp main.py root@$LOONGSON_IP:~/YOLOv5_AccessControl/
scp core/*.py root@$LOONGSON_IP:~/YOLOv5_AccessControl/core/
scp ui/*.py ui/*.png root@$LOONGSON_IP:~/YOLOv5_AccessControl/ui/
scp utils/*.py root@$LOONGSON_IP:~/YOLOv5_AccessControl/utils/
scp model/yolov5su.onnx root@$LOONGSON_IP:~/YOLOv5_AccessControl/model/
scp model/onnxruntime-*.whl app/SensorControl.so root@$LOONGSON_IP:~/YOLOv5_AccessControl/
```

### 步骤六：龙芯端安装运行

```bash
# 安装依赖
sudo apt-get install -y python3 python3-pip python3-pyqt5 python3-opencv espeak
pip3 install numpy pillow pyttsx3
pip3 install onnxruntime-1.18.0-cp311-cp311-linux_mips64el.whl

# 运行
cd ~/YOLOv5_AccessControl
python3 main.py
```

## 模型说明

| 模型 | 输入尺寸 | 大小 | 适用场景 |
|------|---------|------|---------|
| `yolov5su.pt` | 640×640 | - | 开发环境 (PyTorch) |
| `yolov5su.onnx` | 640×640 | 35 MB | 龙芯部署 (FP32) |
| `yolov5su_int8.onnx` | 320×320 | 9 MB | 龙芯推荐 (INT8, 快 4 倍) |

> `face_detector.py` 默认加载 `yolov5su.onnx`。使用 INT8 模型需重命名为 `yolov5su.onnx` 或修改代码第 65 行。

## 硬件支持

| 硬件 | 接口 | 说明 |
|------|------|------|
| FS90 舵机 | I2C (GP7101 DAC, 0x58) | 道闸控制 |
| MLX90614 | I2C (0x5A) | 红外测温 |
| CS100A | GPIO (触发/回波) | 超声波测距 |

无硬件时自动降级为模拟模式，不影响人脸识别功能。

## 详细文档

- [龙芯 2K1000 详细部署指南](docs/龙芯2K1000部署指南.md) — 含依赖安装、常见问题、性能调优

## License

MIT
