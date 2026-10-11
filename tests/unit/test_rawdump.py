# Copyright 2026 CHIRP contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import unittest
import zlib

import wx.lib.newevent  # noqa: F401  (modules under test rely on wx.lib)

from mychirp import directory
from mychirp.wxui import common


class TestRawMemoryDump(unittest.TestCase):
    def _load_radio(self):
        image = os.path.join(os.path.dirname(__file__),
                             '..', 'images', 'Baofeng_UV-5R.img')
        return directory.get_radio_by_image(image), image

    def test_dump(self):
        """The dump must be byte-identical to the loaded memory image,
        carry a verifiable CRC32, and clearly state it is not
        firmware."""
        radio, image = self._load_radio()
        expected = radio.get_mmap().get_packed()

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            binpath = os.path.join(tmpdir, 'dump.bin')
            size, crc = common.write_raw_memory_dump(radio, binpath)
            with open(binpath, 'rb') as f:
                data = f.read()
            self.assertEqual(len(expected), len(data))
            self.assertEqual(expected, data)
            self.assertEqual(zlib.crc32(data) & 0xFFFFFFFF, crc)
            # Companion hexdump must exist and label the content
            # honestly
            with open(binpath + '.txt', encoding='utf-8') as f:
                text = f.read()
            self.assertIn('not firmware', text)
            self.assertIn('%08X' % crc, text)
            self.assertIn(radio.MODEL, text)


if __name__ == '__main__':
    unittest.main()
