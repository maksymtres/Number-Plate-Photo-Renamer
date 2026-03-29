from pathlib import Path
import argparse

from src.detector import detect_plate
from src.recognizer import recognize_text
from src.text_processor import normalize_text, validate_text
from src.renamer import build_new_name, assign_unique_names, rename_files
from src.reporter import save_csv, save_excel, print_summary, save_text_summary

LOW_CONFIDENCE_THRESHOLD = 60


def process_one_file(image_path: Path, debug_dir: Path | None = None) -> dict:
    old_name = image_path.name

    plate_region = detect_plate(image_path, debug_dir=debug_dir)
    if plate_region is None:
        return {
            "old_name": old_name,
            "ocr_raw": None,
            "normalized_text": None,
            "parsed_value": None,
            "new_name": None,
            "status": "error",
            "error_reason": "табличка не найдена",
            "confidence": 0.0,
            "low_confidence": False,
        }

    ocr_raw, confidence = recognize_text(plate_region)
    normalized_text = normalize_text(ocr_raw)
    is_valid, error_reason = validate_text(normalized_text)

    low_confidence = (
        confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD
    )

    if not is_valid:
        return {
            "old_name": old_name,
            "ocr_raw": ocr_raw,
            "normalized_text": normalized_text,
            "parsed_value": None,
            "new_name": None,
            "status": "error",
            "error_reason": error_reason,
            "confidence": confidence,
            "low_confidence": low_confidence,
        }

    parsed_value = normalized_text
    new_name = build_new_name(parsed_value, old_name)

    return {
        "old_name": old_name,
        "ocr_raw": ocr_raw,
        "normalized_text": normalized_text,
        "parsed_value": parsed_value,
        "new_name": new_name,
        "status": "ok",
        "error_reason": None,
        "confidence": confidence,
        "low_confidence": low_confidence,
    }


def process_folder(input_dir: Path, debug_dir: Path) -> list[dict]:
    image_files = sorted(
        [
            p for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
    )

    if not image_files:
        print(f"В папке нет изображений: {input_dir}")
        return []

    results = []
    for image_path in image_files:
        row = process_one_file(image_path, debug_dir=debug_dir)
        results.append(row)

    results = assign_unique_names(results)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Переименование фото по номерам на табличках"
    )

    parser.add_argument(
        "--input-dir",
        type=str,
        default="input_photos",
        help="Папка с изображениями",
    )
    parser.add_argument(
        "--debug-dir",
        type=str,
        default="debug_output",
        help="Папка для debug-изображений",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default=".",
        help="Папка для report.csv / report.xlsx / summary_report.txt",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Ничего не переименовывать, только отчёты",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Реально переименовать файлы",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent

    input_dir = Path(args.input_dir)
    if not input_dir.is_absolute():
        input_dir = project_dir / input_dir

    debug_dir = Path(args.debug_dir)
    if not debug_dir.is_absolute():
        debug_dir = project_dir / debug_dir

    report_dir = Path(args.report_dir)
    if not report_dir.is_absolute():
        report_dir = project_dir / report_dir

    debug_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    dry_run = not args.apply

    results = process_folder(input_dir, debug_dir)
    if not results:
        return

    results = rename_files(results, input_dir, dry_run=dry_run)

    print_summary(results)

    csv_path = save_csv(results, str(report_dir / "report.csv"))
    excel_path = save_excel(results, str(report_dir / "report.xlsx"))
    summary_path = save_text_summary(results, str(report_dir / "summary_report.txt"))

    print()
    print("Mode:", "dry-run" if dry_run else "apply")
    if csv_path is not None:
        print("CSV:", csv_path.resolve())
    if excel_path is not None:
        print("Excel:", excel_path.resolve())
    print("Summary:", summary_path.resolve())


if __name__ == "__main__":
    main()