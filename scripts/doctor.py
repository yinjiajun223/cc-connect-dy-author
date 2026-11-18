#!/usr/bin/env python3
"""Local installation checks only: no network, imports of ML engines, or Vault writes."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys

import console

ROOT = Path(__file__).resolve().parents[1]
BASE_MODULES = ("yaml", "PIL", "f2", "yt_dlp", "browser_cookie3", "imageio_ffmpeg")


def platform_support():
    """Supported host, otherwise the platform label reported to the user."""
    system, machine = platform.system(), platform.machine()
    lowered = machine.lower()
    if system == "Darwin" and lowered in ("arm64", "aarch64"):
        return True, f"macOS {machine}"
    if system == "Windows" and lowered in ("amd64", "x86_64"):
        return True, f"Windows {machine}"
    return False, f"{system} {machine}"


def modules_present(*names):
    return {name: importlib.util.find_spec(name) is not None for name in names}


def main():
    console.force_utf8()
    issues = []
    supported, platform_name = platform_support()
    if not supported:
        issues.append(f"完整流程目前支持 macOS Apple Silicon 与 Windows 10/11 x64；{platform_name} 未验证")
    if sys.version_info[:2] != (3, 12):
        issues.append("请使用 Python 3.12")
    path = ROOT / "config.json"
    if not path.is_file():
        print(json.dumps({"status": "needs_setup", "issues": ["请先运行 scripts/configure.py"],
                          "platform": platform_name}, ensure_ascii=False))
        return 1
    config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("vault",):
        if not isinstance(config.get(key), str) or not Path(config[key]).is_dir():
            issues.append(f"{key} 目录不可用")
    if config.get("python") != os.path.abspath(sys.executable):
        issues.append("当前解释器入口与 config.json 的 python 不一致")
    import asr
    import ocr_backend
    try:
        asr_backend = asr.backend(config)
    except ValueError as exc:
        issues.append(str(exc))
        asr_backend = None
    try:
        ocr = ocr_backend.backend(config)
    except ValueError as exc:
        issues.append(str(exc))
        ocr = None
    if asr_backend == asr.MLX and not asr.apple_silicon():
        issues.append("asr_backend=mlx 仅支持 Apple Silicon；请改为 auto 或 faster-whisper")
    modules = modules_present(*BASE_MODULES)
    if asr_backend == asr.MLX:
        modules.update(modules_present("mlx_whisper"))
    elif asr_backend == asr.FASTER_WHISPER:
        modules.update(modules_present("faster_whisper"))
    if ocr == ocr_backend.RAPIDOCR:
        modules.update(modules_present("rapidocr_onnxruntime"))
    issues.extend(f"缺少依赖模块：{name}" for name, present in modules.items() if not present)
    if ocr == ocr_backend.VISION and not shutil.which("xcrun"):
        issues.append("缺少 Swift：请安装 Apple Command Line Tools")
    import chrome_session
    config, session = chrome_session.resolve_config(config)
    if session["status"] not in ("available", "disabled"):
        issues.append(session["message"])
    print(json.dumps({"status": "ready" if not issues else "needs_setup", "issues": issues,
                      "platform": platform_name, "asr_backend": asr_backend, "ocr_backend": ocr,
                      "dependency_modules_present": modules,
                      "browser_session": session,
                      "scope": "local_paths_and_dependency_discovery_only_not_live_Douyin_test"}, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
