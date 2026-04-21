import os
import datetime
import io
from PIL import Image

def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


    # 根据环境变量 is_debug 决定是否保存调试截图
    def save_debug_image(img: Image.Image,name: str) -> None:
        is_debug = os.getenv("is_debug", "").strip().lower() in ("1", "true", "yes")
        if is_debug:
            debug_dir = os.path.join(os.getcwd(), "debug_capture")
            os.makedirs(debug_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_path = os.path.join(debug_dir, f"{ts}_{name}.png")
            if isinstance(img, (bytes, bytearray, memoryview)):
                with open(debug_path, "wb") as f:
                    f.write(bytes(img))
            else:
                img.save(debug_path)
            print(f"[DEBUG] 捕获文件已保存: {debug_path}")
