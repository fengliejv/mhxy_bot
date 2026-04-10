"""
梦幻西游打图自动化 - 图像识别模块
"""
import cv2
import numpy as np
from typing import Optional, Tuple, List
from .logger import setup_logger

logger = setup_logger("image_recognition")


class ImageRecognition:
    def __init__(self):
        self.templates = {}

    def load_template(self, name: str, path: str) -> None:
        template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            logger.error(f"无法加载模板图片: {path}")
            return
        self.templates[name] = template
        logger.info(f"已加载模板: {name}")

    def match_template(
        self,
        screenshot: np.ndarray,
        template_name: str,
        threshold: float = 0.8,
    ) -> Optional[Tuple[int, int, float]]:
        if template_name not in self.templates:
            logger.error(f"模板不存在: {template_name}")
            return None

        template = self.templates[template_name]
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            logger.info(f"匹配成功: {template_name} at ({center_x}, {center_y}), 置信度: {max_val:.2f}")
            return (center_x, center_y, max_val)

        logger.debug(f"匹配失败: {template_name}, 最高置信度: {max_val:.2f}")
        return None

    def match_all_templates(
        self,
        screenshot: np.ndarray,
        threshold: float = 0.8,
    ) -> List[Tuple[str, int, int, float]]:
        results = []
        for name in self.templates:
            result = self.match_template(screenshot, name, threshold)
            if result:
                results.append((name, result[0], result[1], result[2]))
        return results

    def find_color_region(
        self,
        screenshot: np.ndarray,
        lower_color: Tuple[int, int, int],
        upper_color: Tuple[int, int, int],
    ) -> Optional[Tuple[int, int, int, int]]:
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_color), np.array(upper_color))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            return (x, y, w, h)
        return None

    def detect_text_region(
        self,
        screenshot: np.ndarray,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[str]:
        try:
            import pytesseract
        except ImportError:
            logger.error("未安装 pytesseract，无法进行文字识别")
            return None

        if roi:
            x, y, w, h = roi
            region = screenshot[y : y + h, x : x + w]
        else:
            region = screenshot

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(thresh, lang="chi_sim+eng").strip()
        return text if text else None
