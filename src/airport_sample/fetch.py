"""Fetch public snapshots; preserves source licenses. SPDX-License-Identifier: MIT"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = "airport-database-sample/0.1 (https://github.com/rkajiyama/airport-database-sample)"


def download(url: str, accept: str = "*/*") -> bytes:
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept}), timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Download failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the complete configured source snapshots")
    parser.add_argument("--output", type=Path, default=ROOT / "data/source")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    query = (ROOT / "config/airlines.rq").read_text()
    sources = [
        (name, f"https://davidmegginson.github.io/ourairports-data/{name}", "Public Domain", "https://ourairports.com/data/")
        for name in ("airports.csv", "countries.csv", "regions.csv")
    ]
    sources.append(("airlines.json", "https://query.wikidata.org/sparql?" + urlencode({"query": query, "format": "json"}), "CC0-1.0", "https://www.wikidata.org/wiki/Wikidata:Licensing"))
    manifest = {"sources": [], "airline_query": query}
    for filename, url, license_name, license_url in sources:
        print(f"Fetching {filename}", flush=True)
        raw = download(url, "application/sparql-results+json" if filename.endswith(".json") else "text/csv")
        if filename.endswith(".json"):
            rows = json.loads(raw)["results"]["bindings"]
            count = len({row["airline"]["value"] for row in rows})
            if not count:
                raise ValueError("Empty airline result")
        else:
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            if not rows or "<!DOCTYPE" in raw[:100].decode("utf-8", errors="ignore"):
                raise ValueError(f"Invalid CSV: {filename}")
            count = len(rows)
        (args.output / filename).write_bytes(raw)
        manifest["sources"].append({"file": filename, "url": url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "license": license_name, "license_url": license_url, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "entity_count": count})
        print(f"  {count:,} entities, {len(raw):,} bytes", flush=True)
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
