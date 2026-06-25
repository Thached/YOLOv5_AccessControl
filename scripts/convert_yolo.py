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
- onnxruntime (CPU) — 推荐，原生支持 MIPS64
- 若 onnxruntime 不可用 → 使用 PyTorch 直接推理
- 最后回退 → OpenCV DNN 模块 + Haar级联

============================================
使用方法:
  python scripts/convert_yolo.py --model yolov5s
  python scripts/convert_yolo.py --model yolov5n --quantize
  python scripts/convert_yolo.py --model yolov5s --img-size 320
============================================
"""

import os
import sys
import argparse
import time
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description='YOLOv5模型转换：pt → ONNX → 龙芯平台')
    parser.add_argument('--model', type=str, default='yolov5s',
                        choices=['yolov5n', 'yolov5s', 'yolov5m', 'yolov5l'],
                        help='YOLOv5模型版本（推荐yolov5s或yolov5n）')
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

    命令等效:
      python export.py --weights yolov5s.pt --include onnx --opset 12 --img 640
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

    try:
        # 方法1: 使用 YOLOv5 官方 export.py
        print(f"加载 YOLOv5 模型: {args.model}")
        model = torch.hub.load('ultralytics/yolov5', args.model,
                               pretrained=True, verbose=False)
        model.eval()

        # 创建虚拟输入
        dummy_input = torch.randn(
            args.batch_size, 3, args.img_size, args.img_size)

        print(f"导出 ONNX (opset={args.opset}, img_size={args.img_size})...")
        torch.onnx.export(
            model,
            dummy_input,
            onnx_path,
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

        # 打印模型大小
        size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        print(f"  模型大小: {size_mb:.1f} MB")

    except Exception as e:
        print(f"[错误] 导出失败: {e}")
        print("请尝试手动运行:")
        print("  git clone https://github.com/ultralytics/yolov5")
        print(f"  cd yolov5 && python export.py --weights {args.model}.pt "
              "--include onnx --opset 12")
        return None

    return onnx_path


def quantize_int8(onnx_path, args):
    """
    第二步：INT8 量化（可选）

    量化方案：
    - 动态量化 (Dynamic Quantization): 权重 INT8，激活保持 FP32
    - 静态量化 (Static Quantization): 需要校准数据集
    - 本脚本使用动态量化，简单且效果显著

    量化命令 (使用 onnxruntime):
      python -m onnxruntime.quantization.preprocess --input model/yolov5s.onnx
      --output model/yolov5s_int8.onnx
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


def verify_onnx(onnx_path):
    """第三步：验证 ONNX 模型"""
    print("=" * 60)
    print("步骤3: 验证 ONNX 模型")
    print("=" * 60)

    try:
        import onnx
        import onnxruntime as ort

        # 检查模型结构
        model = onnx.load(onnx_path)
        onnx.checker.check_model(model)
        print("[OK] ONNX 模型结构验证通过")

        # 检查推理
        session = ort.InferenceSession(
            onnx_path, providers=['CPUExecutionProvider'])
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        print(f"  输入: {input_name} {input_shape}")

        # 运行一次推理测试性能
        dummy = np.random.randn(1, 3, 640, 640).astype(np.float32)
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

    print(f"""
┌─────────────────────────────────────────────────────────────┐
│                  龙芯2K1000 部署步骤                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 安装依赖 (在龙芯平台上):                                  │
│     $ sudo apt-get install python3-pip                       │
│     $ pip3 install numpy opencv-python-headless              │
│     $ pip3 install onnxruntime  # 或从源码编译               │
│                                                             │
│  2. 复制模型文件:                                            │
│     $ scp {model_file} \\
│          user@loongson:~/YOLOv5_AccessControl/model/          │
│                                                             │
│  3. 更新数据库配置(或直接在GUI系统设置中修改):                 │
│     UPDATE settings SET value='{model_file}'                │
│     WHERE key='onnx_model_path';                            │
│                                                             │
│  4. 运行程序:                                                │
│     $ cd ~/YOLOv5_AccessControl                             │
│     $ python3 main.py                                       │
│                                                             │
│  5. 验证后端: 状态栏应显示 "检测: ONNX"                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  性能优化建议:                                               │
│  - 使用 yolov5n (最小模型)                                   │
│  - 设置 --img-size 320 (降低分辨率)                          │
│  - 开启 INT8 量化 (--quantize)                              │
│  - 使用 onnxruntime 的 CPU 优化选项                          │
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
    print(f"  回退方案: PyTorch → OpenCV DNN → Haar级联")


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

    # 步骤3: 验证
    verify_onnx(quant_path)

    # 步骤4: 打印部署指南
    print_deploy_guide(args, onnx_path, quant_path)


if __name__ == '__main__':
    main()
