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
from unittest import mock

import wx

from mychirp.wxui import theme


class TestTheme(unittest.TestCase):
    def test_palettes_have_matching_roles(self):
        """Light and dark palettes must define the same semantic roles."""
        self.assertEqual(set(theme.LIGHT), set(theme.DARK))

    def test_roles_resolve(self):
        """Every role must resolve to a wx.Colour in both modes."""
        for mode in (theme.MODE_LIGHT, theme.MODE_DARK):
            theme._configured_mode = mode
            for name in theme.LIGHT:
                c = theme.color(name)
                self.assertIsInstance(c, wx.Colour)
                self.assertTrue(c.IsOk())

    def test_system_mode_resolution(self):
        """MODE_SYSTEM resolves dark/light from the platform."""
        theme._configured_mode = theme.MODE_SYSTEM
        with mock.patch.object(theme, 'system_prefers_dark',
                               return_value=True):
            self.assertTrue(theme.is_dark())
        with mock.patch.object(theme, 'system_prefers_dark',
                               return_value=False):
            self.assertFalse(theme.is_dark())

    def test_unknown_role(self):
        theme._configured_mode = theme.MODE_LIGHT
        self.assertRaises(KeyError, theme.role, 'NOT_A_ROLE')

    def test_unknown_mode(self):
        self.assertRaises(ValueError, theme.set_mode, 'sepia')

    def test_download_upload_accents_differ(self):
        """Reading and writing must never share an accent color."""
        for palette in (theme.LIGHT, theme.DARK):
            self.assertNotEqual(palette['ACCENT_DOWNLOAD'],
                                palette['ACCENT_UPLOAD'])


if __name__ == '__main__':
    unittest.main()
