from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from urllib.parse import urlparse

import pandas as pd
import requests

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_eleitorado_common import INTERIM_DIR, OFFICIAL_PACKAGE_YEARS, RAW_DIR, TARGET_YEARS, ensure_directories


API_BASE = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=eleitorado-{year}"
DATASET_PAGE = "https://dadosabertos.tse.jus.br/dataset/eleitorado-{year}"


def fetch_package(year: int) -> dict | None:
    if year not in OFFICIAL_PACKAGE_YEARS:
        return None
    response = requests.get(API_BASE.format(year=year), timeout=60)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"Package lookup failed for year {year}: {payload}")
    return payload["result"]


def select_main_resource(package: dict) -> dict:
    candidates = [
        resource
        for resource in package.get("resources", [])
        if resource.get("name", "").strip().lower() == package["title"].strip().lower()
    ]
    if not candidates:
        raise RuntimeError(f"Main electorate resource not found for package {package['name']}")
    return candidates[0]


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    head = requests.head(url, allow_redirects=True, timeout=60)
    head.raise_for_status()
    expected_size = int(head.headers.get("content-length", "0") or 0)
    if destination.exists() and (expected_size == 0 or destination.stat().st_size == expected_size):
        return
    tmp_destination = destination.with_suffix(destination.suffix + ".part")
    response = requests.get(url, stream=True, timeout=180)
    response.raise_for_status()
    with tmp_destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    if expected_size and tmp_destination.stat().st_size != expected_size:
        raise RuntimeError(
            f"Incomplete download for {destination.name}: expected {expected_size} bytes, got {tmp_destination.stat().st_size}"
        )
    tmp_destination.replace(destination)


def build_source_index() -> pd.DataFrame:
    rows: list[dict] = []
    for year in TARGET_YEARS:
        package = fetch_package(year)
        if package is None:
            rows.append(
                {
                    "year": year,
                    "source_url": "",
                    "source_page": "",
                    "file_name": "",
                    "file_format": "",
                    "notes": "No official historical eleitorado package found in the TSE open-data catalog for this odd year; official historical series are exposed for election years only.",
                    "status": "not_found_in_catalog",
                    "download_path": "",
                    "sha256": "",
                }
            )
            continue

        resource = select_main_resource(package)
        file_name = Path(urlparse(resource["url"]).path).name
        raw_dir = RAW_DIR / str(year)
        raw_dir.mkdir(parents=True, exist_ok=True)
        destination = raw_dir / file_name
        download_file(resource["url"], destination)

        rows.append(
            {
                "year": year,
                "source_url": resource["url"],
                "source_page": DATASET_PAGE.format(year=year),
                "file_name": file_name,
                "file_format": resource.get("format", ""),
                "notes": f"Official TSE open-data historical electorate package for {year}.",
                "status": "downloaded",
                "download_path": str(destination.relative_to(RAW_DIR.parent.parent)),
                "sha256": sha256sum(destination),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    ensure_directories()
    df = build_source_index().sort_values("year").reset_index(drop=True)
    output_path = INTERIM_DIR / "source_index.csv"
    df.to_csv(output_path, index=False)
    print(f"Wrote {output_path} with {len(df)} rows.")


if __name__ == "__main__":
    main()
