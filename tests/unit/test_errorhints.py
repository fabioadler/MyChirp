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

import unittest

import wx.lib.newevent  # noqa: F401  (common.py relies on wx.lib)

from mychirp.wxui import common


class TestErrorHints(unittest.TestCase):
    def test_refused_second_block(self):
        """The historical BOMVINK-style failure must produce a
        simplified message plus suggestions."""
        simple, tips = common.error_hints(
            'Radio refused to send second block 0x1EC0')
        self.assertIsNotNone(simple)
        self.assertTrue(tips)
        # The simplified layer must not expose raw hex details as the
        # primary message, and suggestions must be actionable
        for tip in tips:
            self.assertTrue(tip)

    def test_no_response(self):
        simple, tips = common.error_hints('No response from radio')
        self.assertIsNotNone(simple)
        self.assertTrue(tips)

    def test_refused_clone(self):
        simple, tips = common.error_hints('Radio refused clone')
        self.assertIsNotNone(simple)
        self.assertTrue(tips)

    def test_unknown_response(self):
        simple, tips = common.error_hints('Unknown response from radio')
        self.assertIsNotNone(simple)
        self.assertTrue(tips)

    def test_unknown_error_has_no_simplified_layer(self):
        """Unmapped errors must return no simplified text so the caller
        shows the original message alone (nothing invented)."""
        simple, tips = common.error_hints('Some brand new failure')
        self.assertIsNone(simple)
        self.assertEqual([], tips)


if __name__ == '__main__':
    unittest.main()
