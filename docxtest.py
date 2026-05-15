import zipfile
import os
import shutil
import subprocess
import datetime
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import botconfig

def has_attachments(docx_path):
    try:
        # docx 本质是 zip 文件，直接用 zipfile 打开
        with zipfile.ZipFile(docx_path, 'r') as z:
            # 获取压缩包内所有文件的路径列表
            file_list = z.namelist()
            
            # 检查是否有属于内嵌附件的目录
            embed_dirs = ("word/embeddings/", "word/objects/", "word/activex/")
            
            attachments = []  # 用于收集所有附件路径
            for file_name in file_list:
                # 统一转小写进行匹配
                low_name = file_name.lower()
                if any(low_name.startswith(d) for d in embed_dirs):
                    attachments.append(file_name)
            
            if attachments:
                print("发现以下附件（可在原压缩包中按路径查找）：")
                for att in attachments:
                    print(f"  - {att}")
                return True
            return False
    except zipfile.BadZipFile:
        print("不是有效的 docx/zip 文件")
        return False

def crop_pdf_pages(pdf_path: str, start_page: int, end_page: int, output_path: Optional[str] = None) -> str:
    src = Path(pdf_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(str(src))

    start = int(start_page)
    end = int(end_page)
    if start < 1:
        raise ValueError("start_page 必须 >= 1（按 1 开始计数）")
    if end < start:
        raise ValueError("end_page 必须 >= start_page")

    PdfReader = None
    PdfWriter = None
    try:
        from pypdf import PdfReader as _PdfReader, PdfWriter as _PdfWriter  # type: ignore

        PdfReader = _PdfReader
        PdfWriter = _PdfWriter
    except Exception:
        try:
            from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter  # type: ignore

            PdfReader = _PdfReader
            PdfWriter = _PdfWriter
        except Exception as e:
            raise RuntimeError("缺少 PDF 处理依赖：请安装 pypdf（推荐）或 PyPDF2") from e

    reader = PdfReader(str(src))
    total = len(reader.pages)
    if end > total:
        raise ValueError(f"end_page 超出范围：文档共 {total} 页，但 end_page={end}")

    out = Path(output_path).expanduser().resolve() if output_path else src.with_name(f"{src.stem}_p{start}-{end}{src.suffix}")
    out.parent.mkdir(parents=True, exist_ok=True)

    writer = PdfWriter()
    for i in range(start - 1, end):
        writer.add_page(reader.pages[i])
    with open(out, "wb") as f:
        writer.write(f)
    return str(out)

def mineru_parse_keep_artifacts(
    file_path: str,
    output_dir: Optional[str] = None,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    page_base: int = 1,
    mineru_cmd: Optional[str] = None,
    extra_args: Optional[Sequence[str]] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_s: Optional[float] = None,
    live_output: bool = True,
) -> Dict[str, Any]:
    src = Path(file_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(str(src))

    cmd = (mineru_cmd or botconfig.env_str("MINERU_CMD", botconfig.MINERU_CMD) or "mineru").strip()
    if not cmd:
        cmd = "mineru"
    if shutil.which(cmd) is None:
        raise RuntimeError(f"找不到可执行文件: {cmd}（请先安装 MinerU 3.0，并确保命令在 PATH 中）")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir).expanduser().resolve() if output_dir else src.parent / f"mineru_out_{src.stem}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    argv: List[str] = [cmd, "-p", str(src), "-o", str(out_dir)]
    if start_page is not None:
        s = int(start_page)
        s0 = s - page_base
        if s0 < 0:
            raise ValueError("start_page 超出范围")
        argv += ["-s", str(s0)]
    if end_page is not None:
        e = int(end_page)
        e0 = e - page_base
        if e0 < 0:
            raise ValueError("end_page 超出范围")
        argv += ["-e", str(e0)]
    if extra_args:
        argv += [str(x) for x in extra_args if str(x).strip()]

    run_env = botconfig.environ_copy()
    if env:
        for k, v in env.items():
            kk = str(k).strip()
            if not kk:
                continue
            run_env[kk] = str(v)

    cmd_path = out_dir / "mineru_cmd.txt"
    cmd_path.write_text(" ".join(argv), encoding="utf-8")

    stdout_path = out_dir / "mineru_stdout.txt"
    stderr_path = out_dir / "mineru_stderr.txt"

    if not live_output:
        cp = subprocess.run(
            argv,
            cwd=str(out_dir),
            env=run_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        stdout_path.write_text(cp.stdout or "", encoding="utf-8")
        stderr_path.write_text(cp.stderr or "", encoding="utf-8")
        rc = int(cp.returncode)
    else:
        with open(stdout_path, "w", encoding="utf-8") as f_out, open(stderr_path, "w", encoding="utf-8") as f_err:
            proc = subprocess.Popen(
                argv,
                cwd=str(out_dir),
                env=run_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            def _tee(src, dst, prefix: str) -> None:
                try:
                    for line in iter(src.readline, ""):
                        dst.write(line)
                        dst.flush()
                        print(f"{prefix}{line}", end="")
                finally:
                    try:
                        src.close()
                    except Exception:
                        pass

            t1 = threading.Thread(target=_tee, args=(proc.stdout, f_out, "[mineru] "), daemon=True)
            t2 = threading.Thread(target=_tee, args=(proc.stderr, f_err, "[mineru][err] "), daemon=True)
            t1.start()
            t2.start()
            try:
                proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                raise
            t1.join(timeout=2.0)
            t2.join(timeout=2.0)
            rc = int(proc.returncode or 0)

    if rc != 0:
        raise RuntimeError(f"mineru 执行失败: rc={rc}，输出目录：{out_dir}")

    return {
        "ok": True,
        "output_dir": str(out_dir),
        "cmd": argv,
        "cmd_file": str(cmd_path),
        "stdout_file": str(stdout_path),
        "stderr_file": str(stderr_path),
        "returncode": rc,
    }

import tempfile, glob, os
def getMineruOutputDir():
    td = tempfile.gettempdir()
    print("tempdir =", td)
    for pat in ("mineru_pdf_*", "mineru_bin_pdf_*"):
        xs = sorted(glob.glob(os.path.join(td, pat)), key=os.path.getmtime, reverse=True)
        print(pat, "count=", len(xs))
        print("\n".join(xs[:20]))


if __name__ == "__main__":
    # crop_pdf_pages("3.第三册桥梁涵洞第1合同.pdf", 20, 36)
    # res = mineru_parse_keep_artifacts("3.第三册桥梁涵洞第1合同_p20-36.pdf")
    getMineruOutputDir()
