# Copyright 2026:
# * MyChirp contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Baofeng UV-16 Plus (2024/2025 model, UV-5R-style display).

Despite being a newer model (10W labeled, tri-power), this radio uses
the classic UV-5R clone protocol and memory layout, reverse-engineered
on real hardware:

- Serial: 9600 baud, magic ``UV5R_MODEL_291`` (``50 BB FF 20 12 07 25``)
- Radio ident (fingerprint): ``aa 30 76 04 00 05 20 dd``
- Firmware string in the aux block (0x1EF0): ``HN5RV01``
- Image: ident(8) + main 0x0000-0x1800 + aux 0x1EC0-0x2000 = 0x1948
- 128 channels (0-127), tri-power (High/Med/Low)
- Bands: VHF 136-174 MHz, UHF 400-520 MHz (10W labeled)
"""

from mychirp import chirp_common, directory
from mychirp.drivers import uv5r

BASETYPE_UV16PLUS = [b"HN5RV"]

# Labeled watts per the manufacturer (10W). Labels "High"/"Med"/"Low"
# match UV5R_POWER_LEVELS3 so the inherited tri-power encode/decode
# (which matches by string label) keeps working.
UV16PLUS_POWER_LEVELS = [chirp_common.PowerLevel("High", watts=10.00),
                         chirp_common.PowerLevel("Med", watts=5.00),
                         chirp_common.PowerLevel("Low", watts=2.00)]


@directory.register
class BaofengUV16PlusRadio(uv5r.BaofengBFF8HPRadio):
    """Baofeng UV-16 Plus"""
    VENDOR = "Baofeng"
    MODEL = "UV-16 Plus"

    _basetype = BASETYPE_UV16PLUS
    _idents = [uv5r.UV5R_MODEL_291]
    _vhf_range = (136000000, 174000000)
    _uhf_range = (400000000, 520000000)

    def get_features(self):
        rf = super().get_features()
        rf.valid_power_levels = UV16PLUS_POWER_LEVELS
        return rf

    def get_memory(self, number):
        mem = super().get_memory(number)
        if mem.power is not None:
            labels = [str(level) for level in uv5r.UV5R_POWER_LEVELS3]
            mem.power = UV16PLUS_POWER_LEVELS[labels.index(str(mem.power))]
        return mem
