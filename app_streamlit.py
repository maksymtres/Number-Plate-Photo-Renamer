from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import io

import pandas as pd
import streamlit as st

from main import process_folder
from renamer import rename_files
from reporter import build_summary


st.set_page_config(page_title="Photo Renamer MVP", layout="wide")

st.title("Number Plate Photo Renamer")
st.caption("Локальный MVP для распознавания номера на табличке и переименования фото")

st.markdown(
    """
Это Streamlit-оболочка поверх текущего пайплайна.

- **Dry run** — только анализ и расчёт новых имён
- **Apply** — реальное переименование файлов в выбранной папке

Рекомендуемый порядок работы:
1. сначала **Dry run**
2. проверить таблицу и проблемные случаи
3. потом при необходимости запускать **Apply**
"""
)


@st.cache_data(show_spinner=False)
def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


@st.cache_data(show_spinner=False)
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()


@st.cache_data(show_spinner=False)
def summary_to_text(summary: dict) -> str:
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

    return "\n".join(lines)


def empty_summary() -> dict:
    return {
        "renamed_count": 0,
        "low_confidence_count": 0,
        "unrenamed_count": 0,
        "low_confidence_files": [],
        "unrenamed_files": [],
    }


def init_state() -> None:
    if "results_df" not in st.session_state:
        st.session_state.results_df = pd.DataFrame()

    if "summary" not in st.session_state:
        st.session_state.summary = empty_summary()

    if "last_mode" not in st.session_state:
        st.session_state.last_mode = "Dry run"

    if "last_source" not in st.session_state:
        st.session_state.last_source = None

    if "last_message" not in st.session_state:
        st.session_state.last_message = None

    if "preview_mode" not in st.session_state:
        st.session_state.preview_mode = None

    if "preview_root" not in st.session_state:
        st.session_state.preview_root = None

    if "uploaded_preview_bytes" not in st.session_state:
        st.session_state.uploaded_preview_bytes = {}


init_state()


def run_pipeline(input_dir: Path, debug_dir: Path, dry_run: bool) -> tuple[dict, pd.DataFrame]:
    results = process_folder(input_dir, debug_dir)
    if not results:
        return empty_summary(), pd.DataFrame()

    results = rename_files(results, input_dir, dry_run=dry_run)
    summary = build_summary(results)
    df = pd.DataFrame(results)

    return summary, df


def resolve_disk_preview_path(row: dict, root: Path) -> Path | None:
    candidates: list[str] = []

    old_name = row.get("old_name")
    new_name = row.get("new_name")

    if isinstance(old_name, str) and old_name:
        candidates.append(old_name)

    if isinstance(new_name, str) and new_name and new_name not in candidates:
        candidates.append(new_name)

    for name in candidates:
        path = root / name
        if path.exists():
            return path

    return None


def show_problem_previews(df: pd.DataFrame) -> None:
    if df.empty:
        return

    problem_df = df[
        (df["status"] != "ok") | (df["low_confidence"] == True)
    ].copy()

    st.subheader("Проблемные изображения")

    if problem_df.empty:
        st.write("Нет проблемных случаев.")
        return

    cols = st.columns(3)

    for i, row in enumerate(problem_df.to_dict("records")):
        caption = (
            f"{row.get('old_name')} | "
            f"status={row.get('status')} | "
            f"low_conf={row.get('low_confidence')} | "
            f"parsed={row.get('parsed_value')}"
        )

        with cols[i % 3]:
            if st.session_state.preview_mode == "disk":
                root = Path(st.session_state.preview_root)
                image_path = resolve_disk_preview_path(row, root)

                if image_path is not None:
                    st.image(image_path, caption=caption, use_container_width=True)
                else:
                    st.warning(f"Файл не найден: {row.get('old_name')}")

            elif st.session_state.preview_mode == "uploaded":
                image_bytes = st.session_state.uploaded_preview_bytes.get(row.get("old_name"))
                if image_bytes is not None:
                    st.image(image_bytes, caption=caption, use_container_width=True)
                else:
                    st.warning(f"Нет превью: {row.get('old_name')}")

            else:
                st.write(caption)


with st.sidebar:
    st.header("Настройки")

    with st.form("run_form"):
        input_mode = st.radio(
            "Источник изображений",
            ["Папка на диске", "Загрузить несколько файлов"],
        )

        mode = st.radio("Режим обработки", ["Dry run", "Apply"], index=0)
        dry_run = mode == "Dry run"

        show_only_problematic = st.checkbox(
            "Показывать только проблемные случаи",
            value=False,
        )

        if input_mode == "Папка на диске":
            folder_value = st.text_input("Путь к папке с фото", value="input_photos")
            uploaded_files = None
        else:
            folder_value = None
            uploaded_files = st.file_uploader(
                "Загрузи изображения",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
            )

        submitted = st.form_submit_button(
            "Запустить обработку",
            type="primary",
            use_container_width=True,
        )


