from pathlib import Path

from pypdf import PdfReader, PdfWriter

INPUT_PDF_PATH = "resource/第九册 第分一册.pdf"
OUTPUT_DIR = "resource"
PAGES_PER_PART = 50


def split_pdf_by_pages(input_pdf: Path, output_dir: Path, pages_per_part: int = 50) -> list[Path]:
    input_pdf = input_pdf.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_pdf.exists():
        raise FileNotFoundError(str(input_pdf))
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError("input must be a .pdf file")

    if pages_per_part <= 0:
        raise ValueError("pages_per_part must be > 0")

    reader = PdfReader(str(input_pdf))
    if getattr(reader, "is_encrypted", False):
        raise ValueError("input PDF is encrypted; please decrypt it first")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("input PDF has no pages")

    stem = input_pdf.stem
    produced: list[Path] = []

    part_index = 1
    start = 0
    while start < total_pages:
        end = min(start + pages_per_part, total_pages)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        out_path = output_dir / f"{stem}.part{part_index:03d}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)
        produced.append(out_path)

        part_index += 1
        start = end

    return produced


def main() -> int:
    input_pdf = Path(INPUT_PDF_PATH).expanduser() if INPUT_PDF_PATH else None
    output_dir = Path(OUTPUT_DIR).expanduser() if OUTPUT_DIR else None
    pages_per_part = int(PAGES_PER_PART)

    if input_pdf is None:
        raise ValueError("请在脚本顶部配置 INPUT_PDF_PATH")
    if output_dir is None:
        raise ValueError("请在脚本顶部配置 OUTPUT_DIR")

    print(f"Input: {input_pdf}")
    print(f"Output dir: {output_dir}")
    print(f"Pages per part: {pages_per_part}")

    parts = split_pdf_by_pages(input_pdf, output_dir, pages_per_part=pages_per_part)

    print(f"Parts: {len(parts)}")
    for p in parts:
        print(f"- {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
