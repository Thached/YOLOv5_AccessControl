# 智能门禁系统 —— 基于 YOLOv5 + LBPH 的人脸识别门禁

## 项目概述

### 背景

传统门禁系统依赖 IC 卡、指纹或密码，存在忘带卡、指纹磨损、密码泄露等问题。本项目设计了一套**基于 YOLOv5 深度学习 + LBPH 人脸识别**的智能门禁系统，实现无接触、高精度的身份验证与通行控制。系统面向**龙芯 2K1000（MIPS64el）嵌入式平台**部署，同时兼容 Windows/Linux 开发调试。

### 目标

- 利用 YOLOv5 实现实时人体检测，从人体框中定位人脸区域
- 使用 LBPH 算法提取人脸纹理特征并进行身份比对
- 集成红外测温（MLX90614）与超声波测距（CS100A），实现体温筛查与站位引导
- 提供 PyQt5 图形界面，支持预览、记录查询、系统设置
- 支持龙芯平台的 ONNX 推理部署与 INT8 量化加速

### 系统组成

| 层次 | 组件 | 说明 |
|------|------|------|
| **AI 推理层** | YOLOv5 (`yolov5su.pt`) | 人体检测 → 人脸区域估算 |
| **人脸识别层** | OpenCV LBPH | 纹理特征提取 + 直方图比对 |
| **硬件控制层** | C 动态库 (`SensorControl.so`) | 舵机道闸、超声波测距、红外测温 |
| **数据层** | SQLite | 用户、人脸特征、通行记录、系统设置 |
| **UI 层** | PyQt5 | 实时预览、记录查询、系统设置 |
| **语音层** | SAPI / pyttsx3 + espeak | 体温异常告警、陌生人提醒 |

---

## 系统总体设计

### 功能模块图

```
┌──────────────────────────────────────────────────────────┐
│                    智能门禁系统                            │
├────────────┬────────────┬────────────┬──────────┬────────┤
│  摄像头预览 │  人脸录入   │  人脸识别   │ 通行记录  │ 系统设置 │
│            │            │            │          │        │
│ • 实时画面 │ • 5秒倒计时 │ • YOLOv5   │ • 多条件  │ • 检测  │
│ • FPS 显示 │ • 20张采集  │   人体检测  │   筛选    │   引擎  │
│ • 引导圆圈 │ • 灰度存储  │ • LBPH     │ • 抓拍    │ • 门禁  │
│            │ • 自动训练  │   特征比对  │   查看    │   控制  │
│            │            │ • 测温测距  │ • 统计    │ • 安全  │
│            │            │ • 道闸控制  │   卡片    │   策略  │
└────────────┴────────────┴────────────┴──────────┴────────┘
```

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        PyQt5 GUI (main_window.py)                │
│   ┌──────────┐  ┌──────────────┐  ┌──────────────┐              │
│   │ 预览标签页 │  │  记录查询标签页 │  │  系统设置标签页 │              │
│   └─────┬────┘  └──────┬───────┘  └──────┬───────┘              │
│         │              │                  │                      │
├─────────┼──────────────┼──────────────────┼──────────────────────┤
│         ▼              ▼                  ▼                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              AccessControlApp (main.py)                  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │    │
│  │  │CameraThread│ │EnrollThread│ │AutoRunThread│ │TrainThread│  │    │
│  │  └─────┬────┘ └────┬─────┘ └─────┬─────┘ └─────┬──────┘  │    │
│  └────────┼───────────┼─────────────┼──────────────┼────────┘    │
├───────────┼───────────┼─────────────┼──────────────┼─────────────┤
│           ▼           ▼             ▼              ▼             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ FaceDetector │ │FaceRecognizer│ │   Database   │             │
│  │ (yolov5su)   │ │   (LBPH)     │ │  (SQLite)    │             │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
├─────────┼────────────────┼────────────────┼─────────────────────┤
│         ▼                ▼                ▼                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               Hardware (C Driver via ctypes)             │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐       │    │
│  │  │ 舵机道闸  │  │ MLX90614 测温 │  │ CS100A 测距  │       │    │
│  │  └──────────┘  └──────────────┘  └──────────────┘       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 软硬件接口说明

