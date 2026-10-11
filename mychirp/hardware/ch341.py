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

"""CH341A USB programmer support (READ-ONLY).

The CH341A is the de-facto standard low-cost programmer used for BIOS
chips and radio boards. This module implements chip reading over its
two protocols:

- I2C EEPROMs of the 24Cxx family (the classic config/calibration
  EEPROMs found on many radio boards), and
- SPI NOR flash of the 25xx family (the typical BIOS/radio firmware
  chips), including JEDEC identification.

Every constant and framing decision below follows the two canonical
open-source implementations, fetched and reviewed during development:
flashrom's programmers/ch341a_spi.c (SPI part, GPL-2.0+) and the
ch341eepromtool project (I2C 24Cxx part, GPL-2.0+). Nothing was
invented; the provenance is recorded in PLAN.md.

This module never issues chip WRITE commands: it is a reading tool.
Real UV-EPROMs (which need a programming voltage, Vpp) are NOT
supported by the CH341A at all and are reported as unsupported.
"""

import logging

import usb
import usb.core

LOG = logging.getLogger(__name__)

# USB identifiers and endpoints (both references agree)
CH341A_VID = 0x1A86
CH341A_PID = 0x5512
WRITE_ENDPOINT = 0x02
READ_ENDPOINT = 0x82
PACKET_LENGTH = 32
USB_TIMEOUT = 1000

# I2C stream commands (ch341eepromtool ch341eeprom.h)
I2C_STREAM = 0xAA
I2C_STM_STA = 0x74
I2C_STM_STO = 0x75
I2C_STM_OUT = 0x80
I2C_STM_IN = 0xC0
I2C_STM_SET = 0x60
I2C_STM_END = 0x00

# SPI/UIO stream commands (flashrom ch341a_spi.c)
SPI_STREAM = 0xA8
UIO_STREAM = 0xAB
UIO_STM_DIR = 0x40
UIO_STM_OUT = 0x80
UIO_STM_END = 0x20
SPI_CS_HIGH = 0x37
SPI_CS_LOW = 0x36

I2C_SPEED_100K = 1

# 24Cxx EEPROM family: name -> (size in bytes, address width in bytes).
# The I2C device address is the standard 0xA0/0xA1 with A0-A2 grounded.
I2C_EEPROMS = {
    '24C02': (256, 1),
    '24C16': (2048, 1),
    '24C32': (4096, 2),
    '24C64': (8192, 2),
    '24C128': (16384, 2),
    '24C256': (32768, 2),
}

# JEDEC manufacturer IDs (public standard assignments)
JEDEC_MANUFACTURERS = {
    0xEF: 'Winbond',
    0xC2: 'MXIC',
    0xC8: 'GigaDevice',
    0x01: 'Spansion',
    0x20: 'ST/Numonyx',
    0xBF: 'Microchip/SST',
    0x85: 'Puya',
    0xD8: 'Fudan',
}

# The CH341A SPI engine shifts LSB-first, so every byte must be
# bit-reversed on the way in and out (flashrom does the same)
_REVERSE = bytes(int('{:08b}'.format(i)[::-1], 2) for i in range(256))


def reverse_byte(value):
    """Bit-reverse a byte (the CH341A SPI engine is LSB-first)."""
    return _REVERSE[value]


def find_programmers():
    """Return the pyusb device objects for all connected CH341A."""
    return list(usb.core.find(
        find_all=True,
        custom_match=lambda d: (d.idVendor == CH341A_VID and
                                d.idProduct == CH341A_PID)))


def describe_jedec(ident):
    """Decode a 3-byte JEDEC ID into (name, size) or (raw, None).

    The capacity byte is the log2 of the chip size in bytes per the
    JEDEC standard (e.g. 0x18 = 16 MiB); anything implausible is
    reported as unknown rather than guessed.
    """
    if len(ident) < 3:
        return ' '.join('%02X' % b for b in ident), None
    manuf = JEDEC_MANUFACTURERS.get(ident[0], 'Unknown manufacturer')
    cap = ident[2]
    if 0x14 <= cap <= 0x20:
        size = 1 << cap
    else:
        size = None
    return '%s %02X%02X%02X' % (manuf, ident[0], ident[1], ident[2]), size


