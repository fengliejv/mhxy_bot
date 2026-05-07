import ddddocr
import cv2
import sys_util

# 初始化 ddddocr 实例，关闭广告并启用 beta 功能
ocr = ddddocr.DdddOcr(show_ad=False, beta=True)

def ocr_region(img, region_box):
    """
    对指定区域进行 OCR 数字文字识别。

    参数:
        img (numpy.ndarray): 原图，BGR 格式。
        region_box (tuple): 识别区域坐标，格式为 (x1, y1, x2, y2)。

    返回:
        str: OCR 识别结果字符串。
    """
    # 提取感兴趣区域（ROI）
    x1, y1, x2, y2 = region_box
    roi = img[y1:y2, x1:x2]
    # 保存提取的 ROI 图像，方便调试
    sys_util.save_debug_image(roi, f"detected{x1}_{y1}_{x2}_{y2}.png")
    # 转为灰度图
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 二值化并反色，突出文字
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

    # 放大图像，提高识别准确率
    resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)

    # 将图像编码为 PNG 字节流
    _, img_bytes = cv2.imencode('.png', resized)

    # 调用 ddddocr 进行文字识别
    result = ocr.classification(img_bytes.tobytes())
    print(result)
    return result


def ocr_image(img):
    if img is None:
        raise ValueError("img 不能为空")

    sys_util.save_debug_image(img, "ocr_image")

    if len(img.shape) == 2:
        gray = img
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    _, img_bytes = cv2.imencode(".png", resized)
    result = ocr.classification(img_bytes.tobytes())
    print(result)
    return result


