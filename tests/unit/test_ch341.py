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

"""Unit tests for the CH341A programmer module (simulated USB)."""

import unittest
from unittest import mock

from chirp.hardware import ch341


class FakeCH341Device:
    """Simulates a CH341A with a 24Cxx EEPROM and a 25xx SPI flash.

    Implements the same write/read interface pyusb devices expose,
    so the real driver code runs unmodified against it.
    """

    def __init__(self, eeprom=None, flash=None, jedec=b'\xef\x40\x15',
                 idVendor=0x1A86, idProduct=0x5512):
        self.eeprom = eeprom if eeprom is not None else bytes(
            (i * 7 + 3) & 0xFF for i in range(32768))
        self.flash = flash if flash is not None else bytes(
            (i * 13 + 5) & 0xFF for i in range(4096))
        self.jedec = jedec
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.writes = []
        self.in_queue = bytearray()
        self.spi_state = None
        self.configuration_set = False

    # pyusb device interface -------------------------------------------
    def is_kernel_driver_active(self, interface):
        return False

    def detach_kernel_driver(self, interface):
        pass

    def attach_kernel_driver(self, interface):
        pass

    def set_configuration(self):
        self.configuration_set = True

    def write(self, endpoint, data, timeout):
        assert endpoint == ch341.WRITE_ENDPOINT
        data = bytes(data)
        self.writes.append(data)
        for i in range(0, len(data), ch341.PACKET_LENGTH):
            self._packet(data[i:i + ch341.PACKET_LENGTH])

    def read(self, endpoint, size, timeout):
        assert endpoint == ch341.READ_ENDPOINT
        out = bytes(self.in_queue[:size])
        self.in_queue = self.in_queue[size:]
        return out

    # device behavior ----------------------------------------------------
    def _packet(self, pkt):
        if pkt[0] == ch341.I2C_STREAM:
            if ch341.I2C_STM_IN | 0x20 in pkt:
                # our sequential-read command: [AA 74 OUT A0 [addr]
                # 74 81 A1 E0 ...]
                addr_bytes = (pkt[2] & 0x0F) - 1
                if addr_bytes == 2:
                    addr = (pkt[4] << 8) | pkt[5]
                else:
                    addr = pkt[4]
                block = self.eeprom[addr:addr + 0x20]
                block += bytes(0x20 - len(block))
                self.in_queue += block
            else:
                # speed set and other commands: status response
                self.in_queue += bytes(ch341.PACKET_LENGTH)
        elif pkt[0] == ch341.UIO_STREAM:
            # CS handling starts a new SPI transaction
            self.spi_state = {'cmd': None, 'addr_bytes': [], 'pos': 0}
        elif pkt[0] == ch341.SPI_STREAM:
            state = self.spi_state
            out = bytearray()
            for raw in pkt[1:ch341.PACKET_LENGTH]:
                byte = ch341.reverse_byte(raw)
                out.append(self._spi_step(byte, state))
            self.in_queue += bytes(
                ch341.reverse_byte(b) for b in out)

    def _spi_step(self, byte, state):
        """One SPI clock byte: return what MISO shifts out."""
        if state['cmd'] is None:
            state['cmd'] = byte
            return 0xFF
        if state['cmd'] == 0x9F:
            pos = state['pos']
            state['pos'] += 1
            if pos < 3:
                return self.jedec[pos]
            return 0xFF
        if state['cmd'] == 0x03:
            if len(state['addr_bytes']) < 3:
                state['addr_bytes'].append(byte)
                return 0xFF
            addr = (state['addr_bytes'][0] << 16) | \
                (state['addr_bytes'][1] << 8) | state['addr_bytes'][2]
            addr += state['pos']
            state['pos'] += 1
            if addr < len(self.flash):
                return self.flash[addr]
            return 0xFF
        return 0xFF


def _fake_find(devices):
    def finder(find_all=False, custom_match=None, **kwargs):
        found = devices
        if custom_match:
            found = [d for d in found if custom_match(d)]
        if find_all:
            return found
        return found[0] if found else None
    return finder


