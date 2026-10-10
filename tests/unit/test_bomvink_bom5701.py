# Copyright 2026 BOMVINK BOM-5701 contributors
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
import struct
import tempfile
import unittest
from unittest import mock

from chirp import directory
from chirp import errors
from chirp.drivers import uv5r

IDENT = b'\xaa\x30\x76\x04\x00\x05\x20\xdd'

# First two memories observed in a real BOM-5701 serial trace download
# (little-endian BCD: 146.520 MHz and 462.15250 MHz).
MEM0 = (b'\x00\x20\x65\x14\x00\x20\x65\x14'
        b'\x00\x00\x00\x00\x00\x00\x00\x40')
MEM1 = (b'\x00\x25\x21\x46\x00\x25\x21\x46'
        b'\xb5\x02\xb5\x02\x00\x00\x00\x40')

# Block at radio address 0x1FC0 as observed in the real trace; byte 15
# (0x1FCF) is 0x00, meaning the radio does NOT have the dropped byte
# issue.
BLOCK_1FC0 = (b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'
              b'\x00\x00\x1a\x00\x03\xc1\x01\x00\x01\xff\x03\x6f\x03\xc1'
              b'\x00\x00\x00\x00' + b'\x00' * 32)


def _build_main():
    """Simulate a plausible UV-5R main block with two programmed memories"""
    main = bytearray(b'\xff' * 0x1800)
    main[0x0000:0x0010] = MEM0
    main[0x0010:0x0020] = MEM1
    return bytes(main)


def _build_aux(dropped_byte=False):
    """Simulate the BOM-5701 aux area with a blank version string"""
    blocks = {
        0x1EC0: b'\xff' * 0x40,  # includes blank firmware version at 0x1EF0
        0x1F00: b'\xff' * 0x40,
        0x1F40: b'\xff' * 0x40,
        0x1F80: b'\xff' * 0x40,
        0x1FC0: BLOCK_1FC0,
    }
    if dropped_byte:
        # Radios with the dropped byte issue report 0xFF at 0x1FCF
        b = bytearray(BLOCK_1FC0)
        b[15] = 0xFF
        blocks[0x1FC0] = bytes(b)
    aux = b''
    for addr in sorted(blocks):
        aux += blocks[addr]
    return aux


class FakeBOM5701Serial:
    """Behaves like a serial port with a BOMVINK BOM-5701 attached.

    Mirrors the behavior observed in a real serial trace of the radio:
      * responds to both UV-5R magics with ACK + ident
      * does NOT ack the very first block request of a session
      * acks every other block request before sending the X frame
      * ends the clone session once the main block (0x0000-0x1800) has
        been read, staying silent until power-cycled
      * optionally goes silent at an arbitrary main block address
    """

    def __init__(self, silent_after_main=True, silent_at=None):
        self.main = _build_main()
        self.aux = _build_aux()
        self.silent_after_main = silent_after_main
        self.silent_at = silent_at
        self.readbuf = b''
        self.wbuf = b''
        self.session_over = False
        self.first_s_command = True
        self.pending_secondack = False
        self.s_commands = []
        self.timeout = 1

    def _queue(self, data):
        self.readbuf += data

    def write(self, data):
        self.wbuf += data

        for magic in (uv5r.UV5R_MODEL_291, uv5r.UV5R_MODEL_ORIG):
            if self.wbuf == magic:
                self.wbuf = b''
                if not self.session_over:
                    self._queue(b'\x06')
                return

        if self.wbuf == b'\x02':
            self.wbuf = b''
            if not self.session_over:
                self._queue(IDENT)
                # The radio acks CHIRP's ack of the ident (observed in the
                # real trace), but not the per-block acks
                self.pending_secondack = True
            return

        if self.wbuf == b'\x06':
            self.wbuf = b''
            if self.pending_secondack and not self.session_over:
                self.pending_secondack = False
                self._queue(b'\x06')
            return

        if len(self.wbuf) == 4 and self.wbuf[0:1] == b'S':
            cmd, addr, size = struct.unpack('>BHB', self.wbuf)
            self.wbuf = b''
            self.s_commands.append((addr, size))
            if self.session_over:
                # The radio has left clone mode; no response at all
                return
            if self.silent_at is not None and addr >= self.silent_at:
                self.session_over = True
                return
            if addr == 0x1E80:
                # Warm-up block below the aux area, observed as 0xFF
                chunk = b'\xff' * size
            elif addr < 0x1800:
                chunk = self.main[addr:addr + size]
                if addr + size >= 0x1800 and self.silent_after_main:
                    self.session_over = True
            elif addr >= 0x1EC0:
                chunk = self.aux[addr - 0x1EC0:addr - 0x1EC0 + size]
            else:
                chunk = b'\xff' * size
            if not self.first_s_command:
                self._queue(b'\x06')
            self.first_s_command = False
            self._queue(b'X' + struct.pack('>HB', addr, size) + chunk)
            return

    def read(self, n):
        data, self.readbuf = self.readbuf[:n], self.readbuf[n:]
        return data


