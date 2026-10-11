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

"""Tests for the curated language selector of this build."""

import os
import unittest

import wx.lib.newevent  # noqa: F401  (modules under test rely on wx.lib)

from mychirp.wxui import main


class TestLanguageSelector(unittest.TestCase):
    def test_four_languages_offered(self):
        codes = [code for code, label in main.SUPPORTED_LANGUAGES]
        self.assertEqual(['pt_BR', 'en_US', 'zh_CN', 'ja_JP'], codes)

    def test_ptbr_is_the_default(self):
        """Brazilian Portuguese must be the first (default) option."""
        self.assertEqual('pt_BR', main.SUPPORTED_LANGUAGES[0][0])

    def test_every_offered_language_has_a_translation_source(self):
        """Each offered language must have a .po in the tree; the
        compiled .mo is a build artifact and may be absent on fresh
        checkouts."""
        locale_dir = os.path.join(os.path.dirname(main.__file__),
                                  '..', 'locale')
        for code, label in main.SUPPORTED_LANGUAGES:
            po = os.path.join(locale_dir, '%s.po' % code)
            self.assertTrue(os.path.exists(po),
                            'missing %s.po for %s' % (code, label))
            mo = os.path.join(locale_dir, code, 'LC_MESSAGES',
                              'CHIRP.mo')
            if not os.path.exists(mo):
                raise unittest.SkipTest(
                    'catalog %s not compiled in this checkout' % code)

    def test_labels_are_not_empty(self):
        for code, label in main.SUPPORTED_LANGUAGES:
            self.assertTrue(label.strip(), code)


if __name__ == '__main__':
    unittest.main()
