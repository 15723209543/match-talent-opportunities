"""本模块提供安全的文件读取、结构化数据加载、编码处理和结果写出工具。"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.etree import ElementTree


MAX_BYTES = 5 * 1024 * 1024


class InputError(ValueError):
    pass


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_text(path: Path) -> str:
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise InputError(f"File exceeds {MAX_BYTES} bytes: {path}")
    if path.suffix.casefold() == ".docx":
        return extract_docx(path)
    if path.suffix.casefold() == ".pdf":
        raise InputError("PDF text extraction requires the host PDF tool; provide extracted text or JSON.")
    return decode_bytes(path.read_bytes())


def extract_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise InputError(f"Unreadable DOCX: {path}") from exc
    root = ElementTree.fromstring(xml)
    paragraphs = []
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    for paragraph in root.iter(namespace + "p"):
        parts = [node.text or "" for node in paragraph.iter(namespace + "t")]
        if parts:
            paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def load_source(value: Any, literal: bool = False) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        raise InputError("Input is missing")
    if literal:
        return str(value)
    path = Path(str(value))
    if not path.exists():
        raise InputError(f"Input path does not exist: {path}")
    if path.is_dir():
        raise InputError(f"Expected a file, got directory: {path}")
    suffix = path.suffix.casefold()
    text = read_text(path)
    if suffix == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError(f"Invalid JSON in {path}: {exc}") from exc
    if suffix == ".jsonl":
        records = []
        for line_no, line in enumerate(text.splitlines(), 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise InputError(f"Invalid JSONL at line {line_no}: {exc}") from exc
        return records
    if suffix == ".csv":
        return list(csv.DictReader(io.StringIO(text)))
    return text


def load_collection(path_value: str) -> List[Any]:
    path = Path(path_value)
    if path.is_dir():
        records = []
        for child in sorted(path.iterdir()):
            if child.suffix.casefold() in {".json", ".jsonl", ".csv", ".txt", ".md", ".docx"}:
                value = load_source(child)
                records.extend(value if isinstance(value, list) else [value])
        if not records:
            raise InputError(f"No supported input files in directory: {path}")
        return records
    value = load_source(path)
    return value if isinstance(value, list) else [value]


def write_json(data: Any, path: str | None = None) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")
    else:
        # ASCII-escaped stdout avoids Windows pipe/code-page corruption while remaining valid JSON.
        sys.stdout.write(json.dumps(data, ensure_ascii=True, indent=2, sort_keys=False) + "\n")


def write_text(text: str, path: str | None = None) -> None:
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.rstrip() + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text.rstrip() + "\n")


def safe_csv_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text
