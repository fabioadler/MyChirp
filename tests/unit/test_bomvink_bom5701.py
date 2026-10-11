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
        self.write_busy = False
        self.s_commands = []
        self.w_commands = []
        self.accepted_writes = []
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

        if len(self.wbuf) >= 4 and self.wbuf[0:1] == b'X':
            # An X write frame: 1 cmd + 2 addr + 1 size + data
            _cmd, addr, size = struct.unpack('>BHB', self.wbuf[0:4])
            if len(self.wbuf) >= 4 + size:
                data = self.wbuf[4:4 + size]
                self.wbuf = b''
                self.w_commands.append((addr, size, data))
                if self.session_over:
                    return  # silence after the session ended
                if self.write_busy:
                    # Observed on the real radio: the write issued right
                    # after an accepted one is NACKed while the radio
                    # commits; the retry is then accepted
                    self.write_busy = False
                    return  # no ack
                self._queue(b'\x06')
                self.write_busy = True
                self.accepted_writes.append((addr, size, data))
                if addr < 0x1800 and addr + size >= 0x1800:
                    # The last main block ends the clone session,
                    # mirroring the download behavior
                    self.session_over = True
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

    def test_upload_roundtrip_and_order(self):
        """Upload writes the aux block BEFORE the main block (the radio
        ends the session after the main block), retries the NACK that
        the radio gives after every accepted write, transfers the
        image faithfully, and never touches the unmapped 0x1E80
        region."""
        radio, _pipe = self._download(uv5r.BOMVINKBOM5701)
        fresh = FakeBOM5701Serial()
        radio.pipe = fresh
        with mock.patch('time.sleep'):
            radio.sync_out()

        accepted = fresh.accepted_writes
        addrs = [addr for addr, size, data in accepted]
        first_main = next(i for i, a in enumerate(addrs) if a < 0x1800)
        # All aux writes happen first, over exactly the image-mapped
        # range 0x1EC0-0x2000
        self.assertEqual(list(range(0x1EC0, 0x2000, 0x10)),
                         addrs[:first_main])
        # The unmapped 0x1E80-0x1EC0 area must never be written
        self.assertNotIn(0x1E80, addrs)
        # Main writes cover the standard upload ranges
        expected_main = []
        for start, end in [(0x0008, 0x0CF8), (0x0D08, 0x0DF8),
                           (0x0E08, 0x1808)]:
            expected_main += [i - 0x08 for i in range(start, end, 0x10)]
        self.assertEqual(expected_main, addrs[first_main:])
        # The radio NACKs the write after every accepted one: each block
        # must have needed its retry (except the very first)
        attempts = {}
        for addr, size, data in fresh.w_commands:
            attempts[addr] = attempts.get(addr, 0) + 1
        self.assertEqual(1, attempts[addrs[0]])
        for addr in addrs[1:]:
            self.assertEqual(2, attempts[addr],
                             'block 0x%04x should have taken one NACK '
                             'plus one retry' % addr)
        # Every transferred block matches the image byte for byte
        image = radio.get_mmap().get_packed()
        self.assertEqual(0x1948, len(image))
        for addr, size, data in accepted:
            if addr >= 0x1EC0:
                img_addr = 0x1808 + addr - 0x1EC0
            else:
                img_addr = addr + 0x08
            self.assertEqual(image[img_addr:img_addr + size], data)

    def test_generic_uv5r_upload_fails(self):
        """The stock UV-5R upload path writes main first and carries no
        retry: with this radio, which NACKs the write issued right
        after an accepted one, the stock driver dies on the second main
        block. This documents why the aux-first family with
        retry-on-NACK exists (and why the stock full-range aux list,
        which starts at the image-unmapped 0x1E80, must not be used
        with these radios)."""
        bom = uv5r.BOMVINKBOM5701(None)
        bom.pipe = FakeBOM5701Serial()
        with mock.patch('time.sleep'):
            bom.sync_in()
        image = bom.get_mmap().get_packed()
        with tempfile.NamedTemporaryFile(suffix='.img',
                                         delete=False) as f:
            f.write(image)
            path = f.name
        try:
            radio = uv5r.BaofengUV5RGeneric(path)
            fresh = FakeBOM5701Serial()
            radio.pipe = fresh
            with mock.patch('time.sleep'):
                with self.assertRaises(errors.RadioError) as ctx:
                    radio.sync_out()
        finally:
            os.unlink(path)
        addrs = [addr for addr, size, data in fresh.w_commands]
        # The stock driver wrote the first main block fine...
        self.assertTrue(any(a < 0x1800 for a in addrs))
        # ...and then failed without a retry mechanism
        self.assertIn('refused to accept', str(ctx.exception))

    def test_download_full_window(self):
        """The full-window live read returns the complete 8 KiB the
        cable can see, reading the calibration gap and aux BEFORE the
        main block (which ends the session)."""
        radio = uv5r.BOMVINKBOM5701(None)
        pipe = FakeBOM5701Serial()
        radio.pipe = pipe
        seen = []
        with mock.patch('time.sleep'):
            data = radio.download_full_window(status_fn=seen.append)
        self.assertEqual(0x2000, len(data))
        addrs = [a for a, s in pipe.s_commands]
        # Warm-up block first (no ACK expected on the first command)
        self.assertEqual(0x1E80, addrs[0])
        first_main = next(i for i, a in enumerate(addrs) if a < 0x1800)
        # Gap + aux are all read before the main block
        self.assertEqual(sorted(range(0x1800, 0x2000, 0x40)),
                         sorted(addrs[1:first_main]))
        # Main block covers its full range
        self.assertEqual(sorted(range(0x0000, 0x1800, 0x40)),
                         sorted(addrs[first_main:]))
        # Content: main region, FF filler in the gap, real aux
        self.assertEqual(_build_main(), data[0x0000:0x1800])
        self.assertEqual(b'\xff' * 0x6C0, data[0x1800:0x1EC0])
        self.assertEqual(_build_aux(), data[0x1EC0:0x2000])
        # Progress reported once per block (128 blocks total)
        self.assertEqual(128, len(seen))

    def test_registered_models(self):
        """All owner-verified additions are registered as proper,
        separate models with documented hardware."""
        from chirp.drivers import h777
        bom = uv5r.BOMVINKBOM5701(None)
        self.assertEqual('BOMVINK', bom.VENDOR)
        self.assertEqual('BOM-5701', bom.MODEL)
        # The radio presents channels 000-126 (127 channels)
        self.assertEqual((0, 126), bom.get_features().memory_bounds)
        for rclass in (uv5r.BOMVINKBOM5701,
                       h777.BaofengBF777SRadio,
                       h777.IntelbrasRC3002G2Radio):
            self.assertEqual([], rclass.ALIASES)
            self.assertIn('two-pin', rclass.HARDWARE_REQUIREMENTS)
        self.assertEqual('Baofeng', h777.BaofengBF777SRadio.VENDOR)
        self.assertEqual('BF-777S', h777.BaofengBF777SRadio.MODEL)
        self.assertEqual('Intelbras', h777.IntelbrasRC3002G2Radio.VENDOR)
        self.assertEqual('RC 3002 G2', h777.IntelbrasRC3002G2Radio.MODEL)
        # The BF-888-family additions expose the same 16 channels as
        # the BF-888 they were verified against
        for rclass in (h777.BaofengBF777SRadio,
                       h777.IntelbrasRC3002G2Radio):
            self.assertEqual((1, 16),
                             rclass(None).get_features().memory_bounds)

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
