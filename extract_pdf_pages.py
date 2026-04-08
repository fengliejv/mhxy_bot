import io
from pathlib import Path
from pypdf import PdfReader, PdfWriter

# =====================================================================
# Configuration (User Editable)
# =====================================================================
INPUT_PDF_PATH = "resource/第九册 第分一册.pdf"
OUTPUT_PDF_PATH = "resource/第九册_提取版.pdf"

# The pages to extract. Supports integers (1-based index) and tuples (start, end) inclusive.
# Example: [1, 3, (5, 8)] means extract page 1, page 3, and pages 5 through 8.
PAGES_TO_EXTRACT = [
    1,          # Page 1
    (3, 5),     # Pages 3, 4, 5
]
# =====================================================================


def _parse_pages(pages_config: list, total_pages: int) -> list[int]:
    """Parse the configuration into a sorted list of 0-based page indices."""
    indices = set()
    for item in pages_config:
        if isinstance(item, int):
            # 1-based to 0-based
            idx = item - 1
            if 0 <= idx < total_pages:
                indices.add(idx)
        elif isinstance(item, tuple) and len(item) == 2:
            start, end = item
            # 1-based to 0-based
            for idx in range(start - 1, end):
                if 0 <= idx < total_pages:
                    indices.add(idx)
        else:
            print(f"Warning: Ignoring invalid page config item: {item}")
            
    return sorted(list(indices))


def extract_pages(input_pdf: Path, output_pdf: Path, pages_config: list):
    """Extract specified pages from input PDF and save to output PDF."""
    if not input_pdf.exists():
        print(f"Error: Input file not found: {input_pdf}")
        return

    # Ensure output directory exists
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    
    # Get 0-based indices to extract
    indices_to_extract = _parse_pages(pages_config, total_pages)
    
    if not indices_to_extract:
        print("Warning: No valid pages to extract based on the configuration.")
        return

    writer = PdfWriter()
    
    for idx in indices_to_extract:
        writer.add_page(reader.pages[idx])
        
    with open(output_pdf, "wb") as f:
        writer.write(f)
        
    print(f"Successfully extracted {len(indices_to_extract)} pages.")
    print(f"Saved to: {output_pdf}")
    print(f"Extracted 1-based page numbers: {[i + 1 for i in indices_to_extract]}")


def main():
    input_path = Path(INPUT_PDF_PATH)
    output_path = Path(OUTPUT_PDF_PATH)
    
    print(f"Input: {input_path}")
    print(f"Pages config: {PAGES_TO_EXTRACT}")
    
    extract_pages(input_path, output_path, PAGES_TO_EXTRACT)


if __name__ == "__main__":
    main()
