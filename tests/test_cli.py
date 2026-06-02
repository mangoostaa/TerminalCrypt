from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from terminalcrypt.cli import main


class CliTests(unittest.TestCase):
    def test_version_flag_prints_package_version(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["terminalcrypt", "--version"]):
            with self.assertRaises(SystemExit) as raised:
                with redirect_stdout(output):
                    main()

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("terminalcrypt 3.2.0", output.getvalue())

    def test_once_export_flags_are_passed_to_app(self):
        with patch("terminalcrypt.cli.CryptexApp") as app_cls:
            app = app_cls.return_value
            with patch.object(
                sys,
                "argv",
                [
                    "terminalcrypt",
                    "--once",
                    "--format",
                    "json",
                    "--output",
                    "snapshot.json",
                    "--symbols",
                    "btc,eth",
                ],
            ):
                main()

        app.run_once.assert_called_once_with(
            "binance",
            output_format="json",
            output_path="snapshot.json",
            symbols=["BTC", "ETH"],
        )


if __name__ == "__main__":
    unittest.main()
