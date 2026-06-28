"""
YOLOv5 模型转换脚本
====================
转换流程：.pt → ONNX → 龙芯平台可加载格式

步骤概述：
1. 导出 PyTorch 模型为 ONNX 格式
2. (可选) INT8 量化以加速推理
3. 验证 ONNX 模型正确性
4. 将 ONNX 模型部署到龙芯2K1000平台

龙芯平台推理方案：
- onnxruntime (CPU) — 推荐，编译 onnxruntime 适配 MIPS64
- 若 onnxruntime 不可用 → OpenCV DNN 模块加载 ONNX
- 开发环境 → 直接使用 ultralytics 加载 .pt

============================================
使用方法:
  python scripts/convert_yolo.py --model yolov5su
  python scripts/convert_yolo.py --model yolov5su --quantize
  python scripts/convert_yolo.py --model yolov5su --img-size 320
============================================
"""

import os
import sys
import argparse
import time
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description='YOLOv5模型转换：pt → ONNX → 龙芯平台')
    parser.add_argument('--model', type=str, default='yolov5su',
                        choices=['yolov5n', 'yolov5s', 'yolov5m', 'yolov5l', 'yolov5nu', 'yolov5su'],
                        help='YOLOv5模型版本（推荐yolov5su）')
    parser.add_argument('--img-size', type=int, default=640,
                        help='输入图像尺寸 (默认640)')
    parser.add_argument('--batch-size', type=int, default=1,
                        help='批处理大小 (默认1)')
    parser.add_argument('--quantize', action='store_true',
                        help='是否执行 INT8 量化')
    parser.add_argument('--opset', type=int, default=12,
                        help='ONNX算子集版本 (默认12)')
    parser.add_argument('--output-dir', type=str, default='model',
                        help='输出目录 (默认 model/)')
    parser.add_argument('--verify', action='store_true', default=True,
                        help='导出后验证ONNX模型 (默认开启)')
    return parser.parse_args()


def export_to_onnx(args):
    """
    第一步：PyTorch模型 → ONNX格式

    使用 ultralytics 官方导出 API:
      from ultralytics import YOLO
      model = YOLO('yolov5su.pt')
      model.export(format='onnx', imgsz=640, opset=12)
    """
    print("=" * 60)
    print("步骤1: 导出 PyTorch → ONNX")
    print("=" * 60)

    try:
        import torch
    except ImportError:
        print("[错误] 请先安装 PyTorch: pip install torch")
        return None

    os.makedirs(args.output_dir, exist_ok=True)
    onnx_path = os.path.join(args.output_dir, f'{args.model}.onnx')
    cwd_onnx = f'{args.model}.onnx'  # ultralytics 导出到当前目录

    try:
        # 方式1: 使用 ultralytics YOLO（项目当前使用的接口）
        print(f"加载 YOLOv5 模型: {args.model}.pt")
        from ultralytics import YOLO
        model = YOLO(f'{args.model}.pt')
        print(f"导出 ONNX (opset={args.opset}, img_size={args.img_size})...")
        model.export(format='onnx', imgsz=args.img_size, opset=args.opset)
        # ultralytics 导出到当前目录，移动到 model/
        if os.path.exists(cwd_onnx) and not os.path.exists(onnx_path):
            import shutil
            shutil.move(cwd_onnx, onnx_path)
        print(f"[完成] ONNX 模型已保存: {onnx_path}")

    except Exception as e1:
        print(f"[ultralytics] 导出失败: {e1}")
        print("  尝试旧版 torch.hub 方式...")
        try:
            model = torch.hub.load('ultralytics/yolov5', args.model,
                                   pretrained=True, verbose=False)
            model.eval()
            dummy_input = torch.randn(
                args.batch_size, 3, args.img_size, args.img_size)
            torch.onnx.export(
                model, dummy_input, onnx_path,
                opset_version=args.opset,
                input_names=['images'],
                output_names=['output'],
                dynamic_axes={
                    'images': {0: 'batch'},
                    'output': {0: 'batch'}
                } if args.batch_size > 1 else None,
                verbose=False
            )
            print(f"[完成] ONNX 模型已保存: {onnx_path}")
        except Exception as e2:
            print(f"[错误] 两种方式均导出失败")
            print(f"  ultralytics: {e1}")
            print(f"  torch.hub: {e2}")
            return None

    size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
    print(f"  模型大小: {size_mb:.1f} MB")
    return onnx_path


