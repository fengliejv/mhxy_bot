import os
import datetime
import io
import atexit
import queue
import threading
import time
try:
    from PIL import Image as _PIL_Image
except Exception:
    _PIL_Image = None
import botconfig

_debug_queue: "queue.Queue[tuple]" = queue.Queue(maxsize=256)
_debug_worker_started = False
_debug_worker_lock = threading.Lock()


def _ensure_debug_worker() -> None:
    global _debug_worker_started
    if _debug_worker_started:
        return
    with _debug_worker_lock:
        if _debug_worker_started:
            return

        t = threading.Thread(target=_debug_worker_loop, name="debug-image-writer", daemon=True)
        t.start()
        _debug_worker_started = True

        def _drain() -> None:
            deadline = time.time() + 2.0
            while time.time() < deadline:
                try:
                    img, debug_path = _debug_queue.get_nowait()
                except Exception:
                    break
                try:
                    _write_debug_image(img, debug_path)
                except Exception:
                    pass
                finally:
                    try:
                        _debug_queue.task_done()
                    except Exception:
                        pass

        atexit.register(_drain)


def _write_debug_image(img, debug_path: str) -> None:
    if isinstance(img, (bytes, bytearray, memoryview)):
        with open(debug_path, "wb") as f:
            f.write(bytes(img))
        print(f"[DEBUG] 捕获文件已保存: {debug_path}")
        return
    if hasattr(img, "save"):
        img.save(debug_path)
        print(f"[DEBUG] 捕获文件已保存: {debug_path}")
        return
    if _PIL_Image is None:
        return
    try:
        shape = getattr(img, "shape", None)
        if shape is not None and len(shape) == 3 and shape[2] == 3:
            pil_img = _PIL_Image.fromarray(img[:, :, ::-1])
        elif shape is not None and len(shape) == 3 and shape[2] == 4:
            pil_img = _PIL_Image.fromarray(img[:, :, [2, 1, 0, 3]])
        else:
            pil_img = _PIL_Image.fromarray(img)
        pil_img.save(debug_path)
        print(f"[DEBUG] 捕获文件已保存: {debug_path}")
    except Exception:
        return


def _debug_worker_loop() -> None:
    while True:
        try:
            img, debug_path = _debug_queue.get()
        except Exception:
            time.sleep(0.05)
            continue
        try:
            _write_debug_image(img, debug_path)
        except Exception:
            pass
        finally:
            try:
                _debug_queue.task_done()
            except Exception:
                pass


def load_dotenv(path: str = ".env") -> None:
    botconfig.init(path)


def save_debug_image(img, name: str) -> None:
        is_debug = bool(botconfig.is_debug())
        if not is_debug:
            return
        debug_dir = os.path.join(os.getcwd(), "debug_capture")
        os.makedirs(debug_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_path = os.path.join(debug_dir, f"{ts}_{name}.png")
        try:
            _ensure_debug_worker()
            _debug_queue.put_nowait((img, debug_path))
        except Exception:
            return
import shutil
def clear_debug_capture() -> None:
    debug_dir = os.path.join(os.getcwd(), "debug_capture")
    if os.path.isdir(debug_dir):
        for f in os.listdir(debug_dir):
            fp = os.path.join(debug_dir, f)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
        try:
            shutil.rmtree(debug_dir)
        except Exception:
            pass
