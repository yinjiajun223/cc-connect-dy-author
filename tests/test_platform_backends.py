"""Platform backend coverage: ASR/OCR selection, file locks, Windows naming and layout."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

import helpers  # noqa: F401  (sets sys.path)
import asr
import console
import doctor
import file_lock
import image_posts
import library
import ocr_backend

from PIL import Image

VID = "7659111274168454446"


class AsrBackendTests(unittest.TestCase):
    def test_auto_backend_follows_host_capabilities(self):
        with patch.object(asr.platform, "system", return_value="Darwin"), \
             patch.object(asr.platform, "machine", return_value="arm64"):
            self.assertEqual(asr.backend({}), asr.MLX)
        with patch.object(asr.platform, "system", return_value="Windows"), \
             patch.object(asr.platform, "machine", return_value="AMD64"):
            self.assertEqual(asr.backend({}), asr.FASTER_WHISPER)

    def test_explicit_backend_is_validated(self):
        self.assertEqual(asr.backend({"asr_backend": "faster_whisper"}), asr.FASTER_WHISPER)
        with self.assertRaises(ValueError):
            asr.backend({"asr_backend": "whisper.cpp"})

    def test_mlx_model_name_maps_to_faster_whisper_sizes(self):
        self.assertEqual(asr.model_name("mlx-community/whisper-small-mlx", asr.FASTER_WHISPER), "small")
        self.assertEqual(asr.model_name("mlx-community/whisper-large-v3-turbo-mlx", asr.FASTER_WHISPER),
                         "large-v3-turbo")
        self.assertEqual(asr.model_name("whisper-small", asr.FASTER_WHISPER), "small")
        self.assertEqual(asr.model_name("Systran/faster-whisper-small", asr.FASTER_WHISPER),
                         "Systran/faster-whisper-small")
        self.assertEqual(asr.model_name("mlx-community/whisper-small-mlx", asr.MLX),
                         "mlx-community/whisper-small-mlx")

    def test_faster_whisper_transcription_shape(self):
        models = []

        class Model:
            def __init__(self, path, device, compute_type):
                models.append((path, device, compute_type))

            # Explicit signature: faster-whisper has no `verbose` keyword.
            def transcribe(self, samples, language=None, task=None, condition_on_previous_text=None):
                return iter([SimpleNamespace(start=0.0, end=1.0, text=" 第一段"),
                             SimpleNamespace(start=1.0, end=2.0, text="第二段")]), SimpleNamespace(language="zh")

        module = ModuleType("faster_whisper")
        module.WhisperModel = Model
        asr._ENGINES.clear()
        self.addCleanup(asr._ENGINES.clear)
        with patch.dict(sys.modules, {"faster_whisper": module}), \
             patch.object(asr, "local_asr_model", side_effect=lambda name: name):
            result = asr.transcribe(object(), "small", asr.FASTER_WHISPER, "cpu")
        self.assertEqual(models, [("small", "cpu", "int8")])
        self.assertEqual(result["text"], "第一段第二段")
        self.assertEqual([row["text"] for row in result["segments"]], [" 第一段", "第二段"])
        self.assertEqual(result["language"], "zh")

    def test_mlx_backend_is_rejected_off_apple_silicon(self):
        with patch.object(asr.platform, "system", return_value="Windows"), \
             patch.object(asr.platform, "machine", return_value="AMD64"):
            with self.assertRaises(ValueError):
                asr.transcribe(object(), "small", asr.MLX)


class OcrBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "page.png"
        Image.new("RGB", (200, 100), "white").save(self.image)
        previous = ocr_backend._ENGINE
        ocr_backend._ENGINE = None
        self.addCleanup(setattr, ocr_backend, "_ENGINE", previous)

    def test_auto_backend_follows_host(self):
        with patch.object(ocr_backend.platform, "system", return_value="Darwin"):
            self.assertEqual(ocr_backend.backend({}), ocr_backend.VISION)
        with patch.object(ocr_backend.platform, "system", return_value="Windows"):
            self.assertEqual(ocr_backend.backend({}), ocr_backend.RAPIDOCR)
        with self.assertRaises(ValueError):
            ocr_backend.backend({"ocr_backend": "tesseract"})

    def test_rapidocr_pages_are_normalized_and_read_in_order(self):
        rows = [[[[10, 60], [120, 60], [120, 80], [10, 80]], "第二行", 0.9],
                [[[10, 10], [80, 10], [80, 30], [10, 30]], "第一行", 0.8]]
        module = ModuleType("rapidocr_onnxruntime")
        module.RapidOCR = lambda: (lambda path: (rows, [0]))
        with patch.dict(sys.modules, {"rapidocr_onnxruntime": module}):
            raw = ocr_backend.run([self.image], {"ocr_backend": "rapidocr"})
        page = raw["pages"][0]
        self.assertEqual(raw["engine"], "RapidOCR")
        self.assertEqual(page["text"], "第一行\n第二行")
        self.assertEqual((page["width"], page["height"]), (200, 100))
        self.assertAlmostEqual(page["lines"][0]["box"][0], 10 / 200)
        self.assertAlmostEqual(page["lines"][0]["box"][2], 70 / 200)

    def test_vision_reports_a_missing_toolchain(self):
        with patch.object(ocr_backend.subprocess, "run", side_effect=FileNotFoundError("xcrun")):
            with self.assertRaises(ocr_backend.OcrError):
                ocr_backend.run([self.image], {"ocr_backend": "vision"})


def image_bundle(root):
    cache = root / VID
    directory = cache / "images"
    directory.mkdir(parents=True)
    image = directory / "001.png"
    Image.new("RGB", (120, 60), "white").save(image)
    data = image.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    bundle = {"schema_version": 2, "aweme_id": VID, "source_url": f"https://www.douyin.com/note/{VID}",
              "media_kind": "image", "title": "图文示例", "caption": "", "author": "作者",
              "author_id": None, "image_count": 1,
              "images": [{"page": 1, "file": "images/001.png", "sha256": digest, "width": 120,
                          "height": 60, "original_file": "images/001.png", "original_sha256": digest}]}
    path = cache / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return path


class ImageExtractTests(unittest.TestCase):
    def test_extract_uses_the_selected_backend_and_records_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = image_bundle(root)
            calls = []

            def fake_run(paths, config):
                calls.append((paths, config))
                return {"engine": "FakeOCR", "pages": [{"page": 1, "file": paths[0], "width": 120,
                        "height": 60, "text": "第一页文字", "lines": []}]}

            with patch.object(image_posts.ocr_backend, "run", side_effect=fake_run):
                result = image_posts.extract(bundle, {"ocr_backend": "rapidocr"})
            self.assertEqual(result["status"], "extracted")
            self.assertEqual(result["pages"], 1)
            raw = json.loads((root / VID / "transcript.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["text"], "第 1 页\n第一页文字")
            self.assertEqual(raw["pages"][0]["sha256"],
                             json.loads(bundle.read_text(encoding="utf-8"))["images"][0]["sha256"])
            self.assertEqual(calls[0][1], {"ocr_backend": "rapidocr"})

    def test_extract_wraps_backend_errors_as_stage_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = image_bundle(Path(folder))
            with patch.object(image_posts.ocr_backend, "run",
                              side_effect=image_posts.ocr_backend.OcrError("缺少本地 OCR")):
                with self.assertRaises(image_posts.StageError) as error:
                    image_posts.extract(bundle, {})
            self.assertEqual(error.exception.stage, "ocr")


class LibraryPlatformTests(unittest.TestCase):
    def test_windows_reserved_titles_get_importable_slugs(self):
        self.assertEqual(library.slug("CON"), "CON-")
        self.assertEqual(library.slug("nul"), "nul-")
        self.assertEqual(library.slug("COM3"), "COM3-")
        self.assertEqual(library.slug("console"), "console")

    def test_exclusive_write_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            library.atomic_write(path, b"first", exclusive=True)
            with self.assertRaises(OSError):
                library.atomic_write(path, b"second", exclusive=True)
            self.assertEqual(path.read_bytes(), b"first")

    def test_file_lock_releases_between_acquisitions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "run.lock"
            for _ in range(2):
                with path.open("a") as handle:
                    file_lock.lock(handle)
                    file_lock.unlock(handle)


class DoctorPlatformTests(unittest.TestCase):
    def test_supported_platform_labels(self):
        with patch.object(doctor.platform, "system", return_value="Windows"), \
             patch.object(doctor.platform, "machine", return_value="AMD64"):
            self.assertEqual(doctor.platform_support(), (True, "Windows AMD64"))
        with patch.object(doctor.platform, "system", return_value="Darwin"), \
             patch.object(doctor.platform, "machine", return_value="arm64"):
            self.assertEqual(doctor.platform_support(), (True, "macOS arm64"))

    def test_unsupported_platform_is_reported(self):
        with patch.object(doctor.platform, "system", return_value="Linux"), \
             patch.object(doctor.platform, "machine", return_value="x86_64"):
            supported, label = doctor.platform_support()
        self.assertFalse(supported)
        self.assertIn("Linux", label)


class ConsoleEncodingTests(unittest.TestCase):
    """Chinese JSON on stdout must not depend on the host's regional code page."""

    ENTRY_POINTS = ("author_works.py", "backfill_authors.py", "configure.py", "doctor.py",
                    "dy_author.py", "pipeline.py")

    def test_force_utf8_reconfigures_text_streams(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
        with patch.object(console.sys, "stdout", stream), \
             patch.object(console.sys, "stderr", stream):
            console.force_utf8()
        self.assertEqual(stream.encoding.lower().replace("-", ""), "utf8")

    def test_streams_without_reconfigure_are_left_alone(self):
        with patch.object(console.sys, "stdout", io.StringIO()), \
             patch.object(console.sys, "stderr", io.StringIO()):
            console.force_utf8()

    def test_every_entry_point_forces_utf8(self):
        for name in self.ENTRY_POINTS:
            with self.subTest(entry=name):
                source = (helpers.SCRIPTS / name).read_text(encoding="utf-8")
                self.assertIn("import console", source)
                self.assertIn("console.force_utf8()", source)

    def test_chinese_stdout_is_utf8_under_a_gbk_code_page(self):
        program = ("import sys; sys.path.insert(0, sys.argv[1]);"
                   "import console; console.force_utf8();"
                   "print('请先运行 scripts/configure.py')")
        env = {**os.environ, "PYTHONIOENCODING": "gbk"}
        done = subprocess.run([sys.executable, "-B", "-c", program, str(helpers.SCRIPTS)],
                              capture_output=True, env=env, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(done.stdout.decode("utf-8").strip(), "请先运行 scripts/configure.py")


if __name__ == "__main__":
    unittest.main()