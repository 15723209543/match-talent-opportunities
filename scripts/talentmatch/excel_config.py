"""本模块直接读取并校验指标Excel，确保每次运行都使用最新系数和配置。"""

from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List
from xml.etree import ElementTree as ET


SKILL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_WORKBOOK = SKILL_ROOT / "reference_indicators" / "talent_matching_indicators.xlsx"
CONFIG_SHEET_NAME = "匹配指标配置"
PROFILE_SHEET_NAME = "岗位权重模板"
DEFAULT_PROFILE = "general"

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_COLUMN_RE = re.compile(r"([A-Z]+)")


class MetricConfigError(ValueError):
    """Raised when the editable metric workbook is missing or invalid."""


def _column_number(reference: str) -> int:
    match = _COLUMN_RE.match(reference.upper())
    if not match:
        return 0
    value = 0
    for character in match.group(1):
        value = value * 26 + ord(character) - 64
    return value


def _shared_strings(archive: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings: List[str] = []
    for item in root.findall(f"{{{_MAIN_NS}}}si"):
        strings.append("".join(node.text or "" for node in item.iter(f"{{{_MAIN_NS}}}t")))
    return strings


def _sheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relation_id = None
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relation_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
            break
    if not relation_id:
        raise MetricConfigError(f"Excel 中缺少工作表：{sheet_name}")

    relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = None
    for relation in relations.findall(f"{{{_PKG_REL_NS}}}Relationship"):
        if relation.attrib.get("Id") == relation_id:
            target = relation.attrib.get("Target")
            break
    if not target:
        raise MetricConfigError(f"无法定位工作表：{sheet_name}")
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def _cell_value(cell: ET.Element, shared: List[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{_MAIN_NS}}}t"))
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    raw = value_node.text
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            raise MetricConfigError("Excel 共享字符串索引损坏")
    if cell_type in {"str", "e"}:
        return raw
    if cell_type == "b":
        return raw == "1"
    try:
        number = float(raw)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw


def _read_rows(path: Path) -> List[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as archive:
            shared = _shared_strings(archive)
            root = ET.fromstring(archive.read(_sheet_path(archive, CONFIG_SHEET_NAME)))
    except FileNotFoundError as exc:
        raise MetricConfigError(f"匹配指标 Excel 不存在：{path}") from exc
    except zipfile.BadZipFile as exc:
        raise MetricConfigError(f"匹配指标文件不是有效的 xlsx：{path}") from exc
    except (KeyError, ET.ParseError) as exc:
        raise MetricConfigError(f"匹配指标 Excel 结构损坏：{path}") from exc

    table: List[List[Any]] = []
    for row in root.findall(f".//{{{_MAIN_NS}}}row"):
        values: Dict[int, Any] = {}
        for cell in row.findall(f"{{{_MAIN_NS}}}c"):
            values[_column_number(cell.attrib.get("r", ""))] = _cell_value(cell, shared)
        if values:
            table.append([values.get(index, "") for index in range(1, max(values) + 1)])
    if not table:
        raise MetricConfigError("匹配指标工作表为空")

    headers = [str(value).strip() for value in table[0]]
    required_headers = [
        "参考指标影响系数（0-10）",
        "指标ID",
        "指标名称",
        "视角",
        "类别",
        "启用",
        "计算方法",
        "缺失值策略",
        "指标说明",
        "候选人输入字段",
        "岗位输入字段",
    ]
    missing_headers = [header for header in required_headers if header not in headers]
    if missing_headers:
        raise MetricConfigError("Excel 缺少列：" + "、".join(missing_headers))

    records: List[Dict[str, Any]] = []
    for row_number, row in enumerate(table[1:], start=2):
        padded = row + [""] * max(0, len(headers) - len(row))
        record = dict(zip(headers, padded))
        if not str(record.get("指标ID", "")).strip():
            continue
        record["_row"] = row_number
        records.append(record)
    return records


def _read_profile_rows(path: Path) -> List[Dict[str, Any]]:
    """读取同一工作簿中的岗位权重模板；旧版自定义工作簿可暂时没有该工作表。"""
    try:
        with zipfile.ZipFile(path) as archive:
            shared = _shared_strings(archive)
            root = ET.fromstring(archive.read(_sheet_path(archive, PROFILE_SHEET_NAME)))
    except MetricConfigError:
        return []
    except (FileNotFoundError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise MetricConfigError(f"岗位权重模板读取失败：{path}") from exc
    table: List[List[Any]] = []
    for row in root.findall(f".//{{{_MAIN_NS}}}row"):
        values: Dict[int, Any] = {}
        for cell in row.findall(f"{{{_MAIN_NS}}}c"):
            values[_column_number(cell.attrib.get("r", ""))] = _cell_value(cell, shared)
        if values:
            table.append([values.get(index, "") for index in range(1, max(values) + 1)])
    if not table:
        return []
    headers = [str(value).strip() for value in table[0]]
    required = ["模板ID", "模板名称", "版本", "适用岗位关键词", "指标ID（留空表示模板元数据）", "覆盖系数（0-10）"]
    missing = [header for header in required if header not in headers]
    if missing:
        raise MetricConfigError("岗位权重模板缺少列：" + "、".join(missing))
    records = []
    for row_number, row in enumerate(table[1:], 2):
        padded = row + [""] * max(0, len(headers) - len(row))
        record = dict(zip(headers, padded))
        if str(record.get("模板ID", "")).strip():
            record["_row"] = row_number
            records.append(record)
    return records


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "是", "启用"}


def load_metric_config(path: str | None = None, profile: str = DEFAULT_PROFILE) -> Dict[str, Any]:
    """每次调用重新读取工作簿，并按安全的模板ID覆盖指定指标系数。"""
    source = Path(path).expanduser().resolve() if path else DEFAULT_METRICS_WORKBOOK
    profile_id = str(profile or DEFAULT_PROFILE).strip().casefold()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", profile_id):
        raise MetricConfigError("岗位权重模板ID格式无效")
    records = _read_rows(source)
    profile_rows = _read_profile_rows(source)
    metrics: List[Dict[str, Any]] = []
    overall: Dict[str, float] = {}
    seen = set()
    errors: List[str] = []

    for record in records:
        row = record["_row"]
        indicator_id = str(record["指标ID"]).strip()
        if indicator_id in seen:
            errors.append(f"第{row}行指标ID重复:{indicator_id}")
            continue
        seen.add(indicator_id)
        try:
            coefficient = float(record["参考指标影响系数（0-10）"])
        except (TypeError, ValueError):
            errors.append(f"第{row}行系数不是数字:{indicator_id}")
            continue
        if not 0 <= coefficient <= 10:
            errors.append(f"第{row}行系数超出0-10:{indicator_id}")
        perspective = str(record["视角"]).strip().casefold()
        enabled = _as_bool(record["启用"])
        if perspective not in {"recruiter", "candidate", "overall"}:
            errors.append(f"第{row}行视角无效:{indicator_id}")
        item = {
            "id": indicator_id,
            "name": str(record["指标名称"]).strip() or indicator_id,
            "side": perspective,
            "category": str(record["类别"]).strip(),
            "coefficient": coefficient,
            "enabled": enabled,
            "method": str(record["计算方法"]).strip(),
            "missing_policy": str(record["缺失值策略"]).strip() or "exclude",
            "description": str(record["指标说明"]).strip(),
            "candidate_fields": str(record["候选人输入字段"]).strip(),
            "job_fields": str(record["岗位输入字段"]).strip(),
            "row": row,
        }
        if perspective == "overall":
            overall[indicator_id] = coefficient
        else:
            metrics.append(item)

    for side in ("recruiter", "candidate"):
        active = [item for item in metrics if item["side"] == side and item["enabled"] and item["coefficient"] > 0]
        if not active:
            errors.append(f"{side}至少需要一个启用且系数大于0的指标")
    for key in ("overall_recruiter", "overall_candidate"):
        if key not in overall or overall[key] <= 0:
            errors.append(f"缺少有效的双向合成系数:{key}")
    if errors:
        raise MetricConfigError("匹配指标 Excel 校验失败：" + "；".join(errors))

    available_profiles: Dict[str, Dict[str, Any]] = {
        DEFAULT_PROFILE: {"id": DEFAULT_PROFILE, "name": "通用岗位", "version": "1.0", "applicable_roles": "全部岗位", "overrides": {}}
    }
    for record in profile_rows:
        row_profile = str(record.get("模板ID", "")).strip().casefold()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", row_profile):
            errors.append(f"岗位权重模板第{record['_row']}行模板ID无效")
            continue
        metadata = available_profiles.setdefault(row_profile, {
            "id": row_profile,
            "name": str(record.get("模板名称", "")).strip() or row_profile,
            "version": str(record.get("版本", "")).strip() or "1.0",
            "applicable_roles": str(record.get("适用岗位关键词", "")).strip(),
            "overrides": {},
        })
        indicator_id = str(record.get("指标ID（留空表示模板元数据）", "")).strip()
        if not indicator_id:
            continue
        if indicator_id not in seen or indicator_id in overall:
            errors.append(f"岗位权重模板第{record['_row']}行指标ID不存在或不可覆盖:{indicator_id}")
            continue
        try:
            override = float(record.get("覆盖系数（0-10）"))
        except (TypeError, ValueError):
            errors.append(f"岗位权重模板第{record['_row']}行覆盖系数不是数字:{indicator_id}")
            continue
        if not 0 <= override <= 10:
            errors.append(f"岗位权重模板第{record['_row']}行覆盖系数超出0-10:{indicator_id}")
            continue
        metadata["overrides"][indicator_id] = override
    if profile_id not in available_profiles:
        errors.append("未知岗位权重模板：" + profile_id + "；可选值：" + "、".join(sorted(available_profiles)))
    if errors:
        raise MetricConfigError("匹配指标 Excel 校验失败：" + "；".join(errors))
    selected_profile = available_profiles[profile_id]
    for item in metrics:
        item["base_coefficient"] = item["coefficient"]
        if item["id"] in selected_profile["overrides"]:
            item["coefficient"] = selected_profile["overrides"][item["id"]]

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "source": str(source),
        "sha256": digest,
        "metrics": metrics,
        "overall": overall,
        "metric_count": len(metrics),
        "profile": {key: value for key, value in selected_profile.items() if key != "overrides"},
        "profile_override_count": len(selected_profile["overrides"]),
        "available_profiles": [{key: value for key, value in item.items() if key != "overrides"} for item in available_profiles.values()],
    }


def validate_metric_config(path: str | None = None, profile: str = DEFAULT_PROFILE) -> List[str]:
    try:
        load_metric_config(path, profile)
        return []
    except (MetricConfigError, OSError) as exc:
        return [str(exc)]
