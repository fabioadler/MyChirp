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

"""Read-only chip programmer dialog for the CH341A.

Reads I2C EEPROMs (24Cxx) and SPI NOR flash (25xx) through a
CH341A programmer - the same hardware commonly used for BIOS chips.
Reading is the only operation; writing chips is deliberately not
offered (see chirp/hardware/ch341.py for the full rationale).
"""

import logging
import threading

import wx

from chirp import errors
from chirp.hardware import ch341
from chirp.wxui import common

_ = wx.GetTranslation
LOG = logging.getLogger(__name__)

READ_CHUNK = 32 * 8  # progress granularity


class ChirpChipProgDialog(wx.Dialog):
    """Read chips with a CH341A programmer (read-only)."""

    def __init__(self, parent):
        super().__init__(
            parent, title=_('Read chip with CH341A programmer'),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        vbox = wx.BoxSizer(wx.VERTICAL)
        panel = wx.Panel(self)
        psizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(psizer)
        vbox.Add(panel, 1, wx.EXPAND | wx.ALL, border=10)

        # Programmer status
        hs = wx.BoxSizer(wx.HORIZONTAL)
        self._status = wx.StaticText(panel, label=_('Detecting...'))
        hs.Add(self._status, 1, wx.ALIGN_CENTER_VERTICAL)
        self._detect_btn = wx.Button(panel, label=_('Detect again'))
        self._detect_btn.Bind(wx.EVT_BUTTON, self._detect)
        hs.Add(self._detect_btn, 0, wx.LEFT, border=8)
        psizer.Add(hs, 0, wx.EXPAND | wx.BOTTOM, border=8)

        # Family choice
        gs = wx.BoxSizer(wx.HORIZONTAL)
        gs.Add(wx.StaticText(panel, label=_('Chip type')),
               0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self._family = wx.Choice(panel, choices=[
            _('I2C EEPROM (24Cxx)'), _('SPI flash (25xx)')])
        self._family.SetSelection(0)
        self._family.Bind(wx.EVT_CHOICE, self._family_changed)
        gs.Add(self._family, 1)
        psizer.Add(gs, 0, wx.EXPAND | wx.BOTTOM, border=8)

        # I2C chip model
        self._eeprom_choice = wx.Choice(
            panel, choices=sorted(ch341.I2C_EEPROMS.keys()))
        self._eeprom_choice.SetStringSelection('24C64')
        gs2 = wx.BoxSizer(wx.HORIZONTAL)
        gs2.Add(wx.StaticText(panel, label=_('EEPROM')),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        gs2.Add(self._eeprom_choice, 1)
        psizer.Add(gs2, 0, wx.EXPAND | wx.BOTTOM, border=8)

        # SPI identification
        hs3 = wx.BoxSizer(wx.HORIZONTAL)
        self._jedec_btn = wx.Button(panel, label=_('Identify (JEDEC ID)'))
        self._jedec_btn.Bind(wx.EVT_BUTTON, self._identify)
        self._jedec_label = wx.StaticText(panel, label=_('Unknown'))
        hs3.Add(self._jedec_btn, 0, wx.RIGHT, border=8)
        hs3.Add(self._jedec_label, 1, wx.ALIGN_CENTER_VERTICAL)
        psizer.Add(hs3, 0, wx.EXPAND | wx.BOTTOM, border=8)
        hs4 = wx.BoxSizer(wx.HORIZONTAL)
        hs4.Add(wx.StaticText(panel, label=_('Size (bytes)')),
                0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        self._spi_size = wx.SpinCtrl(panel, min=1024, max=64 * 1024 * 1024,
                                     initial=1024 * 1024)
        hs4.Add(self._spi_size, 1)
        psizer.Add(hs4, 0, wx.EXPAND | wx.BOTTOM, border=8)

        self._family_changed(None)

        # Actions
        hs5 = wx.BoxSizer(wx.HORIZONTAL)
        self._read_btn = wx.Button(panel, label=_('Read chip'))
        self._read_btn.Bind(wx.EVT_BUTTON, self._read)
        hs5.Add(self._read_btn, 0, wx.RIGHT, border=8)
        close = wx.Button(panel, wx.ID_OK, _('Close'))
        hs5.AddStretchSpacer()
        hs5.Add(close, 0)
        psizer.Add(hs5, 0, wx.EXPAND | wx.TOP, border=8)

        # Honest safety note
        note = _(
            'Read-only tool. Real UV-EPROM chips (which need a '
            'programming voltage) are not supported by the CH341A. '
            'Reading a chip in-circuit may not work depending on the '
            'board; if in doubt, remove the chip. Nothing is written '
            'to the chip.')
        psizer.Add(wx.StaticText(panel, label=note), 0, wx.TOP, border=8)

        self._dev = None
        self.SetSizerAndFit(vbox)
        self.Center()
        wx.CallAfter(self._detect, None)

    # -- programmer detection ------------------------------------------
    def _detect(self, event):
        self._status.SetLabel(_('Detecting...'))
        try:
            devs = ch341.find_programmers()
        except Exception as e:
            LOG.exception('Programmer detection failed')
            self._status.SetLabel(_('Detection failed: %s') % e)
            self._dev = None
            return
        if not devs:
            self._status.SetLabel(
                _('No CH341A programmer found (USB %04X:%04X)') % (
                    ch341.CH341A_VID, ch341.CH341A_PID))
            self._dev = None
            return
        if len(devs) == 1:
            self._status.SetLabel(_('One CH341A programmer found'))
        else:
            self._status.SetLabel(_('%i CH341A programmers found; '
                                    'using the first') % len(devs))
        self._dev = devs[0]

    # -- helpers --------------------------------------------------------
    def _family_changed(self, event):
        i2c = self._family.GetSelection() == 0
        self._eeprom_choice.Enable(i2c)
        self._jedec_btn.Enable(not i2c)
        self._jedec_label.Enable(not i2c)
        self._spi_size.Enable(not i2c)

    def _open_programmer(self):
        if self._dev is None:
            raise errors.RadioError(
                _('No CH341A programmer found; click Detect again'))
        prog = ch341.CH341A(self._dev)
        prog.open()
        return prog

    # -- actions ---------------------------------------------------------
    @common.error_proof()
    def _identify(self, event):
        prog = self._open_programmer()
        try:
            prog.spi_enable()
            ident = prog.jedec_id()
        finally:
            try:
                prog.spi_disable()
            except Exception:
                pass
            prog.close()
        name, size = ch341.describe_jedec(ident)
        LOG.info('JEDEC ID: %s (name=%s size=%s)',
                 ' '.join('%02X' % b for b in ident), name, size)
        self._jedec_label.SetLabel(name)
        if size:
            self._spi_size.SetValue(size)

    @common.error_proof()
    def _read(self, event):
        prog = self._open_programmer()
        family = self._family.GetSelection()
        if family == 0:
            chip = self._eeprom_choice.GetStringSelection()
            size, addr_bytes = ch341.I2C_EEPROMS[chip]
        else:
            chip = self._jedec_label.GetLabel()
            size = self._spi_size.GetValue()
            addr_bytes = None

        total_blocks = max(1, size // READ_CHUNK)
        progress = wx.GenericProgressDialog(
            _('Reading chip'),
            _('Reading %i bytes...') % size,
            maximum=total_blocks, parent=self,
            style=wx.PD_AUTO_HIDE | wx.PD_APP_MODAL | wx.PD_CAN_ABORT)

        def worker(done):
            try:
                if family == 0:
                    data = prog.i2c_read_eeprom(
                        size, addr_bytes=addr_bytes,
                        status_fn=lambda a: wx.CallAfter(
                            progress.Update,
                            min((a + READ_CHUNK) // READ_CHUNK,
                                total_blocks)))
                    desc = _('I2C EEPROM %s') % chip
                else:
                    prog.spi_enable()
                    try:
                        data = prog.spi_read_flash(
                            size,
                            status_fn=lambda a: wx.CallAfter(
                                progress.Update,
                                min(a // READ_CHUNK, total_blocks)))
                    finally:
                        prog.spi_disable()
                    desc = _('SPI flash %s') % chip
                prog.close()
                wx.CallAfter(done, data, desc, None)
            except Exception as e:
                try:
                    prog.close()
                except Exception:
                    pass
                wx.CallAfter(done, None, None, e)

        def done(data, desc, error):
            progress.Destroy()
            if error is not None:
                LOG.error('Chip read failed: %s', error)
                common.error_proof.show_error(
                    _('Reading failed: %s') % error, parent=self)
                return
            d = wx.FileDialog(self, _('Save chip dump'),
                              defaultFile='chip_dump.bin',
                              wildcard='Raw binary (*.bin)|*.bin',
                              style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            if d.ShowModal() != wx.ID_OK:
                return
            extra = [_('Chip: %s') % desc,
                     _('Everything the chip returned; read-only '
                       'operation, nothing was written')]
            _size, crc = common.write_raw_bytes_dump(
                data, d.GetPath(), _('Chip dump'), extra)
            LOG.info('Chip dump: %s, %i bytes, CRC32 %08X',
                     desc, _size, crc)
            wx.MessageBox(
                _('Read %i bytes (CRC32 %08X).') % (_size, crc),
                _('Chip dump'), wx.ICON_INFORMATION, parent=self)

        t = threading.Thread(target=worker, args=(done,), daemon=True)
        t.start()