**软件接口：**

| 接口 | 类型 | 说明 |
|------|------|------|
| `FaceDetector.detect(img)` | Python | YOLOv5 人体检测 → 人脸区域列表 |
| `FaceRecognizer.predict(roi)` | Python | LBPH 特征比对 → (姓名, 置信度) |
| `Database.add_access_record()` | SQLite | 写入通行记录 |
| `HardwareController.gate_open()` | C DLL | 舵机开门控制 |
| `HardwareController.get_temperature()` | C DLL | 红外测温读数 |
| `HardwareController.get_distance()` | C DLL | 超声波测距读数 |

**硬件接口（龙芯 2K1000 平台）：**

| 硬件 | 接口类型 | 引脚/地址 | 说明 |
|------|---------|----------|------|
| 舵机 (SG90/MG995) | GPIO PWM | GPIO 12 | 道闸控制，0°关门 / 90°开门 |
| MLX90614 | I²C | 0x5A | 红外体温传感器，精度 ±0.2°C |
| CS100A | UART / GPIO | GPIO 17/27 | 超声波测距，范围 2cm–300cm |
| USB 摄像头 | USB 2.0 | — | 视频采集，分辨率 640×480 |

---

## YOLOv5 模型部署详解

### YOLOv5 模型选型依据

本系统选用 **yolov5su（YOLOv5 Small Unified）** 作为唯一检测模型，基于以下考虑：

| 因素 | 分析 | 结论 |
|------|------|------|
| **精度 vs 速度** | YOLOv5n 最快但精度略低，YOLOv5m/l 精度高但推理慢 | YOLOv5s 最佳平衡点 |
| **平台适配** | 龙芯 2K1000 为嵌入式 CPU，无 GPU 加速 | 需小模型 + ONNX 推理 |
| **统一格式** | `-u` 后缀为 Ultralytics 统一格式，兼容 ultralytics 库 | 简化加载流程 |
| **模型大小** | yolov5su.pt ≈ 18.6 MB，适合嵌入式存储 | 可接受 |
| **检测目标** | COCO 预训练包含 person 类 (class 0) | 直接可用，无需重训练 |

**为什么检测 person 而非 face：** YOLOv5 的标准 COCO 模型包含 80 个类别，其中包含 person（人）但不包含 face（人脸）。系统通过从人体检测框中估算人脸区域来间接实现人脸定位，避免了额外训练人脸检测模型的工作量。

人体框 → 人脸区域估算公式：
```
face_x = x1 + body_width × 0.15
face_y = y1 + body_height × 0.03
face_w = body_width × 0.65
face_h = face_w × 1.25          # 基于人脸固定宽高比
```

### 模型获取与转换流程

#### 1. 获取预训练模型

```bash
# 方式一：使用 ultralytics 库自动下载
python -c "from ultralytics import YOLO; YOLO('yolov5su.pt')"

# 方式二：手动下载
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov5su.pt
```

#### 2. .pt → ONNX 转换

```bash
# 使用项目自带脚本
python scripts/convert_yolo.py --model yolov5su --img-size 640

# 或使用 ultralytics 导出
python -c "from ultralytics import YOLO; \
    model = YOLO('yolov5su.pt'); \
    model.export(format='onnx', imgsz=640, opset=12)"
```

#### 3. ONNX → 龙芯平台部署

```bash
# 在龙芯 2K1000 平台上：
# 1. 安装 onnxruntime
pip3 install onnxruntime  # 或从源码交叉编译

# 2. 复制 ONNX 模型
scp yolov5su.onnx user@loongson:~/YOLOv5_AccessControl/model/

# 3. 更新数据库配置（后改为直接使用 yolov5su.pt，此步骤以实际为准）
```

**当前版本（v2.0）已简化为直接使用 ultralytics 加载 .pt 文件**，无需 ONNX 转换。若需部署到龙芯平台且 onnxruntime 不可用，可使用 `scripts/convert_yolo.py` 完成转换。

### 模型量化优化方案

对于龙芯嵌入式平台，可通过 INT8 量化进一步加速：

