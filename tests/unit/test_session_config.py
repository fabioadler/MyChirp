import os
import shutil
import tempfile

from mychirp.config import ChirpConfig
from tests.unit import base


class TestSessionPersistence(base.BaseTest):
    """Session persistence keys (theme, open radios, clone selections).

    Uses a throwaway ChirpConfig in a temp dir so the real user config
    in ~/.chirp/ is never touched by the tests.
    """

    def setUp(self):
        super().setUp()
        self.tempdir = tempfile.mkdtemp()
        self.conf = ChirpConfig(self.tempdir)

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)

    # ----- helpers -----
    def _set(self, key, value):
        self.conf.set(key, value, "state")
        self.conf.save()

    def _get(self, key):
        # Re-read from disk to prove persistence
        fresh = ChirpConfig(self.tempdir)
        return fresh.get(key, "state")

    # ----- theme -----
    def test_theme_mode_persists_across_restart(self):
        for mode in ("light", "dark", "system"):
            self._set("theme_mode", mode)
            self.assertEqual(self._get("theme_mode"), mode)

    def test_theme_mode_default(self):
        self.assertIsNone(self._get("theme_mode"))

    # ----- open radios (session restore) -----
    def test_last_session_roundtrip(self):
        files = "/home/user/a.img$/home/user/b.csv"
        self._set("last_session", files)
        self.assertEqual(self._get("last_session"), files)

    def test_last_session_empty_after_all_closed(self):
        self._set("last_session", "/tmp/x.img")
        self._set("last_session", "")
        self.assertEqual(self._get("last_session"), "")

    def test_restore_session_flag(self):
        self.assertIsNone(self._get("restore_session"))
        # The UI stores booleans as str(bool(value)); the proxy's
        # get_bool() reads them back case-insensitively
        self.conf.set("restore_session", str(bool(True)), "state")
        self.conf.save()
        fresh = ChirpConfig(self.tempdir)
        self.assertEqual(
            (fresh.get("restore_session", "state") or "").lower(), "true")

    # ----- clone dialog selections -----
    def test_clone_last_vendor_model_port(self):
        self._set("clone_last_vendor", "Baofeng")
        self._set("clone_last_model", "UV-5R")
        self._set("clone_last_port", "/dev/ttyUSB0")
        self.assertEqual(self._get("clone_last_vendor"), "Baofeng")
        self.assertEqual(self._get("clone_last_model"), "UV-5R")
        self.assertEqual(self._get("clone_last_port"), "/dev/ttyUSB0")

    # ----- recent files -----
    def test_recent_files_roundtrip(self):
        self._set("last_open", "/a.img$/b.img$/c.img")
        raw = self._get("last_open") or ""
        recents = [x for x in raw.split("$") if x]
        self.assertEqual(recents, ["/a.img", "/b.img", "/c.img"])
