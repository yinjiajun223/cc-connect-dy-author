"""Local image OCR: Apple Vision on macOS, RapidOCR (ONNX Runtime) elsewhere.

Both backends return {"engine", "pages": [{"page", "file", "width", "height",
"text", "lines"}]}, so image evidence validation is platform independent.
"""
from __future__ import annotations

import json
from pathlib import Path
import platform
import subprocess

VISION = "vision"
RAPIDOCR = "rapidocr"
SWIFT_SCRIPT = Path(__file__).with_name("ocr_images.swift")
_ENGINE = None


class OcrError(RuntimeError):
    pass


def default_backend():
    return VISION if platform.system() == "Darwin" else RAPIDOCR


def backend(config=None):
    value = str((config or {}).get("ocr_backend") or "auto").strip().lower()
    if value in ("", "auto"):
        return default_backend()
    if value in (VISION, RAPIDOCR):
        return value
    raise ValueError("ocr_backend 只能是 auto、vision 或 rapidocr。")


def run(paths, config=None):
    return _vision(paths) if backend(config) == VISION else _rapidocr(paths)


def _vision(paths):
    command = ["xcrun", "swift", str(SWIFT_SCRIPT), *[str(path) for path in paths]]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OcrError("无法运行本地 Apple Vision；需要 macOS 和 Xcode Command Line Tools。") from exc
    if process.returncode:
        raise OcrError(f"Apple Vision 识别失败：{process.stderr[-800:]}")
    try:
        return json.loads(process.stdout)
    except ValueError:
        raise OcrError("Apple Vision 输出无法解析。") from None


def _rapidocr(paths):
    from PIL import Image
    engine = _rapid_engine()
    pages = []
    for index, path in enumerate(paths, 1):
        try:
            with Image.open(path) as image:
                width, height = image.width, image.height
            rows, _ = engine(str(path))
        except Exception as exc:
            raise OcrError(f"第 {index} 页本地 OCR 失败：{type(exc).__name__}") from None
        lines = []
        for row in rows or []:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            box, text, confidence = row[0], row[1], row[2]
            try:
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                frame = [min(xs) / width, min(ys) / height,
                         (max(xs) - min(xs)) / width, (max(ys) - min(ys)) / height]
                score = float(confidence)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            lines.append({"text": str(text), "confidence": score, "box": frame})
        lines.sort(key=lambda line: (round(line["box"][1], 2), line["box"][0]))
        pages.append({"page": index, "file": str(path), "width": width, "height": height,
                      "text": "\n".join(line["text"] for line in lines), "lines": lines})
    return {"engine": "RapidOCR", "pages": pages}


def _rapid_engine():
    global _ENGINE
    if _ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise OcrError("未安装本地 OCR 依赖 rapidocr-onnxruntime；请按 requirements.lock.txt 安装后重试。") from exc
        _ENGINE = RapidOCR()
    return _ENGINE