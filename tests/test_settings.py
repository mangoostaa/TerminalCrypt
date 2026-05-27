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
                "[terminalcrypt]\nsource='kraken'\ninitial_view='detail'\nselected_symbol='eth'\nrefresh_per_second=5\n",
                encoding="utf-8",
            )
            settings = load_settings(path)
        self.assertEqual(settings.source, "kraken")
        self.assertEqual(settings.initial_view, "detail")
        self.assertEqual(settings.selected_symbol, "ETH")
        self.assertEqual(settings.refresh_per_second, 5)


if __name__ == "__main__":
    unittest.main()