if submitted:
    with st.spinner("Обрабатываю изображения..."):
        with TemporaryDirectory() as tmp_root:
            tmp_root_path = Path(tmp_root)
            debug_dir = tmp_root_path / "debug_output"
            debug_dir.mkdir(parents=True, exist_ok=True)

            if input_mode == "Папка на диске":
                input_dir = Path(folder_value).expanduser()

                if not input_dir.exists() or not input_dir.is_dir():
                    st.error("Папка не найдена. Проверь путь.")
                    st.stop()

                working_dir = input_dir
                source_label = str(working_dir)
                uploaded_bytes_map = {}

            else:
                if not uploaded_files:
                    st.error("Сначала загрузи хотя бы один файл.")
                    st.stop()

                working_dir = tmp_root_path / "uploaded_images"
                working_dir.mkdir(parents=True, exist_ok=True)

                uploaded_bytes_map = {}
                for file in uploaded_files:
                    file_bytes = file.getbuffer().tobytes()
                    (working_dir / file.name).write_bytes(file_bytes)
                    uploaded_bytes_map[file.name] = file_bytes

                source_label = "uploaded files"

            summary, df = run_pipeline(working_dir, debug_dir, dry_run=dry_run)

            if df.empty:
                st.warning("Подходящие изображения не найдены.")
                st.stop()

            st.session_state.results_df = df
            st.session_state.summary = summary
            st.session_state.last_mode = mode
            st.session_state.last_source = source_label

            if input_mode == "Папка на диске":
                st.session_state.preview_mode = "disk"
                st.session_state.preview_root = str(working_dir)
                st.session_state.uploaded_preview_bytes = {}
            else:
                st.session_state.preview_mode = "uploaded"
                st.session_state.preview_root = None
                st.session_state.uploaded_preview_bytes = uploaded_bytes_map

            if input_mode == "Папка на диске" and not dry_run:
                st.session_state.last_message = "Файлы в выбранной папке были переименованы."
            elif input_mode == "Папка на диске" and dry_run:
                st.session_state.last_message = (
                    "Это был dry run: имена только рассчитаны, без реального переименования."
                )
            else:
                st.session_state.last_message = (
                    "Режим загрузки файлов использует временную папку. "
                    "Исходные файлы на диске не меняются."
                )


results_df = st.session_state.results_df
summary = st.session_state.summary

if st.session_state.last_source:
    st.info(
        f"Последний запуск: **{st.session_state.last_mode}** | "
        f"Источник: **{st.session_state.last_source}**"
    )

if st.session_state.last_message:
    st.success(st.session_state.last_message)

if not results_df.empty:
    display_df = results_df.copy()

    if show_only_problematic:
        display_df = display_df[
            (display_df["status"] != "ok") | (display_df["low_confidence"] == True)
        ]

    c1, c2, c3 = st.columns(3)
    c1.metric("Renamed", summary["renamed_count"])
    c2.metric("Low-confidence", summary["low_confidence_count"])
    c3.metric("Unrenamed", summary["unrenamed_count"])

    st.subheader("Результаты")
    st.dataframe(display_df, use_container_width=True)

    low_conf = summary["low_confidence_files"]
    unrenamed = summary["unrenamed_files"]

    left, right = st.columns(2)

    with left:
        st.subheader("Low-confidence")
        if low_conf:
            for name in low_conf:
                st.write(f"- {name}")
        else:
            st.write("Нет")

    with right:
        st.subheader("Unrenamed")
        if unrenamed:
            for name in unrenamed:
                st.write(f"- {name}")
        else:
            st.write("Нет")

    show_problem_previews(results_df)

    csv_bytes = df_to_csv_bytes(results_df)
    excel_bytes = df_to_excel_bytes(results_df)
    summary_text = summary_to_text(summary)

    st.subheader("Скачать отчёты")
    d1, d2, d3 = st.columns(3)

    d1.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name="report.csv",
        mime="text/csv",
        use_container_width=True,
    )

    d2.download_button(
        "Download Excel",
        data=excel_bytes,
        file_name="report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    d3.download_button(
        "Download Summary",
        data=summary_text.encode("utf-8"),
        file_name="summary_report.txt",
        mime="text/plain",
        use_container_width=True,
    )

else:
    st.warning("Пока нет результатов. Выбери параметры слева и нажми «Запустить обработку».")


st.markdown("---")
st.markdown(
    "Совет: для реальной работы с экспедиционными папками используй режим "
    "**Папка на диске**. Режим загрузки файлов удобен для демонстрации и отладки."
)