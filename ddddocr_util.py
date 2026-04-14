import ddddocr
import cv2
import numpy as np

ocr = ddddocr.DdddOcr(show_ad=False, beta=True)

def ocr_region(img, region_box):
    """
    img: 原图 (numpy array, BGR格式)
    region_box: (x1, y1, x2, y2) 识别区域坐标
    """
    x1, y1, x2, y2 = region_box
    roi = img[y1:y2, x1:x2]
    
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    
    resized = cv2.resize(thresh, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    
    _, img_bytes = cv2.imencode('.png', resized)
    result = ocr.classification(img_bytes.tobytes())
    
    return result