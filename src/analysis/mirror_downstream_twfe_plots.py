from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_BASE = ROOT / "resources" / "did" / "downstream_outcomes" / "unweighted"
TARGET_BASE = ROOT / "resources" / "images" / "regressions" / "twfe_dynamic"


def main() -> None:
    for pdf_path in SOURCE_BASE.glob("*/twfe_dynamic/event_study_plot.pdf"):
        outcome = pdf_path.parent.parent.name
        target_dir = TARGET_BASE / outcome
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, target_dir / "event_study_plot.pdf")
        png_path = pdf_path.with_suffix(".png")
        if png_path.exists():
            shutil.copy2(png_path, target_dir / "event_study_plot.png")


if __name__ == "__main__":
    main()