class BOMVINKBOM5701Test(unittest.TestCase):
    def _download(self, rclass, **kwargs):
        pipe = FakeBOM5701Serial(**kwargs)
        radio = rclass(None)
        radio.pipe = pipe
        with mock.patch('time.sleep'):
            radio.sync_in()
        return radio, pipe

    def test_download_order_and_image(self):
        """The BOM-5701 download must read the aux block BEFORE the main
        block, and produce a standard 0x1948-byte UV-5R image."""
        radio, pipe = self._download(uv5r.BOMVINKBOM5701)

        self.assertEqual(0x1948, len(radio._mmap.get_packed()))
        self.assertEqual(IDENT, radio._mmap.get_packed()[0:8])
        self.assertEqual(_build_main(),
                         radio._mmap.get_packed()[8:8 + 0x1800])
        self.assertEqual(_build_aux(),
                         radio._mmap.get_packed()[8 + 0x1800:0x1948])

        # All aux requests must happen before the first main block request
        addresses = [addr for addr, size in pipe.s_commands]
        first_main = addresses.index(0x0000)
        for aux_addr in (0x1E80, 0x1EC0, 0x1F00, 0x1F40, 0x1F80, 0x1FC0):
            self.assertIn(aux_addr, addresses[:first_main])
        # The main block must be read completely
        self.assertEqual(list(range(0x0000, 0x1800, 0x40)),
                         addresses[first_main:])
        # No dropped-byte workaround expected for this radio
        sizes = {size for addr, size in pipe.s_commands}
        self.assertEqual({0x40}, sizes)

    def test_download_dropped_byte_variant(self):
        """A dropped-byte radio still downloads with 0x10 blocks at the
        end of the aux area, aux-first."""
        pipe = FakeBOM5701Serial()
        pipe.aux = _build_aux(dropped_byte=True)
        radio = uv5r.BOMVINKBOM5701(None)
        radio.pipe = pipe
        with mock.patch('time.sleep'):
            radio.sync_in()

        self.assertEqual(0x1948, len(radio._mmap.get_packed()))
        addresses = [addr for addr, size in pipe.s_commands]
        first_main = addresses.index(0x0000)
        self.assertIn(0x1FD0, addresses[:first_main])
        self.assertIn(0x1FF0, addresses[:first_main])

    def test_memories_decode(self):
        """The downloaded image decodes the observed channels."""
        radio, pipe = self._download(uv5r.BOMVINKBOM5701)
        mem = radio.get_memory(0)
        self.assertEqual(146520000, mem.freq)
        self.assertEqual('', mem.duplex)
        mem = radio.get_memory(1)
        self.assertEqual(462125000, mem.freq)

    def test_generic_uv5r_download_fails(self):
        """The stock UV-5R driver still fails against this radio at the
        aux block (documenting the incompatibility, see issue #12332)."""
        radio = uv5r.BaofengUV5RGeneric(None)
        radio.pipe = FakeBOM5701Serial()
        with mock.patch('time.sleep'):
            with self.assertRaises(errors.RadioError) as ctx:
                radio.sync_in()
        self.assertIn('0x1ec0', str(ctx.exception))

    def test_upload_blocked(self):
        """Uploading must be blocked until the protocol is validated."""
        radio, pipe = self._download(uv5r.BOMVINKBOM5701)
        commands_before = len(pipe.s_commands)
        with self.assertRaises(errors.RadioError) as ctx:
            radio.sync_out()
        self.assertIn('not supported', str(ctx.exception))
        # The failed upload attempt must not have issued any new command
        self.assertEqual(commands_before, len(pipe.s_commands))

    def test_download_mid_main_silence(self):
        """A radio that goes silent mid-download must raise, never
        silently succeed."""
        radio = uv5r.BOMVINKBOM5701(None)
        radio.pipe = FakeBOM5701Serial(silent_at=0x0800)
        with mock.patch('time.sleep'):
            with self.assertRaises(errors.RadioError):
                radio.sync_in()

    def test_no_contact(self):
        """A radio that never answers must raise a contact error."""
        radio = uv5r.BOMVINKBOM5701(None)
        radio.pipe = FakeBOM5701Serial(silent_after_main=True)
        radio.pipe.session_over = True
        with mock.patch('time.sleep'):
            with self.assertRaises(errors.RadioError):
                radio.sync_in()

    def test_match_model(self):
        """Images from a BOM-5701 (blank version string) are detected,
        genuine UV-5R images are not."""
        image = IDENT + _build_main() + _build_aux()
        self.assertTrue(uv5r.BOMVINKBOM5701.match_model(image, None))

        # A genuine UV-5R with a real version string must not match
        genuine = bytearray(image)
        genuine[0x1838:0x183E] = b'BFB297'
        self.assertFalse(uv5r.BOMVINKBOM5701.match_model(bytes(genuine), None))

        # Wrong sizes must not match
        self.assertFalse(
            uv5r.BOMVINKBOM5701.match_model(b'\xff' * 0x1808, None))
        self.assertFalse(uv5r.BOMVINKBOM5701.match_model(b'', None))

    def test_directory_detect(self):
        """A raw BOM-5701 image (no metadata) is detected by the
        directory as this model."""
        image = IDENT + _build_main() + _build_aux()
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, 'BOM-5701.img')
            with open(fname, 'wb') as f:
                f.write(image)
            rclass = directory.get_radio_by_image(fname)
            self.assertEqual('BOMVINK', rclass.VENDOR)
            self.assertEqual('BOM-5701', rclass.MODEL)


if __name__ == '__main__':
    unittest.main()
