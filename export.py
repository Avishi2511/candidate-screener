import argparse
import csv
import datetime
import glob
import json
import os

CSV_COLUMNS = [
    "timestamp",
    "candidate_name",
    "phone_number",
    "role",
    "call_outcome",
    "current_role",
    "years_experience",
    "skills",
    "notice_period_days",
    "current_ctc_lpa",
    "expected_ctc_lpa",
    "open_to_relocation",
    "classification",
    "classification_reason",
]


def _flatten(record: dict) -> dict:
    answers = record.get("answers", {})
    return {
        "timestamp": record.get("timestamp"),
        "candidate_name": record.get("candidate_name"),
        "phone_number": record.get("phone_number"),
        "role": record.get("role"),
        "call_outcome": record.get("call_outcome"),
        "current_role": answers.get("current_role"),
        "years_experience": answers.get("years_experience"),
        "skills": ", ".join(answers.get("skills", [])),
        "notice_period_days": answers.get("notice_period_days"),
        "current_ctc_lpa": answers.get("current_ctc_lpa"),
        "expected_ctc_lpa": answers.get("expected_ctc_lpa"),
        "open_to_relocation": answers.get("open_to_relocation"),
        "classification": record.get("classification"),
        "classification_reason": record.get("classification_reason"),
    }


def export_csv(
    from_date: datetime.date = None,
    to_date: datetime.date = None,
    output_path: str = "screening_results/all_results.csv",
) -> tuple[int, str]:
    """
    Read all JSONs from screening_results/, filter by date range, write a CSV.
    Returns (row_count, output_path).
    """
    records = []
    for filepath in sorted(glob.glob("screening_results/*.json")):
        try:
            with open(filepath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        ts = datetime.datetime.fromisoformat(data["timestamp"]).date()
        if from_date and ts < from_date:
            continue
        if to_date and ts > to_date:
            continue

        records.append(_flatten(data))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(records)

    return len(records), output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export screening results to CSV.")
    parser.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD), inclusive")
    parser.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD), inclusive")
    parser.add_argument("--out", default=None, help="Output CSV path (default: auto-named in screening_results/)")
    args = parser.parse_args()

    from_date = datetime.date.fromisoformat(args.from_date) if args.from_date else None
    to_date = datetime.date.fromisoformat(args.to_date) if args.to_date else None

    if args.out:
        output_path = args.out
    elif from_date or to_date:
        label = f"{args.from_date or 'start'}_to_{args.to_date or 'today'}"
        output_path = f"screening_results/export_{label}.csv"
    else:
        output_path = "screening_results/all_results.csv"

    count, path = export_csv(from_date, to_date, output_path)
    print(f"Exported {count} record(s) → {path}")
