from pathlib import Path
from collections import defaultdict


def split_parsed_value(parsed_value: str) -> tuple[str, str]:
    if not parsed_value:
        return "", ""

    if parsed_value[-1].isalpha():
        return parsed_value[:-1], parsed_value[-1]

    return parsed_value, ""


def format_base_name(parsed_value: str) -> str:
    digits, suffix = split_parsed_value(parsed_value)
    formatted_digits = digits.zfill(4)
    return formatted_digits + suffix


def build_new_name(
    parsed_value: str,
    old_name: str,
    duplicate_index: int = 0,
    low_confidence: bool = False,
) -> str:
    ext = Path(old_name).suffix.lower()
    base_name = format_base_name(parsed_value)

    if duplicate_index == 0:
        stem = base_name
    else:
        stem = f"{base_name}_{duplicate_index}"

    if low_confidence:
        stem += "-!"

    return stem + ext


def assign_unique_names(results: list[dict]) -> list[dict]:
    counters = defaultdict(int)

    for row in results:
        if row["status"] != "ok" or not row.get("parsed_value"):
            row["rename_done"] = False
            row["rename_comment"] = "не переименован"
            continue

        base_name = format_base_name(row["parsed_value"])
        duplicate_index = counters[base_name]

        row["formatted_base_name"] = base_name
        row["new_name"] = build_new_name(
        parsed_value=row["parsed_value"],
        old_name=row["old_name"],
        duplicate_index=duplicate_index,
        low_confidence=row.get("low_confidence", False),
    )

        counters[base_name] += 1

    return results


def rename_files(results: list[dict], input_dir: Path, dry_run: bool = True) -> list[dict]:
    for row in results:
        if row["status"] != "ok" or not row.get("new_name"):
            row["rename_done"] = False
            if not row.get("rename_comment"):
                row["rename_comment"] = "не переименован"
            continue

        old_path = input_dir / row["old_name"]
        new_path = input_dir / row["new_name"]

        if dry_run:
            row["rename_done"] = False
            row["rename_comment"] = f"План: {old_path.name} -> {new_path.name}"
            continue

        old_path.rename(new_path)
        row["rename_done"] = True
        row["rename_comment"] = f"Renamed: {old_path.name} -> {new_path.name}"

    return results