def quantize_int8(onnx_path, args):
    """
    第二步：INT8 量化（可选）

    量化方案：
    - 动态量化 (Dynamic Quantization): 权重 INT8，激活保持 FP32
    - 使用 onnxruntime.quantization.quantize_dynamic
    - 模型体积缩小约75%, 推理速度提升2-4倍
    """
    print("=" * 60)
    print("步骤2: INT8 量化")
    print("=" * 60)

    quant_path = onnx_path.replace('.onnx', '_int8.onnx')

    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType

        print("执行动态量化...")
        print("  量化方案: 动态量化 (Dynamic Quantization)")
        print("  权重: INT8, 激活: FP32/UINT8")
        print("  优点: 模型体积缩小约75%, 推理速度提升2-4倍")
        print("  缺点: 精度略有下降(通常<1%)")

        quantize_dynamic(
            model_input=onnx_path,
            model_output=quant_path,
            weight_type=QuantType.QInt8
        )

        size_before = os.path.getsize(onnx_path) / (1024 * 1024)
        size_after = os.path.getsize(quant_path) / (1024 * 1024)
        compression = (1 - size_after / size_before) * 100

        print(f"[完成] INT8量化模型已保存: {quant_path}")
        print(f"  量化前: {size_before:.1f} MB")
        print(f"  量化后: {size_after:.1f} MB")
        print(f"  压缩率: {compression:.1f}%")

        return quant_path

    except ImportError:
        print("[跳过] onnxruntime 未安装，跳过量化")
        print("  安装: pip install onnxruntime")
        return onnx_path
    except Exception as e:
        print(f"[错误] 量化失败: {e}")
        return onnx_path


def verify_onnx(onnx_path, fallback_size=640):
    """第三步：验证 ONNX 模型"""
    print("=" * 60)
    print("步骤3: 验证 ONNX 模型")
    print("=" * 60)

    try:
        import onnx
        import onnxruntime as ort

        model = onnx.load(onnx_path)
        onnx.checker.check_model(model)
        print("[OK] ONNX 模型结构验证通过")

        session = ort.InferenceSession(
            onnx_path, providers=['CPUExecutionProvider'])
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        print(f"  输入: {input_name} {input_shape}")

        # 从模型实际输入尺寸生成测试数据（支持动态维度）
        h = input_shape[2] if isinstance(input_shape[2], int) else fallback_size
        w = input_shape[3] if isinstance(input_shape[3], int) else fallback_size
        dummy = np.random.randn(1, 3, h, w).astype(np.float32)
        times = []
        for _ in range(10):
            t0 = time.time()
            _ = session.run(None, {input_name: dummy})
            times.append(time.time() - t0)

        avg_time = sum(times[2:]) / len(times[2:])  # 排除预热
        fps = 1.0 / avg_time
        print(f"  平均推理时间: {avg_time * 1000:.1f}ms")
        print(f"  预估 FPS: {fps:.1f}")

        if fps < 5:
            print(f"  [警告] FPS < 5，请考虑:")
            print(f"    1. 使用更小的模型 (yolov5n)")
            print(f"    2. 减小输入尺寸 (--img-size 320)")
            print(f"    3. 执行 INT8 量化 (--quantize)")
        else:
            print(f"  [OK] FPS >= 5, 满足要求")

        return True

    except ImportError as e:
        print(f"[跳过] 缺少依赖: {e}")
        print("  安装: pip install onnx onnxruntime")
        return False
    except Exception as e:
        print(f"[错误] 验证失败: {e}")
        return False


