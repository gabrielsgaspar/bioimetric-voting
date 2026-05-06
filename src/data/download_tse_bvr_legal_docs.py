from __future__ import annotations

import hashlib
import mimetypes
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_bvr_common import INTERIM_DIR, RAW_TSE_DIR, TSE_SOURCE_CATALOG, ensure_directories, slugify_url


def _extension_for_response(url: str, content_type: str | None) -> str:
    if content_type:
        if "pdf" in content_type:
            return ".pdf"
        if "zip" in content_type:
            return ".zip"
        if "json" in content_type:
            return ".json"
        if "html" in content_type:
            return ".html"
    guessed = mimetypes.guess_extension((content_type or "").split(";")[0]) if content_type else None
    if guessed:
        return guessed
    if url.endswith(".pdf"):
        return ".pdf"
    if url.endswith(".zip"):
        return ".zip"
    return ".bin"


def download_tse_sources() -> pd.DataFrame:
    ensure_directories()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; codex-bvr-dataset/1.0)",
        }
    )

    records = []
    for row in TSE_SOURCE_CATALOG:
        url = row["source_url"]
        response = session.get(url, timeout=120)
        response.raise_for_status()

        extension = _extension_for_response(url, response.headers.get("content-type"))
        filename = f"{slugify_url(url)}{extension}"
        path = RAW_TSE_DIR / filename

        with path.open("wb") as handle:
            handle.write(response.content)

        sha256 = hashlib.sha256(response.content).hexdigest()
        record = dict(row)
        record["downloaded_path"] = str(path.relative_to(path.parents[2]))
        record["content_type"] = response.headers.get("content-type", "")
        record["status_code"] = response.status_code
        record["sha256"] = sha256
        records.append(record)

    df = pd.DataFrame(records)
    for column in ["municipality_scope", "election_use_year", "rollout_year", "hybrid_flag"]:
        if column not in df.columns:
            df[column] = ""
    df.to_csv(INTERIM_DIR / "tse_legal_sources_index.csv", index=False)
    return df


def main() -> None:
    download_tse_sources()


if __name__ == "__main__":
    main()