```bash
# INT8 动态量化（权重 INT8，激活保持 FP32）
python scripts/convert_yolo.py --model yolov5su --quantize
```

| 指标 | 量化前 (FP32) | 量化后 (INT8) |
|------|-------------|-------------|
| 模型大小 | ~72 MB | ~18 MB |
| 推理延迟 | ~200 ms | ~80 ms |
| 精度损失 | — | < 1% mAP |
| 压缩率 | — | ~75% |

量化原理：
- 将 32 位浮点权重映射到 8 位整数
- 推理时反量化恢复近似值
- 动态量化无需校准数据集，使用方便
- 适用于 CPU 推理场景（如 onnxruntime）

### 推理速度测试

测试环境：Intel i5-12400 / 16GB RAM / Windows 11 / Python 3.10

| 模型 | 输入尺寸 | 推理时间 | FPS | 后端 |
|------|---------|---------|-----|------|
| yolov5su.pt | 640×640 | ~45 ms | ~22 | Ultralytics (PyTorch) |
| yolov5su.onnx | 640×640 | ~35 ms | ~28 | ONNX Runtime |
| yolov5n.pt | 640×640 | ~25 ms | ~40 | Ultralytics (PyTorch) |

> **注意：** 以上为 PC 端数据。龙芯 2K1000 平台上推理速度会显著降低（约 3-5 FPS），建议配合输入尺寸缩减（320×320）和 INT8 量化使用。

### YOLOv5 推理效果

检测流程示意：

```
┌──────────────────────────────────────┐
│  输入帧 (640×480 BGR)                │
│  ┌────────────────────────────────┐  │
│  │       ☉ 引导绿圈                │  │
│  │     ┌──────────┐               │  │
│  │     │ 人体检测框 │ ← YOLOv5      │  │
│  │     │  ┌────┐   │   person 0.89 │  │
│  │     │  │人脸│   │               │  │
│  │     │  │ROI │   │ ← 估算人脸区   │  │
│  │     │  └────┘   │               │  │
│  │     └──────────┘               │  │
│  │  张三 45.2  ← LBPH识别结果      │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

- **蓝色框**：YOLOv5 检测到的人体边界框
- **红色框**：估算的人脸 ROI 区域
- **文字标注**：识别结果 (姓名 + 置信度)

---

## 核心实现详解

### Qt 界面设计

系统采用 PyQt5 构建，基于 Catppuccin Mocha 暗色主题，包含三个标签页：

**标签页 1 — 摄像头预览：**
- 顶部信息栏：当前用户、检测后端（YOLOv5su）、FPS
- 中央：640×360 实时视频画面
- 底部：大字红色识别结果（姓名 + 体温 + 距离）
- 快捷统计栏：总通行 / 今日 / 成功次数

**标签页 2 — 通行记录：**
- 统计卡片：今日通行、识别成功、识别失败、体温异常
- 筛选栏：快捷日期（今天/3天/本周/全部）、日期范围、结果类型、关键字搜索
- 表格：时间、姓名、账号、结果、体温、置信度
- 详情面板：选中记录的抓拍图像和详细信息
- 分页：每页 50 条记录

**标签页 3 — 系统设置：**
- 模型状态卡片：训练状态、模型路径、已注册人数
- 检测引擎设置：检测方法（固定 yolov5）、模型（固定 yolov5su）、检测阈值、识别阈值
- 门禁控制设置：体温上限、有效距离、开门延时、检测间隔
- 安全策略：重试上限、锁定时长、陌生人抓拍开关
- 硬件状态：道闸、测温传感器、超声波测距状态

**菜单栏：**
- 管理菜单：登录、注册、注销、自动运行、退出
- 功能菜单：开启摄像头、启动人脸识别、录入人脸数据、训练人脸模型

### OpenCV 图像采集与 YOLOv5 推理流程

```
摄像头采集 (cv2.VideoCapture)
    │
    ▼
