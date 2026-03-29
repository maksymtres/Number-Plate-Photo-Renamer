import csv
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None


def _collect_fieldnames(results: list[dict]) -> list[str]:
    fieldnames = []
    seen = set()

    for row in results:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    return fieldnames


def save_csv(results: list[dict], output_path: str = "report.csv") -> Path | None:
    if not results:
        return None

    fieldnames = _collect_fieldnames(results)
    output = Path(output_path)

    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    return output


def save_excel(results: list[dict], output_path: str = "report.xlsx") -> Path | None:
    if not results or pd is None:
        return None

    output = Path(output_path)
    df = pd.DataFrame(results)
    df.to_excel(output, index=False)

    return output


def build_summary(results: list[dict]) -> dict:
    renamed = [row for row in results if row.get("status") == "ok"]
    low_confidence = [row for row in results if row.get("low_confidence") is True]
    unrenamed = [row for row in results if row.get("status") != "ok"]

    return {
        "renamed_count": len(renamed),
        "low_confidence_count": len(low_confidence),
        "unrenamed_count": len(unrenamed),
        "low_confidence_files": [row["old_name"] for row in low_confidence],
        "unrenamed_files": [row["old_name"] for row in unrenamed],
    }


def print_summary(results: list[dict]) -> None:
    summary = build_summary(results)

    print(f"Renamed files: {summary['renamed_count']}")
    print(f"Low-confidence files: {summary['low_confidence_count']}")
    print(f"Unrenamed files: {summary['unrenamed_count']}")

    print("\nLow-confidence list:")
    if summary["low_confidence_files"]:
        for name in summary["low_confidence_files"]:
            print(f" - {name}")
    else:
        print(" - none")

    print("\nUnrenamed list:")
    if summary["unrenamed_files"]:
        for name in summary["unrenamed_files"]:
            print(f" - {name}")
    else:
        print(" - none")


def save_text_summary(results: list[dict], output_path: str = "summary_report.txt") -> Path:
    summary = build_summary(results)
    output = Path(output_path)

    lines = [
        f"Renamed files: {summary['renamed_count']}",
        f"Low-confidence files: {summary['low_confidence_count']}",
        f"Unrenamed files: {summary['unrenamed_count']}",
        "",
        "Low-confidence list:",
    ]

    if summary["low_confidence_files"]:
        lines.extend(f" - {name}" for name in summary["low_confidence_files"])
    else:
        lines.append(" - none")

    lines.append("")
    lines.append("Unrenamed list:")

    if summary["unrenamed_files"]:
        lines.extend(f" - {name}" for name in summary["unrenamed_files"])
    else:
        lines.append(" - none")

    output.write_text("\n".join(lines), encoding="utf-8")
    return output