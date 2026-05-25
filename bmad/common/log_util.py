from typing import Any, Mapping, Optional


def log_step(module: str, name: str, detail: str, *, extra: Optional[Mapping[str, Any]] = None) -> None:
    prefix = f"[{module}] {name}: {detail}"
    if not extra:
        print(prefix)
        return
    extras = " ".join(f"{k}={v!r}" for k, v in extra.items())
    print(f"{prefix} {extras}")

