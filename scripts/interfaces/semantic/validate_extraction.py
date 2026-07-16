"""本脚本校验任意平台或模型产出的语义抽取JSON，并输出规范化结果。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPTS_DIR = next(parent for parent in Path(__file__).resolve().parents if (parent / "talentmatch").is_dir())
sys.path.insert(0, str(SCRIPTS_DIR))

from talentmatch.semantic_adapter import semantic_extraction_contract, validate_semantic_extraction


def main() -> int:
    parser = argparse.ArgumentParser(description="校验外部语义抽取结果")
    parser.add_argument("--input", help="待校验JSON")
    parser.add_argument("--output", help="规范化结果JSON")
    parser.add_argument("--print-contract", action="store_true", help="打印适配契约")
    args = parser.parse_args()
    if args.print_contract:
        print(json.dumps(semantic_extraction_contract(), ensure_ascii=False, indent=2))
        return 0
    if not args.input or not args.output:
        parser.error("校验时必须同时提供 --input 和 --output")
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = validate_semantic_extraction(payload)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
