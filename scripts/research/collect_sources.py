"""Cache explicitly identified public engineering PDFs, recording content hashes.
This is a research utility, not a train simulator. Run from the repository root.
It requires the requests package already present in the research environment.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


SOURCES = {
    "jica-2011-lrt2": "https://openjicareport.jica.go.jp/pdf/1000023377_01.pdf",
    "lrta-2017-maintenance-tor": (
        "https://publiccontent.sinpro.cz/PublicFiles/2017/11/26/"
        "PB17-167-8.Bidding%20Document.072523311.pdf"
    ),
    "lrta-2017-maintenance-tor-archived": (
        "https://web.archive.org/web/20200612124628id_/http://publiccontent.sinpro.cz/"
        "PublicFiles/2017/11/26/PB17-167-8.Bidding%20Document.072523311.pdf"
    ),
    "lrta-2020-west-extension": "https://www.lrta.gov.ph/wp-content/uploads/2021/04/7203775.pdf",
    "lrta-2022-propulsion-tender": "https://www.lrta.gov.ph/wp-content/uploads/2022/06/8763449.pdf",
    "lrta-2021-foi-rolling-stock": "https://www.foi.gov.ph/documents/51680/img-125091420.pdf",
    "toshiba-2003-highlights": (
        "https://www.global.toshiba/content/dam/toshiba/migration/corp/"
        "techReviewAssets/tech/review/2003/high2003/high2003pdf/0305.pdf"
    ),
    "depdev-2020-lrt2-impact-evaluation": (
        "https://nep.depdev.gov.ph/storage/document/"
        "1606724568_Impact%20Evaluation_LRT%202%20Project_Final%20Report.pdf"
    ),
    "denr-2020-lrt2-west-eis": "https://eia.emb.gov.ph/wp-content/uploads/2020/12/revised-EIS.pdf",
    "jica-lrt2-japanese-report": "https://openjicareport.jica.go.jp/pdf/1000023375.pdf",
    "jica-2011-lrt2-part2": "https://openjicareport.jica.go.jp/pdf/1000023377_02.pdf",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=SOURCES, help="Check selected sources; retain other manifest entries")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    cache = root / ".cache" / "research"
    cache.mkdir(parents=True, exist_ok=True)
    output = root / "docs" / "research" / "source-manifest.json"
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else []
    records = {record["source_id"]: record for record in existing}
    for source_id, url in SOURCES.items():
        if args.only and source_id not in args.only:
            continue
        target = cache / f"{source_id}.pdf"
        record = {"source_id": source_id, "url": url,
                  "checked_at_utc": datetime.now(timezone.utc).isoformat()}
        try:
            if not target.exists():
                with requests.get(url, timeout=(10, 60), stream=True) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    for chunk in response.iter_content(1024 * 1024):
                        payload.extend(chunk)
                        if len(payload) > 100 * 1024 * 1024:
                            raise ValueError("Research source exceeds 100 MiB limit")
                    if not payload.startswith(b"%PDF"):
                        raise ValueError("Response is not a PDF")
                    target.write_bytes(payload)
                    record["final_url"] = response.url
            payload = target.read_bytes()
            if not payload.startswith(b"%PDF"):
                raise ValueError("Cached file is not a PDF")
            record.update(
                status="cached",
                sha256=hashlib.sha256(payload).hexdigest(),
                bytes=len(payload),
                cache_path=target.relative_to(root).as_posix(),
                checked_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        except (requests.RequestException, OSError, ValueError) as error:
            record.update(status="unavailable", error=str(error))
        records[source_id] = record
        print(f"{source_id}: {record['status']}", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(list(records.values()), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
