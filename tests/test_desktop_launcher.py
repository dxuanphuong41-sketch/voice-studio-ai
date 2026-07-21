from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import desktop_launcher


class DesktopLauncherTests(unittest.TestCase):
    def test_native_app_components_work_without_console_streams(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.dict("os.environ", {"VOICE_STUDIO_DATA_DIR": temp_dir}),
                patch.object(sys, "stdout", None),
                patch.object(sys, "stderr", None),
            ):
                desktop_launcher.ensure_console_streams()
                output_dir = desktop_launcher.output_directory()

                self.assertIsNotNone(sys.stdout)
                self.assertIsNotNone(sys.stderr)
                self.assertTrue(output_dir.is_dir())
                self.assertEqual(len(desktop_launcher.VOICE_OPTIONS), 30)
                self.assertTrue(desktop_launcher.ffmpeg_executable())
                for stream in desktop_launcher._NULL_STREAMS:
                    stream.close()
                desktop_launcher._NULL_STREAMS.clear()


if __name__ == "__main__":
    unittest.main()
