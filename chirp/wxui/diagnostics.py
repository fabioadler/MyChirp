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

"""Radio communication diagnostics panel.

Presents the information that matters when a clone fails, in two
layers: the human-oriented summary with suggestions, and the raw
technical facts (detected ports, selected model, baud rate, last
communication step and original error message). Never guesses: if a
piece of information is unknown, it is shown as unknown.
"""

import logging

import serial.tools.list_ports
import wx

from chirp import chirp_common
from chirp import directory
from chirp.wxui import clone
from chirp.wxui import common
from chirp.wxui import config

_ = wx.GetTranslation
LOG = logging.getLogger(__name__)
CONF = config.get()


def _get_rclass_for(vendor, model):
    for rclass in directory.DRV_TO_RADIO.values():
        if (rclass.VENDOR == vendor and rclass.MODEL == model and
                issubclass(rclass, chirp_common.CloneModeRadio)):
            return rclass
    return None


def _add_section(parent, sizer, title):
    label = wx.StaticText(parent, label=title)
    font = label.GetFont()
    font.SetWeight(wx.FONTWEIGHT_BOLD)
    label.SetFont(font)
    sizer.Add(label, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, border=4)


class ChirpDiagnosticsDialog(wx.Dialog):
    """Dialog summarizing the communication state for troubleshooting."""

    def __init__(self, parent):
        super().__init__(parent, title=_('Radio diagnostics'),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        vbox = wx.BoxSizer(wx.VERTICAL)
        panel = wx.Panel(self)
        psizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(psizer)
        vbox.Add(panel, 1, wx.EXPAND | wx.ALL, border=10)

        # Serial ports section
        _add_section(panel, psizer, _('Serial ports'))
        ports = serial.tools.list_ports.comports()
        if ports:
            port_list = wx.ListCtrl(panel, style=wx.LC_REPORT |
                                    wx.BORDER_SUNKEN)
            port_list.InsertColumn(0, _('Device'))
            port_list.InsertColumn(1, _('Description'))
            port_list.InsertColumn(2, _('USB ID'))
            for port in ports:
                row = port_list.InsertItem(
                    port_list.GetItemCount(), port.device)
                port_list.SetItem(row, 1, port.description or '')
                if port.vid is not None:
                    port_list.SetItem(row, 2, '%04X:%04X' % (
                        port.vid, port.pid or 0))
            port_list.SetColumnWidth(0, 140)
            port_list.SetColumnWidth(1, 220)
            port_list.SetColumnWidth(2, 100)
            psizer.Add(port_list, 0, wx.EXPAND | wx.BOTTOM, border=8)
        else:
            psizer.Add(wx.StaticText(
                panel, label=_('No serial ports detected')),
                0, wx.BOTTOM, border=8)

        # Selected model section
        _add_section(panel, psizer, _('Selected radio'))
        vendor = CONF.get('last_vendor', 'state') or _('unknown')
        model = CONF.get('last_model', 'state') or _('unknown')
        rclass = _get_rclass_for(vendor, model)
        lines = ['%s: %s %s' % (_('Model'), vendor, model)]
        if rclass is not None:
            lines.append('%s: %s baud' % (_('Communication speed'),
                                          getattr(rclass, 'BAUD_RATE',
                                                  _('unknown'))))
            requirements = getattr(rclass, 'HARDWARE_REQUIREMENTS', None)
            if requirements:
                lines.append('%s: %s' % (_('Cable'), requirements))
        for line in lines:
            psizer.Add(wx.StaticText(panel, label=line), 0,
                       wx.LEFT, border=8)

        # Last communication section
        _add_section(panel, psizer, _('Last communication'))
        result = clone.LAST_CLONE_RESULT
        if not result:
            no_attempt = wx.StaticText(
                panel, label=_('No communication attempt recorded in '
                               'this session'))
            psizer.Add(no_attempt, 0, wx.LEFT, border=8)
        else:
            status = _('succeeded') if result.get('ok') else _('failed')
            info = [
                '%s: %s' % (_('Operation'), result.get('direction') or
                            _('unknown')),
                '%s: %s' % (_('Model'), result.get('model') or _('unknown')),
                '%s: %s' % (_('Port'), result.get('port') or _('unknown')),
                '%s: %s' % (_('Time'), result.get('time') or _('unknown')),
                '%s: %s' % (_('Result'), status),
            ]
            for line in info:
                psizer.Add(wx.StaticText(panel, label=line), 0,
                           wx.LEFT, border=8)
            error = result.get('error')
            if error:
                _add_section(panel, psizer, _('Technical error message'))
                errbox = wx.TextCtrl(panel, style=wx.TE_MULTILINE |
                                     wx.TE_READONLY | wx.BORDER_SUNKEN)
                errbox.SetValue(str(error))
                errbox.SetMinSize((-1, 60))
                psizer.Add(errbox, 0, wx.EXPAND | wx.BOTTOM, border=8)
                suggestions = common.error_hints(error)[1]
                if suggestions:
                    _add_section(panel, psizer, _('Suggestions'))
                    for suggestion in suggestions:
                        psizer.Add(wx.StaticText(
                            panel, label=' - %s' % suggestion),
                            0, wx.LEFT, border=8)

        # Debug log section
        _add_section(panel, psizer, _('Debug log'))
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        log_btn = wx.Button(panel, label=_('Open debug log'))
        log_btn.Bind(wx.EVT_BUTTON, self._open_debug_log)
        hbox.Add(log_btn, 0, wx.ALL, border=4)
        psizer.Add(hbox, 0, wx.EXPAND)

        # Honest note about firmware, so users understand what CHIRP
        # can and cannot do (and why)
        _add_section(panel, psizer, _('About firmware'))
        note = _(
            'CHIRP reads and writes the channel memory image over the '
            "radio's clone protocol. It does not read or write "
            'firmware: firmware access requires radio-specific hardware '
            'and protocols, and writing it without validation can '
            'permanently damage the radio.')
        psizer.Add(wx.StaticText(panel, label=note),
                   0, wx.LEFT | wx.BOTTOM, border=8)

        close = wx.Button(self, wx.ID_OK)
        vbox.Add(close, 0, wx.ALL | wx.ALIGN_RIGHT, border=10)
        self.SetSizerAndFit(vbox)
        self.Center()

    def _open_debug_log(self, event):
        dst = common.temporary_debug_log()
        wx.LaunchDefaultApplication(dst)