def print_deploy_guide(args, onnx_path, quant_path):
    """打印龙芯2K1000部署指南"""
    print("=" * 60)
    print("步骤4: 龙芯2K1000 (MIPS64el) 部署指南")
    print("=" * 60)

    model_file = quant_path if args.quantize else onnx_path
    model_name = os.path.basename(model_file)

    print(f"""
┌─────────────────────────────────────────────────────────────┐
│                  龙芯2K1000 部署步骤                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. PC端：导出并传输模型                                      │
│     $ python scripts/convert_yolo.py --model {args.model}     │
│     $ scp {model_file} \\                                   │
│          user@loongson:~/YOLOv5_AccessControl/model/         │
│                                                             │
│  2. 龙芯平台安装依赖:                                         │
│     $ sudo apt-get install python3-pip python3-pyqt5        │
│     $ pip3 install numpy opencv-contrib-python-headless     │
│     $ pip3 install pillow                                   │
│                                                             │
│  3. 编译 onnxruntime (MIPS64):                               │
│     $ git clone https://github.com/microsoft/onnxruntime    │
│     $ cd onnxruntime                                        │
│     $ ./build.sh --config Release --build_shared_lib        │
│          --parallel --compile_no_warning_as_error           │
│          --skip_tests                                       │
│     交叉编译后复制 .whl 到龙芯平台安装                        │
│                                                             │
│  4. 编译硬件驱动:                                             │
│     $ cd C_driver && make                                   │
│     $ cp app/SensorControl.so ~/YOLOv5_AccessControl/app/    │
│                                                             │
│  5. 运行程序:                                                │
│     $ cd ~/YOLOv5_AccessControl                             │
│     $ python3 main.py                                       │
│     (检测器自动选择 ONNX 后端)                                │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  性能优化建议:                                               │
│  - 使用 --img-size 320 (推理快4倍)                            │
│  - 开启 INT8 量化 (--quantize, 模型缩小75%)                  │
│  - 自动检测间隔调整为 4-5 秒                                  │
│  - 使用 onnxruntime CPU 优化选项                             │
│                                                             │
│  如果是Windows/Linux开发机:                                   │
│  - FaceDetector 自动检测到 PyTorch → 使用 ultralytics 后端    │
│  - 无需转换, 直接运行 python main.py                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
""")

    print("总结:")
    print(f"  原始模型: {args.model}.pt")
    print(f"  ONNX模型: {onnx_path}")
    if args.quantize:
        print(f"  量化模型: {quant_path}")
    print(f"  目标平台: 龙芯 2K1000 (MIPS64 little-endian)")
    print(f"  推理后端: onnxruntime (CPU)")
    print(f"  检测器会自动选择: ultralytics → ONNX")


def main():
    args = parse_args()

    print("YOLOv5 模型转换工具")
    print(f"目标平台: 龙芯 2K1000 (MIPS64 little-endian)")
    print(f"模型: {args.model} | 输入尺寸: {args.img_size} | "
          f"量化: {'是' if args.quantize else '否'}")
    print()

    # 步骤1: 导出 ONNX
    onnx_path = export_to_onnx(args)
    if onnx_path is None:
        sys.exit(1)

    quant_path = onnx_path

    # 步骤2: INT8 量化
    if args.quantize:
        quant_path = quantize_int8(onnx_path, args)

    # 步骤3: 验证原始 ONNX 模型
    print()
    ok = verify_onnx(onnx_path, fallback_size=args.img_size)
    if not ok:
        print("[警告] 原始 ONNX 模型验证失败，请检查环境")
        sys.exit(1)

    # 步骤3b: 验证量化模型（如有）
    if args.quantize and quant_path != onnx_path:
        print()
        print("验证 INT8 量化模型...")
        ok_q = verify_onnx(quant_path, fallback_size=args.img_size)
        if not ok_q:
            print("[注意] INT8 量化模型验证失败（ConvInteger 算子需要 ONNX Runtime ≥ 1.15 或特殊编译）")
            print("  方案1: 在龙芯上编译 onnxruntime 时启用 --enable_contrib_ops")
            print("  方案2: 使用原始 ONNX 模型（未量化），仍可正常工作")
            print(f"  原始模型: {onnx_path}")

    # 步骤4: 打印部署指南
    print_deploy_guide(args, onnx_path, quant_path)


if __name__ == '__main__':
    main()