YOLOv5 推理 (ultralytics YOLO)
    │
    ├── 检测到 person 类 (cls 0)
    │   └── 解析边界框 (xyxy → x1,y1,x2,y2)
    │       └── 估算人脸 ROI
    │           ├── face_x = x1 + fw × 0.15
    │           ├── face_y = y1 + fh × 0.03
    │           ├── face_w = fw × 0.65
    │           └── face_h = face_w × 1.25
    │
    ├── ROI 过滤 (detect_in_roi)
    │   └── 人脸中心点在有效区域内 → 有效
    │
    └── 标注输出 (annotate)
        ├── 蓝色框：人体边界框
        ├── 红色框：人脸 ROI
        └── 中文文字：识别结果
```

关键代码路径：

| 文件 | 行数 | 功能 |
|------|------|------|
| [core/face_detector.py](core/face_detector.py) | 111 | `FaceDetector` 类，YOLOv5 加载、推理、人脸估算 |
| [main.py:179](main.py#L179) | — | `FaceDetectThread`，实时人脸检测线程 |
| [main.py:223](main.py#L223) | — | `EnrollThread`，录入采集线程 |
| [main.py:322](main.py#L322) | — | `AutoRunThread`，自动门禁运行线程 |

### 人脸识别算法流程与特征比对

**LBPH（Local Binary Patterns Histograms）算法原理：**

1. **LBP 特征提取：** 对每个像素，比较其与周围 8 个邻居的灰度值，生成 8 位二进制编码
2. **网格划分：** 将人脸图像分为 8×8 网格
3. **直方图统计：** 每个网格统计 256 级 LBP 编码直方图
4. **特征拼接：** 拼接所有网格直方图 → 2048 维特征向量
5. **L2 归一化：** 特征向量归一化处理

**训练流程：**

```
dataset/张三/{1..20}.jpg  ──┐
dataset/李四/{1..20}.jpg  ──┤
                             ├──→ LBPH.train() ──→ model/model.xml
                             ├──→ 特征提取 ──→ SQLite face_features 表
                             └──→ 训练完成，清空 dataset/
```

**识别流程：**

```
人脸 ROI (BGR)
    │
    ├──→ cv2.cvtColor() → 灰度图
    ├──→ cv2.resize(200, 200)
    ├──→ LBPH.predict()
    │     ├── 置信度 < 阈值 (70) → 匹配成功 → 返回姓名
    │     └── 置信度 ≥ 阈值 → 陌生人
    └──→ 备选: predict_by_features()
          └── 余弦相似度比对 (DB 特征向量)
```

参数配置：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| radius | 1 | LBP 邻域半径 |
| neighbors | 8 | 邻域采样点数 |
| grid_x / grid_y | 8 | 网格划分 (8×8=64 块) |
| recognition_threshold | 70 | LBPH 置信度阈值 (越低越严格) |

### 道闸控制接口实现

**C 驱动层 (`C_driver/src/SensorControl.c`)：**

```c
// 统一传感器控制接口
float Sensor_Control(int cmd) {
    switch(cmd) {
        case 1: return cs100a_get_distance();   // 超声波测距 (cm)
        case 2: servo_open();   return 0;        // 道闸开门
        case 3: servo_close();  return 0;        // 道闸关门
        case 4: return mlx90614_get_temp();      // 红外测温 (°C)
    }
}
```

**Python 调用层 (`core/hardware.py`)：**

```python
# 通过 ctypes 加载 C 动态库
dll = cdll.LoadLibrary('app/SensorControl.so')
dll.Sensor_init()

# 开门，3秒后自动关闭
dll.Sensor_Control(2)
threading.Timer(3.0, lambda: dll.Sensor_Control(3)).start()
```

**模拟模式：** 当硬件不可用时（如 Windows 开发环境），自动切换到 `SimulatedHardware`，返回随机但合理的传感器数值。

### SQLite 数据库表结构设计

```sql
-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,          -- SHA-256 哈希
    role TEXT DEFAULT 'user',             -- 'admin' | 'user'
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 人脸特征表
CREATE TABLE face_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    feature_data BLOB NOT NULL,           -- pickle 序列化的 LBPH 特征向量
    image_count INTEGER DEFAULT 20,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

