"""Local speech recognition: MLX Whisper on Apple Silicon, faster-whisper elsewhere.

Both backends return the same shape: {"text", "segments", "language"}, so the
queue, transcript validation and checkpoint hashes stay platform independent.
"""
from __future__ import annotations

from pathlib import Path
import platform
import re

MLX = "mlx"
FASTER_WHISPER = "faster-whisper"
BACKENDS = (MLX, FASTER_WHISPER)
DEFAULT_MODELS = {MLX: "mlx-community/whisper-small-mlx", FASTER_WHISPER: "small"}
_MLX_MODEL = re.compile(r"^(?:mlx-community/)?whisper-(?P<size>.+?)-mlx$")
_WHISPER_NAME = re.compile(r"^whisper-(tiny|base|small|medium|large-v\d+(?:-turbo)?)$")
_ENGINES = {}


def apple_silicon():
    return platform.system() == "Darwin" and platform.machine().lower() in ("arm64", "aarch64")


def default_backend():
    return MLX if apple_silicon() else FASTER_WHISPER


def backend(config=None):
    value = str((config or {}).get("asr_backend") or "auto").strip().lower().replace("_", "-")
    if value in ("", "auto"):
        return default_backend()
    if value in BACKENDS:
        return value
    raise ValueError("asr_backend 只能是 auto、mlx 或 faster-whisper。")


def model_name(model, backend_name):
    """Map a model copied between platforms to the selected backend's naming."""
    model = str(model or DEFAULT_MODELS[backend_name])
    if backend_name == FASTER_WHISPER:
        match = _MLX_MODEL.fullmatch(model)
        if match:
            return match.group("size")
        if model.startswith("mlx-community/"):
            return model.split("/", 1)[1]
        match = _WHISPER_NAME.fullmatch(model)
        if match:
            return match.group(1)
    return model


def local_asr_model(model):
    """Prefer an already-downloaded Hugging Face snapshot so ASR works offline.

    Both mlx_whisper and faster-whisper otherwise ask Hugging Face on every run,
    which fails (e.g. SSLError / timeout) whenever huggingface.co is unreachable
    even though the model is cached. Falls back to the name so a first-time
    download still works.
    """
    if Path(model).expanduser().exists():
        return str(Path(model).expanduser())
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(repo_id=model, local_files_only=True)
    except Exception:
        return model


def transcribe(samples, model, backend_name, device="cpu"):
    if backend_name == MLX:
        return _mlx(samples, model)
    return _faster_whisper(samples, model, device)


def _mlx(samples, model):
    if not apple_silicon():
        raise ValueError("MLX ASR 仅支持 Apple Silicon；其他平台请使用 asr_backend=faster-whisper。")
    try:
        import mlx_whisper
    except ImportError as exc:
        raise ImportError("未安装 mlx-whisper；请按 requirements.lock.txt 安装后重试。") from exc
    return mlx_whisper.transcribe(samples, path_or_hf_repo=local_asr_model(model), language="zh",
                                  task="transcribe", verbose=False, condition_on_previous_text=False)


def _faster_whisper(samples, model, device):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ImportError("未安装 faster-whisper；请按 requirements.lock.txt 安装后重试。") from exc
    device = str(device or "cpu").strip().lower()
    if device not in ("cpu", "cuda", "auto"):
        raise ValueError("asr_device 只能是 cpu、cuda 或 auto。")
    compute_type = {"cpu": "int8", "cuda": "float16"}.get(device, "auto")
    key = (model, device, compute_type)
    engine = _ENGINES.get(key)
    if engine is None:
        engine = WhisperModel(local_asr_model(model), device=device, compute_type=compute_type)
        _ENGINES[key] = engine
    segments, info = engine.transcribe(samples, language="zh", task="transcribe",
                                       condition_on_previous_text=False)
    rows = [{"start": float(segment.start), "end": float(segment.end), "text": segment.text}
            for segment in segments]
    return {"text": "".join(row["text"] for row in rows).strip(), "segments": rows,
            "language": getattr(info, "language", None) or "zh"}