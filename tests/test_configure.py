import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import helpers
import batch_notice
import configure


class ConfigureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "a skill's directory"
        self.root.mkdir()
        source = Path(__file__).resolve().parents[1]
        shutil.copyfile(source / "config.example.json", self.root / "config.example.json")
        template = self.root / "integrations/cc-connect"
        template.mkdir(parents=True)
        shutil.copyfile(source / "integrations/cc-connect/dy-author.md", template / "dy-author.md")
        self.vault = self.root / "Vault with spaces"
        self.vault.mkdir()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def args(self, **values):
        result = dict(vault=str(self.vault), no_browser=True, chrome_profile=None, chrome_cache=None,
                      cc_workspace=None, cc_binary=None, cc_data_dir=None)
        result.update(values)
        return argparse.Namespace(**result)

    def test_personal_config_and_cc_command_use_installer_paths(self):
        result = configure.configure(self.args(cc_workspace=str(self.workspace)), self.root)
        config = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["vault"], str(self.vault))
        self.assertEqual(config["material_cache_dirs"], [])
        self.assertIsNone(config["browser"])
        if os.name != "nt":
            # Windows only tracks the read-only bit, not POSIX permission bits.
            self.assertEqual((self.root / "config.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(result["skill_link"]).resolve(), self.root)
        command = Path(result["command_file"]).read_text(encoding="utf-8")
        self.assertIn((self.root / "SKILL.md").as_posix(), command)
        self.assertNotIn("@@SKILL_DIR@@", command)
        self.assertTrue(command.rstrip().endswith("DYA_RAW_ARGUMENTS_BEGIN"))
        self.assertEqual(list(self.vault.iterdir()), [])

    def test_existing_command_is_preserved_and_config_is_not_written(self):
        command = self.workspace / ".claude/commands/dy-author.md"
        command.parent.mkdir(parents=True)
        command.write_text("existing command", encoding="utf-8")
        with self.assertRaises(ValueError):
            configure.configure(self.args(cc_workspace=str(self.workspace)), self.root)
        self.assertEqual(command.read_text(encoding="utf-8"), "existing command")
        self.assertFalse((self.root / "config.json").exists())

    def test_existing_config_is_never_overwritten(self):
        configure.configure(self.args(), self.root)
        before = (self.root / "config.json").read_bytes()
        with self.assertRaises(ValueError):
            configure.configure(self.args(), self.root)
        self.assertEqual((self.root / "config.json").read_bytes(), before)

    def test_fresh_download_defaults_to_auto_profile_and_silent_mode(self):
        session = {"status": "login_required", "message": "请手动登录"}
        with patch("chrome_session.resolve_config", side_effect=lambda config: (dict(config), session)), \
             patch("subprocess.Popen") as browser:
            result = configure.configure(self.args(no_browser=False), self.root)
        config = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertIsNone(config["browser_profile"])
        self.assertIsNone(config["browser_cache_dir"])
        self.assertFalse(config["auto_browser_recovery"])
        self.assertEqual(result["browser_session"], session)
        browser.assert_not_called()

    def test_custom_profile_requires_matching_explicit_cache(self):
        profile = self.root / "custom-user-data/Profile 2"
        cache = self.root / "custom-cache/Cache_Data"
        profile.mkdir(parents=True)
        cache.mkdir(parents=True)
        with self.assertRaises(ValueError):
            configure.configure(self.args(no_browser=False, chrome_profile=str(profile)), self.root)
        self.assertFalse((self.root / "config.json").exists())
        configure.configure(self.args(no_browser=False, chrome_profile=str(profile), chrome_cache=str(cache)), self.root)
        config = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["browser_profile"], str(profile.resolve()))
        self.assertEqual(config["browser_cache_dir"], str(cache.resolve()))

    def test_notification_uses_personal_config_without_changing_session_boundary(self):
        binary = self.root / "cc-connect"
        binary.write_text("fixture, subprocess is mocked", encoding="utf-8")
        data = self.root / "cc-data"
        data.mkdir()
        report = {"batch_finished": True, "message": "已完成一批"}
        with patch.dict(os.environ, {"CC_PROJECT": "test-project", "CC_SESSION_KEY": "test-session"}, clear=True), \
             patch.object(batch_notice.subprocess, "run") as send:
            send.return_value.returncode = 0
            result = batch_notice.notify({"last_batch_ids": ["example"]}, report, lambda: None,
                                         config={"cc_binary": str(binary), "cc_data_dir": str(data)})
            self.assertEqual(result["status"], "sent")
            self.assertEqual(send.call_args.args[0], [str(binary), "send", "--project", "test-project",
                             "--session", "test-session", "--data-dir", str(data), "--stdin"])

    def test_windows_configuration_uses_faster_whisper_model(self):
        with patch.object(configure.platform, "system", return_value="Windows"), \
             patch.object(configure.platform, "machine", return_value="AMD64"):
            configure.configure(self.args(), self.root)
        config = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["asr_model"], "small")
        self.assertEqual(config["asr_backend"], "auto")
        self.assertEqual(config["ocr_backend"], "auto")

    def test_apple_silicon_keeps_mlx_model(self):
        with patch.object(configure.platform, "system", return_value="Darwin"), \
             patch.object(configure.platform, "machine", return_value="arm64"):
            configure.configure(self.args(), self.root)
        config = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["asr_model"], "mlx-community/whisper-small-mlx")

    @unittest.skipUnless(sys.platform == "win32", "junction fallback is Windows-only")
    def test_windows_skill_link_falls_back_to_junction(self):
        skill_link = self.workspace / ".claude/skills/dy-author"
        skill_link.parent.mkdir(parents=True)
        with patch.object(Path, "symlink_to", side_effect=OSError("symlink privilege denied")):
            configure.link_skill(skill_link, self.root)
        self.assertTrue(skill_link.is_dir())
        self.assertTrue(os.path.isjunction(skill_link))
        self.assertEqual(skill_link.resolve(), self.root)


if __name__ == "__main__":
    unittest.main()
