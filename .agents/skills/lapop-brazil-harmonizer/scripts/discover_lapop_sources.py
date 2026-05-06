from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from utils import CATALOG_PAGE, DATASET_BASE, INTERIM_DIR, OFFICIAL_WAVES, year_slug


def discover_sources() -> pd.DataFrame:
    rows: list[dict] = [
        {
            "survey_year": None,
            "wave_label": None,
            "source_type": "catalog_page",
            "source_url": CATALOG_PAGE,
            "title": "LAPOP raw data access page",
            "file_format": "html",
            "official": True,
            "notes": "Official Vanderbilt page describing public data access and weighting guidance.",
        }
    ]

    session = requests.Session()
    for year in OFFICIAL_WAVES:
        slug = year_slug(year)
        page_url = f"{DATASET_BASE}/datasets/download/{slug}"
        resp = session.get(page_url, timeout=60)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title = soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else f"Brazil {year}"
        link = soup.find("a", href=lambda href: href and "/datasets/get/" in href)
        data_url = f"{DATASET_BASE}{link['href']}" if link else None
        file_format = Path(data_url).suffix.lstrip(".").lower() if data_url else None

        rows.append(
            {
                "survey_year": year,
                "wave_label": f"brazil_{year}",
                "source_type": "dataset_page",
                "source_url": page_url,
                "title": title,
                "file_format": "html",
                "official": True,
                "notes": "Official LAPOP Brazil dataset page with click-through public download link.",
            }
        )
        rows.append(
            {
                "survey_year": year,
                "wave_label": f"brazil_{year}",
                "source_type": "dataset_file",
                "source_url": data_url,
                "title": Path(data_url).name if data_url else None,
                "file_format": file_format,
                "official": True,
                "notes": "Official LAPOP Brazil public microdata file.",
            }
        )

    rows.append(
        {
            "survey_year": 2020,
            "wave_label": "brazil_2020",
            "source_type": "availability_check",
            "source_url": f"{DATASET_BASE}/datasets/download/bra_2020",
            "title": "Brazil 2020 availability check",
            "file_format": None,
            "official": True,
            "notes": "No official public Brazil 2020 wave found in the LAPOP catalog. Closest official waves are 2019 and 2021.",
        }
    )

    df = pd.DataFrame(rows)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(INTERIM_DIR / "source_inventory.csv", index=False)
    return df


if __name__ == "__main__":
    discover_sources()