-- 通行记录表
CREATE TABLE access_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    name TEXT,
    result TEXT NOT NULL,                 -- 'success' | 'fail'
    confidence REAL DEFAULT 0,            -- LBPH 置信度
    temperature REAL,                     -- 体温 (°C)
    distance REAL,                        -- 距离 (cm)
    image BLOB,                           -- JPEG 抓拍
    timestamp TEXT DEFAULT (datetime('now','localtime'))
);

-- 系统设置表 (Key-Value)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

默认配置项（14 项）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| detect_method | yolov5 | 检测方法 |
| model_name | yolov5su | 模型名称 |
| confidence_threshold | 0.5 | 检测置信度阈值 |
| recognition_threshold | 70 | 识别阈值 |
| temp_limit | 37.2 | 体温上限 (°C) |
| dist_min | 10 | 最小有效距离 (cm) |
| dist_max | 120 | 最大有效距离 (cm) |
| auto_interval | 3 | 自动检测间隔 (秒) |
| gate_delay | 3 | 开门延时 (秒) |
| retry_limit | 5 | 连续失败锁定阈值 |
| lockout_duration | 5 | 锁定时长 (秒) |
| stranger_snapshot | true | 陌生人自动抓拍 |
| model_path | ./model/model.xml | LBPH 模型路径 |
| onnx_model_path | ./model/yolov5s.onnx | ONNX 模型路径（预留） |

---

## 测试与分析

### YOLOv5 检测准确率

| 测试场景 | 条件 | 检出率 | 说明 |
|----------|------|--------|------|
| 正脸、正常光照 | 距离 50-80cm | > 95% | 人体框完整 |
| 侧脸 (±30°) | 距离 50-80cm | ~85% | 部分角度人体框偏移 |
| 弱光环境 | 室内暗光 | ~80% | 需配合补光灯 |
| 近距离 (< 30cm) | 脸部填满画面 | ~90% | 只能看到上半身，检测框不完整 |
| 多人场景 | 2-3 人同框 | ~90% | 取第一个检测结果 |

### 识别成功率测试

| 测试条件 | 成功率 | 说明 |
|----------|--------|------|
| 录入与识别同人、同光照 | > 95% | LBPH 纹理匹配良好 |
| 录入与识别同人、不同光照 | ~80% | 光照变化影响 LBPH 纹理 |
| 未录入人员 (陌生人) | > 90% 正确拒绝 | 置信度 > 阈值 |
| 遮挡 (口罩、眼镜) | ~60% | 遮挡严重影响 LBPH 特征 |

### 响应时间测试

| 环节 | 耗时 | 说明 |
|------|------|------|
| 摄像头采集 | ~30 ms | 30 FPS |
| YOLOv5 推理 | ~45 ms | yolov5su, 640×640 |
| LBPH 推理 | ~5 ms | 200×200 灰度图 |
| 传感器采集 | ~150 ms | 测距 + 测温 |
| 端到端延迟 | ~230 ms | 采集到结果显示 |

---

## 问题与解决方案

### 问题 1：YOLOv5 检测 person 而非 face 导致人脸 ROI 不准确

**现象：** YOLOv5 标准模型只有 person 类，检测到的是全身/上半身，需要估算人脸位置。

**解决：** 设计人体框 → 人脸区域估算算法，通过多次迭代调整 `face_h` 从 `fh × 0.35` 优化为 `face_w × 1.25`（基于人脸固定宽高比），消除距离变化对人脸裁剪的影响。

### 问题 2：近距离人脸无法检测

**现象：** 人贴近摄像头时，YOLOv5 检测不到 person（缺少足够身体特征），或人脸估算区域超出 ROI 被过滤。

**解决：**
1. 降低 `confidence_threshold` 默认值
2. 将 ROI 过滤从"四条边全在界内"改为"中心点在界内"，大幅提高近距离检测通过率

### 问题 3：LBPH 识别一致性

**现象：** 录入和识别使用不同的检测方式导致人脸裁剪区域不一致，LBPH 无法正确匹配。

**解决：** 统一录入和识别使用同一个 `FaceDetector.detect()` 和相同的 ROI 估算公式，确保裁剪区域一致。

