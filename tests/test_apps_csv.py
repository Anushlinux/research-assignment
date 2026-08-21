import csv
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPS_CSV = PROJECT_ROOT / "data" / "apps.csv"
EXPECTED_HEADER = ["id", "app_name", "website_hint", "category", "notes"]
EXPECTED_PILOT = {
    22: "Twilio",
    31: "Google Ads",
    61: "GitHub",
    90: "PitchBook",
    98: "Mermaid CLI",
}


def load_apps() -> list[dict[str, str]]:
    with APPS_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows
    header, *data_rows = rows
    assert header == EXPECTED_HEADER
    assert all(len(row) == len(header) for row in data_rows)

    return [dict(zip(header, row, strict=True)) for row in data_rows]


def test_apps_csv_contract() -> None:
    apps = load_apps()
    ids = [int(app["id"]) for app in apps]
    category_counts = Counter(app["category"] for app in apps)

    assert len(apps) == 100
    assert ids == list(range(1, 101))
    assert len(set(ids)) == 100
    assert len(category_counts) == 10
    assert set(category_counts.values()) == {10}


def test_pilot_apps_match_the_brief() -> None:
    apps_by_id = {int(app["id"]): app for app in load_apps()}

    assert {app_id: apps_by_id[app_id]["app_name"] for app_id in EXPECTED_PILOT} == EXPECTED_PILOT
    assert apps_by_id[84]["app_name"] == "Paygent Connect"
    assert apps_by_id[84]["website_hint"] == ""