class CH341A:
    """Read-only access to one CH341A programmer.

    @dev may be a pyusb device or an injected test double with the
    same write/read interface.
    """

    def __init__(self, dev):
        self._dev = dev
        self._spi_enabled = False

    # -- USB plumbing ------------------------------------------------
    def open(self):
        try:
            if self._dev.is_kernel_driver_active(0):
                self._dev.detach_kernel_driver(0)
        except NotImplementedError:
            pass  # not available on every platform
        self._dev.set_configuration()

    def close(self):
        try:
            if self._spi_enabled:
                self.spi_disable()
        except Exception:
            LOG.exception('Failed to disable SPI pins on close')
        try:
            self._dev.attach_kernel_driver(0)
        except Exception:
            pass  # best effort only
        try:
            import usb.util
            usb.util.dispose_resources(self._dev)
        except Exception:
            # Not a real pyusb device (e.g. a test double) or already
            # disposed
            pass

    def _write(self, data):
        self._dev.write(WRITE_ENDPOINT, data, USB_TIMEOUT)

    def _read(self, n):
        return bytes(self._dev.read(READ_ENDPOINT, n, USB_TIMEOUT))

    # -- I2C EEPROM (24Cxx) -------------------------------------------
    def set_i2c_speed(self, speed=I2C_SPEED_100K):
        """Set the I2C bus speed (0=20k, 1=100k, 2=400k, 3=750k)."""
        self._write(bytes([I2C_STREAM, I2C_STM_SET | speed,
                           I2C_STM_END]))
        self._read(PACKET_LENGTH)  # drain the status response

    def _i2c_read_packet(self, addr, addr_bytes):
        """Build the documented 32-byte sequential-read command
        packet for a 24Cxx EEPROM at @addr (ch341eepromtool's
        CH341_EEPROM_READ_NEXT_CMD with the address bytes replaced)."""
        out = bytes([
            I2C_STREAM,
            I2C_STM_STA,
            I2C_STM_OUT | (1 + addr_bytes),  # dev addr + memory address
            0xA0,
        ])
        if addr_bytes == 2:
            out += bytes([(addr >> 8) & 0xFF, addr & 0xFF])
        else:
            out += bytes([addr & 0xFF])
        out += bytes([
            I2C_STM_STA,
            I2C_STM_OUT | 1,   # read mode device address
            0xA1,
            I2C_STM_IN | 0x20,  # read 32 bytes
            I2C_STM_END,
        ])
        # Documented filler from the reference NEXT_CMD packet,
        # padded with zeros to a full 32-byte USB packet
        out += bytes([
            0x00, 0x10, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00,
            0x8C, 0xF1, 0x12, 0x00, 0x01,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])
        assert len(out) <= PACKET_LENGTH
        return out + bytes(PACKET_LENGTH - len(out))

    def i2c_read_eeprom(self, size, addr_bytes=2, status_fn=None):
        """Read a 24Cxx EEPROM (up to @size bytes) in 32-byte blocks.

        The standard I2C device address 0xA0/0xA1 is used (A0-A2
        pins grounded), matching the reference implementations.
        """
        self.set_i2c_speed()
        data = bytearray()
        for addr in range(0, size, PACKET_LENGTH):
            self._write(self._i2c_read_packet(addr, addr_bytes))
            data += self._read(PACKET_LENGTH)
            if status_fn:
                status_fn(addr)
        return bytes(data)

    # -- SPI flash (25xx) ----------------------------------------------
    def _cs_assert_packet(self):
        """UIO packet that asserts CS (flashrom's pluck_cs with the
        default two delay bytes), padded to a full 32-byte packet."""
        out = bytes([
            UIO_STREAM,
            UIO_STM_OUT | SPI_CS_HIGH,  # deassert first
            UIO_STM_OUT | SPI_CS_HIGH,  # delay
            UIO_STM_OUT | SPI_CS_HIGH,  # delay
            UIO_STM_OUT | SPI_CS_LOW,   # assert
            UIO_STM_END,
        ])
        return out + bytes(PACKET_LENGTH - len(out))

    def spi_enable(self):
        """Drive the SPI pins (flashrom's enable_pins)."""
        self._write(bytes([
            UIO_STREAM,
            UIO_STM_OUT | SPI_CS_HIGH,
            UIO_STM_DIR | 0x3F,
            UIO_STM_END,
        ]))
        self._spi_enabled = True

    def spi_disable(self):
        self._write(bytes([
            UIO_STREAM,
            UIO_STM_OUT | SPI_CS_HIGH,
            UIO_STM_DIR | 0x00,
            UIO_STM_END,
        ]))
        self._spi_enabled = False

    def spi_transfer(self, write_bytes, read_len, packets=1):
        """One SPI transaction under a single CS assertion.

        Writes @write_bytes then reads @read_len bytes, using
        @packets 31-byte SPI stream packets (payload limited to
        31*packets bytes). Returns the read data with bits restored
        to MSB-first order.
        """
        payload = bytes(reverse_byte(b) for b in write_bytes)
        total_payload = len(payload) + read_len
        if total_payload > packets * 31:
            raise ValueError('transfer exceeds %i bytes' % (packets * 31))

        out = bytearray(self._cs_assert_packet())
        sent = 0
        for _ in range(packets):
            chunk = payload[sent:sent + 31]
            sent += len(chunk)
            pad = 31 - len(chunk)
            out += bytes([SPI_STREAM]) + chunk + b'\xff' * pad

        self._write(bytes(out))
        raw = self._read(31 * packets)

        result = bytearray()
        for i in range(read_len):
            offset = len(payload) + i
            result.append(reverse_byte(raw[offset]))
        return bytes(result)

    def jedec_id(self):
        """Read the 3-byte JEDEC manufacturer/device ID (command 0x9F)."""
        return self.spi_transfer([0x9F], 3)

    def spi_read_flash(self, size, status_fn=None, chunk_packets=8):
        """Read @size bytes of SPI NOR flash with the standard 0x03
        read command, in @chunk_packets-packet chunks per CS cycle
        (up to 31*chunk_packets-4 data bytes each)."""
        data = bytearray()
        addr = 0
        chunk_data = 31 * chunk_packets - 4
        while addr < size:
            n = min(chunk_data, size - addr)
            wbytes = [0x03,
                      (addr >> 16) & 0xFF,
                      (addr >> 8) & 0xFF,
                      addr & 0xFF]
            data += self.spi_transfer(wbytes, n,
                                      packets=chunk_packets)
            addr += n
            if status_fn:
                status_fn(addr)
        return bytes(data)
