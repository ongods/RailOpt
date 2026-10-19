"""Extract searchable PDF text and render selected evidence pages into the local cache.
Install pypdfium2==5.14.0 in .research-tools, or into the active environment.
Rendering does not itself certify a source: visual review is recorded separately.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".research-tools"))
import pypdfium2 as pdfium


def main():
    records = json.loads((ROOT / "docs/research/source-manifest.json").read_text(encoding="utf-8"))
    cache = ROOT / ".cache/research"
    for source in records:
        if source["status"] != "cached":
            continue
        source_id = source["source_id"]
        with pdfium.PdfDocument(ROOT / source["cache_path"]) as document:
            chunks = []
            selected = {
                "jica-2011-lrt2": {122, 142, 143, 159, 160},
                "jica-lrt2-japanese-report": {178, 179},
                "jica-2011-lrt2-part2": {195, 196, 199, 201, 202, 203, 204, 205, 206, 207},
            }.get(source_id, set())
            for index in range(len(document)):
                page = document[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range()
                    finally:
                        textpage.close()
                    chunks.append(f"\n=== PDF PAGE {index + 1} ===\n{text}")
                    if source_id == "toshiba-2003-highlights" and "Manila LRT" in text:
                        selected.add(index + 1)
                    if index + 1 in selected:
                        bitmap = page.render(scale=1.8)
                        try:
                            bitmap.to_pil().save(cache / f"{source_id}-page-{index + 1}.png")
                        finally:
                            bitmap.close()
                finally:
                    page.close()
            (cache / f"{source_id}.txt").write_text("".join(chunks), encoding="utf-8")
            print(f"{source_id}: {len(document)} pages; rendered {sorted(selected)}", flush=True)


if __name__ == "__main__":
    main()