class TestCH341(unittest.TestCase):
    def _programmer(self, **kwargs):
        dev = FakeCH341Device(**kwargs)
        prog = ch341.CH341A(dev)
        prog.open()
        return prog, dev

    def test_find_programmers_filters_by_usb_id(self):
        devices = [FakeCH341Device(),
                   FakeCH341Device(idVendor=0x1234, idProduct=0x5678)]
        with mock.patch('usb.core.find', side_effect=_fake_find(devices)):
            found = ch341.find_programmers()
        self.assertEqual(1, len(found))
        self.assertEqual(0x1A86, found[0].idVendor)

    def test_read_only_module(self):
        """The module must not expose any chip-writing entry point."""
        prog, dev = self._programmer()
        self.assertFalse(hasattr(prog, 'i2c_write_eeprom'))
        self.assertFalse(hasattr(prog, 'spi_write_flash'))
        self.assertFalse(hasattr(prog, 'write_chip'))
        prog.close()

    def test_i2c_read_24c64(self):
        prog, dev = self._programmer()
        try:
            data = prog.i2c_read_eeprom(8192, addr_bytes=2)
        finally:
            prog.close()
        self.assertEqual(8192, len(data))
        self.assertEqual(dev.eeprom[:8192], data)
        # First write is the speed-set, then one 32-byte command per
        # block with the device address and 16-bit address in place
        self.assertEqual(bytes([0xAA, 0x61, 0x00]), dev.writes[0])
        pkt = dev.writes[1]
        self.assertEqual(32, len(pkt))
        self.assertEqual(0xA0, pkt[3])
        self.assertEqual((0x00, 0x00), (pkt[4], pkt[5]))
        # Block commands carry the aligned block start address
        mid = dev.writes[1 + 0x1200 // 32]
        self.assertEqual((0x12, 0x00), (mid[4], mid[5]))

    def test_i2c_read_24c02_one_byte_addressing(self):
        prog, dev = self._programmer()
        try:
            data = prog.i2c_read_eeprom(256, addr_bytes=1)
        finally:
            prog.close()
        self.assertEqual(256, len(data))
        self.assertEqual(dev.eeprom[:256], data)
        pkt = dev.writes[1]
        # OUT 2 = device address + one address byte
        self.assertEqual(0x82, pkt[2])
        self.assertEqual(0xA0, pkt[3])

    def test_jedec_id(self):
        prog, dev = self._programmer(jedec=b'\xef\x40\x15')
        try:
            prog.spi_enable()
            ident = prog.jedec_id()
        finally:
            prog.close()
        self.assertEqual(b'\xef\x40\x15', ident)
        name, size = ch341.describe_jedec(ident)
        self.assertIn('Winbond', name)
        self.assertEqual(2 * 1024 * 1024, size)

    def test_describe_jedec_unknown(self):
        name, size = ch341.describe_jedec(b'\xde\xad\xa5')
        self.assertIsNone(size)

    def test_spi_read_flash(self):
        prog, dev = self._programmer()
        try:
            prog.spi_enable()
            data = prog.spi_read_flash(4096)
            transactions = list(dev.writes)
        finally:
            prog.close()
        self.assertEqual(4096, len(data))
        self.assertEqual(dev.flash, data)
        # writes[0] is the enable packet; each transaction is a single
        # write containing the CS UIO packet followed by SPI packets
        self.assertEqual(ch341.UIO_STREAM, transactions[0][0])
        first = transactions[1]
        self.assertEqual(ch341.UIO_STREAM, first[0])
        self.assertEqual(ch341.UIO_STM_OUT | ch341.SPI_CS_LOW,
                         first[4])
        self.assertEqual(ch341.SPI_STREAM, first[32])

    def test_reverse_byte(self):
        self.assertEqual(0x80, ch341.reverse_byte(0x01))
        self.assertEqual(0x01, ch341.reverse_byte(0x80))
        self.assertEqual(0xFF, ch341.reverse_byte(0xFF))
        self.assertEqual(0x55, ch341.reverse_byte(0xAA))
        # double reversal is identity
        for value in (0x00, 0x5A, 0xF0, 0x0F):
            self.assertEqual(value,
                             ch341.reverse_byte(ch341.reverse_byte(value)))


if __name__ == '__main__':
    unittest.main()
