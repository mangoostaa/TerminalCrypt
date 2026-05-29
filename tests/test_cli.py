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


if __name__ == "__main__":
    unittest.main()