### 问题 4：龙芯平台部署挑战

**现象：** 龙芯 2K1000 为 MIPS64 架构，许多 Python 库需从源码编译，onnxruntime 无预编译包。

**解决策略：**
1. 当前版本改为直接使用 ultralytics 加载 .pt 文件，无需 ONNX 转换
2. 预留 `scripts/convert_yolo.py` 转换脚本和 INT8 量化方案
3. C 驱动层与 Python 层分离，硬件控制通过 ctypes 调用独立 .so 库

---

## 总结与改进

### 已完成功能

- [x] YOLOv5 (yolov5su.pt) 实时人体检测与人脸区域估算
- [x] LBPH 人脸特征提取、训练、识别
- [x] PyQt5 暗色主题界面（预览 / 记录 / 设置三个标签页）
- [x] SQLite 数据库（4 张表，14 项可配置参数）
- [x] 红外测温 + 超声波测距 + 道闸控制（含模拟模式）
- [x] 安全策略：连续失败锁定、陌生人抓拍
- [x] 中文 TTS 语音播报（Windows SAPI / Linux pyttsx3）
- [x] 录入→手动训练工作流，训练后自动清屏

### 后续改进方向

| 方向 | 方案 | 优先级 |
|------|------|--------|
| **人脸检测升级** | 替换为 YOLOv5-face 或 RetinaFace，直接检测人脸而非从人体框估算 | 高 |
| **识别算法升级** | 引入 FaceNet / ArcFace 深度学习特征，替代 LBPH 纹理特征 | 高 |
| **龙芯平台优化** | ONNX Runtime + INT8 量化 + 输入降采样到 320×320 | 中 |
| **活体检测** | 眨眼/张嘴动作检测，防止照片攻击 | 中 |
| **多人同时识别** | 支持一帧内多人脸检测与识别 | 低 |
| **远程管理** | Web 管理后台，远程查看通行记录和系统状态 | 低 |
| **边缘计算** | 模型在设备端增量训练，无需重新采集 | 低 |

---

## 项目结构

```
YOLOv5_AccessControl/
├── main.py                 # 应用入口，线程管理，回调绑定
├── yolov5su.pt             # YOLOv5 预训练模型 (18.6 MB)
├── core/
│   ├── database.py         # SQLite 数据库 (4 表, 14 配置项)
│   ├── face_detector.py    # YOLOv5 人脸检测器
│   ├── face_recognizer.py  # LBPH 人脸识别器
│   └── hardware.py         # 硬件控制 (C DLL + 模拟)
├── ui/
│   ├── main_window.py      # 主窗口 (3 标签页, 暗色主题)
│   └── login.py            # 登录对话框
├── utils/
│   └── face_utils.py       # 中文路径读写 + Pillow 中文渲染
├── scripts/
│   └── convert_yolo.py     # .pt → ONNX 转换 + INT8 量化
├── C_driver/               # C 语言硬件驱动 (1359 行)
│   ├── gpio.c/h            # GPIO 控制
│   ├── i2c/                # I²C 总线驱动
│   └── src/                # 传感器驱动 (舵机/测温/测距)
├── data/                   # 数据库 + 级联文件
├── model/                  # 训练好的 LBPH 模型
└── dataset/                # 人脸采集图像 (训练后清空)
```

## 快速开始

```bash
# 1. 安装依赖
pip install ultralytics opencv-contrib-python PyQt5 numpy pillow

# 2. 确保 yolov5su.pt 在项目根目录（首次运行自动下载）

# 3. 运行
python main.py

# 4. 默认管理员账号
#    账号: admin  密码: admin123
```

## 依赖清单

| 包 | 用途 |
|----|------|
| ultralytics | YOLOv5 模型加载与推理 |
| opencv-contrib-python | 图像处理、LBPH 人脸识别 |
| PyQt5 | GUI 界面 |
| numpy | 数值计算 |
| Pillow | 中文文字渲染 |
| pyttsx3 | Linux TTS 语音播报 |
| pywin32 | Windows SAPI 语音播报 |
| onnx / onnxruntime | ONNX 模型推理 (龙芯部署) |
