# Copyright 2008 Dan Smith <dsmith@danplanet.com>
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

CHIRP_VERSION = "2.0.2-beta"

# ---------------------------------------------------------------------------
# Translatable-string shim (upstream parity)
#
# Upstream CHIRP resolved the ``_()`` marker in every driver by injecting a
# translation function into the Python builtins from the wxui package
# (``builtins._ = wx.GetTranslation``).  The wxui was removed in the
# PySide6 migration and nothing replaced the injection, leaving 73 driver
# files and 2 chirp_common sites with an undefined ``_`` (NameError at
# runtime: 227 of 564 drivers crashed in get_prompts()).
#
# This shim installs a NO-OP translation as soon as the mychirp package is
# imported (so nothing ever crashes), and the real catalog-aware ``_`` is
# installed later on top of it by mychirp.pysideui.i18n at GUI startup.
import builtins

if '_' not in builtins.__dict__:
    builtins._ = str
