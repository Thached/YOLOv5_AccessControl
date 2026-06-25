"""
工具函数模块
- 中文路径 imread/imwrite
- 中文文字渲染 (PIL)
- 跨平台中文字体查找
"""
import os
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont


# ========== 中文路径支持 ==========

def imread_unicode(filepath, flags=cv2.IMREAD_GRAYSCALE):
    """支持中文路径的 imread"""
    with open(filepath, 'rb') as f:
        data = f.read()
    img_array = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(img_array, flags)


def imwrite_unicode(filepath, img):
    """支持中文路径的 imwrite"""
    ext = os.path.splitext(filepath)[1]
    ret, buf = cv2.imencode(ext, img)
    if ret:
        with open(filepath, 'wb') as f:
            f.write(buf.tobytes())
    return ret


# ========== 中文字体查找与渲染 ==========

def _find_chinese_font():
    """跨平台查找系统中支持中文的字体"""
    search_dirs = []
    if sys.platform == 'win32':
        windir = os.environ.get('WINDIR', r'C:\Windows')
        search_dirs = [os.path.join(windir, 'Fonts')]
    else:
        search_dirs = [
            '/usr/share/fonts',
            '/usr/local/share/fonts',
            os.path.expanduser('~/.fonts'),
        ]

    for font_dir in search_dirs:
        if not os.path.isdir(font_dir):
            continue
        for root, _dirs, files in os.walk(font_dir):
            for f in files:
                if not f.lower().endswith(('.ttf', '.ttc', '.otf')):
                    continue
                fp = os.path.join(root, f)
                try:
                    font = ImageFont.truetype(fp, 24)
                    if font.getbbox('中')[2] > font.getbbox('A')[2] * 1.5:
                        return fp
                except Exception:
                    continue
    return None


_CHINESE_FONT_PATH = _find_chinese_font()


def put_chinese_text(img, text, position, font_size=30, color=(0, 0, 255)):
    """在OpenCV图片上用Pillow绘制中文文字"""
    if _CHINESE_FONT_PATH is None:
        return cv2.putText(img, text, position, cv2.FONT_HERSHEY_SIMPLEX,
                           1, color, 2)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    font = ImageFont.truetype(_CHINESE_FONT_PATH, font_size)
    draw.text(position, text, font=font, fill=(color[2], color[1], color[0]))
    img[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return img
