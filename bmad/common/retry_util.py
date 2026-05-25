import time
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar


T = TypeVar("T")


def retry(
    fn: Callable[[int], T],
    *,
    times: int,
    sleep_s: float,
    name: str = "retry",
    collect: bool = True,
) -> Tuple[Optional[T], Dict[str, Any]]:
    attempts = []
    last_exc = None
    max_times = max(1, int(times))
    for i in range(1, max_times + 1):
        try:
            out = fn(i)
            return out, {"ok": True, "attempt": i, "attempts": attempts}
        except Exception as e:
            last_exc = e
            if collect:
                attempts.append({"attempt": i, "error": repr(e)})
            if i < max_times:
                time.sleep(max(0.0, float(sleep_s)))
    return None, {"ok": False, "name": name, "attempts": attempts, "error": repr(last_exc)}

