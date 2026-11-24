import unittest
from unittest.mock import patch
import fastdl

class PreflightTests(unittest.TestCase):
    def test_drm(self):
        with self.assertRaisesRegex(ValueError, "DRM"):
            fastdl.inspect_media({"formats": [{"has_drm": True, "url": "https://example.invalid"}]})

    def test_paid(self):
        with self.assertRaisesRegex(ValueError, "Restricted"):
            fastdl.inspect_media({"availability": "premium_only"})

    def test_formats(self):
        self.assertEqual(fastdl.inspect_media({"formats": [
            {"height": 720, "url": "https://example.invalid"},
            {"height": 1080, "url": "https://example.invalid"},
            {"height": 2160, "has_drm": True, "url": "https://example.invalid"}
        ]}), [720, 1080])

    def test_missing_formats(self):
        with self.assertRaisesRegex(ValueError, "No downloadable"):
            fastdl.inspect_media({})

    def test_runtime(self):
        with patch("fastdl.tool", return_value="deno.exe"):
            self.assertEqual(fastdl.runtime_options()["js_runtimes"]["deno"]["path"], "deno.exe")

if __name__ == "__main__":
    unittest.main()
