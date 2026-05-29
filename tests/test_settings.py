from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from terminalcrypt.settings import load_settings


class SettingsTests(unittest.TestCase):
    def test_loads_toml_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "terminalcrypt.toml"
            path.write_text(
                "[terminalcrypt]\n"
                "source='kraken'\n"
                "initial_view='detail'\n"
                "selected_symbol='eth'\n"
                "refresh_per_second=5\n"
                "sqlite_enabled=true\n"
                "sqlite_path='tmp/ticks.sqlite3'\n"
                "sqlite_batch_size=25\n",
                encoding="utf-8",
            )
            settings = load_settings(path)
        self.assertEqual(settings.source, "kraken")
        self.assertEqual(settings.initial_view, "detail")
        self.assertEqual(settings.selected_symbol, "ETH")
        self.assertEqual(settings.refresh_per_second, 5)
        self.assertTrue(settings.sqlite_enabled)
        self.assertEqual(settings.sqlite_path, "tmp/ticks.sqlite3")
        self.assertEqual(settings.sqlite_batch_size, 25)


if __name__ == "__main__":
    unittest.main()
