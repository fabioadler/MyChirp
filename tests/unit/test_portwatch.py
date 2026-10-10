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

"""Unit tests for serial port hotplug detection (pure logic parts)."""

import unittest

from chirp.wxui import portwatch


class FakePort:
    def __init__(self, device, vid=None, pid=None, description=''):
        self.device = device
        self.vid = vid
        self.pid = pid
        self.description = description


class TestDiffPorts(unittest.TestCase):
    def test_no_change(self):
        old = [FakePort('/dev/ttyUSB0', 0x1A86, 0x7523)]
        new = [FakePort('/dev/ttyUSB0', 0x1A86, 0x7523)]
        added, removed = portwatch.diff_ports(old, new)
        self.assertEqual([], added)
        self.assertEqual([], removed)

    def test_added_and_removed(self):
        old = [FakePort('/dev/ttyUSB0'), FakePort('/dev/ttyACM0')]
        new = [FakePort('/dev/ttyUSB1'), FakePort('/dev/ttyACM0')]
        added, removed = portwatch.diff_ports(old, new)
        self.assertEqual(['/dev/ttyUSB1'], [p.device for p in added])
        self.assertEqual(['/dev/ttyUSB0'], [p.device for p in removed])

    def test_empty_lists(self):
        added, removed = portwatch.diff_ports([], [])
        self.assertEqual(([], []), (added, removed))


class TestDescribePort(unittest.TestCase):
    def test_known_chip(self):
        port = FakePort('/dev/ttyUSB0', 0x1A86, 0x7523, 'USB Serial')
        self.assertIn('CH340', portwatch.describe_port(port))
        self.assertIn('/dev/ttyUSB0', portwatch.describe_port(port))

    def test_unknown_chip_shows_raw_ids(self):
        port = FakePort('/dev/ttyUSB9', 0x1234, 0x5678, 'Weird cable')
        desc = portwatch.describe_port(port)
        self.assertIn('1234:5678', desc)
        self.assertIn('Weird cable', desc)

    def test_no_usb_ids(self):
        port = FakePort('/dev/ttyS0')
        self.assertEqual('/dev/ttyS0', portwatch.describe_port(port))


class TestHardwareRequirements(unittest.TestCase):
    def test_uv5r_family_documents_cable(self):
        """The UV-5R protocol family (including the BOMVINK BOM-5701)
        documents the two-pin cable it needs."""
        from chirp.drivers import uv5r
        for rclass in (uv5r.BaofengUV5R, uv5r.BaofengUV5RGeneric,
                       uv5r.BOMVINKBOM5701):
            reqs = getattr(rclass, 'HARDWARE_REQUIREMENTS', None)
            self.assertIsNotNone(reqs, rclass)
            self.assertIn('two-pin', reqs)

    def test_no_fabricated_requirements(self):
        """Drivers without documented hardware requirements must not
        invent any."""
        from chirp.drivers import generic_csv
        self.assertIsNone(
            getattr(generic_csv.CSVRadio, 'HARDWARE_REQUIREMENTS', None))


if __name__ == '__main__':
    unittest.main()
