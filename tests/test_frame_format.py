"""Offline regression coverage for the real RGB-PNG display corruption."""
import io
from pathlib import Path
import sys
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from turzx_usb import TurzxWinUSB


class NativeFrameFormatTests(unittest.TestCase):
    def png(self, mode, size=(720, 1280)):
        buffer = io.BytesIO()
        Image.new(mode, size).save(buffer, "PNG")
        return buffer.getvalue()

    def test_rgb_png_is_rejected_before_usb(self):
        # The unit ACKs these but visibly repeats strips over the old image.
        with self.assertRaisesRegex(ValueError, "RGBA"):
            TurzxWinUSB._check_image(self.png("RGB"), "PNG")

    def test_rgba_png_accepts_both_opaque_frame_and_transparent_clear(self):
        for alpha in (0, 255):
            image = Image.new("RGBA", (720, 1280), (20, 25, 30, alpha))
            buffer = io.BytesIO()
            image.save(buffer, "PNG", compress_level=1)
            self.assertEqual(buffer.getvalue()[25], 6)  # PNG IHDR colour type.
            TurzxWinUSB._check_image(buffer.getvalue(), "PNG")

    def test_landscape_must_be_rotated_before_transfer(self):
        with self.assertRaisesRegex(ValueError, "720x1280"):
            TurzxWinUSB._check_image(self.png("RGBA", (1280, 720)), "PNG")


if __name__ == "__main__":
    unittest.main()
