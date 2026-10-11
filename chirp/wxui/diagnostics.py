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

import glob
import logging
import os

import serial
import serial.tools.list_ports
import wx

from chirp import chirp_common
from chirp import directory
from chirp.wxui import clone
from chirp.wxui import common
from chirp.wxui import config
from chirp.wxui import portwatch

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

        # Programming cables section
        _add_section(panel, psizer, _('Programming cables'))
        ports = serial.tools.list_ports.comports()
        known = [p for p in ports if portwatch.is_known_cable(p)]
        if known:
            for port in known:
                desc = portwatch.describe_port(port)
                label = '%s: %s' % (port.device, desc)
                psizer.Add(wx.StaticText(panel, label=label),
                           0, wx.LEFT, border=8)
        else:
            psizer.Add(wx.StaticText(
                panel, label=_('No known programming cable connected')),
                0, wx.LEFT, border=8)
        if portwatch.LAST_DETECTED:
            psizer.Add(wx.StaticText(
                panel,
                label='%s: %s (%s)' % (
                    _('Last detected'),
                    portwatch.LAST_DETECTED.get('description'),
                    portwatch.LAST_DETECTED.get('time'))),
                0, wx.LEFT, border=8)

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

        # Connection tests: read-only actions
        _add_section(panel, psizer, _('Connection tests'))
        self._test_output = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY |
            wx.TE_DONTWRAP | wx.BORDER_SUNKEN)
        self._test_output.SetMinSize((-1, 90))
        psizer.Add(self._test_output, 0, wx.EXPAND | wx.BOTTOM, border=8)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        test_port = wx.Button(panel, label=_('Test port'))
        test_port.Bind(wx.EVT_BUTTON, self._test_port)
        hbox.Add(test_port, 0, wx.ALL, border=4)
        ident_btn = wx.Button(panel, label=_('Identify radio (read-only)'))
        ident_btn.Bind(wx.EVT_BUTTON, self._identify_radio)
        hbox.Add(ident_btn, 0, wx.ALL, border=4)
        trace_btn = wx.Button(panel, label=_('Open last serial trace'))
        trace_btn.Bind(wx.EVT_BUTTON, self._open_last_trace)
        hbox.Add(trace_btn, 0, wx.ALL, border=4)
        backup_btn = wx.Button(panel, label=_('Open backup location'))
        backup_btn.Bind(wx.EVT_BUTTON, self._open_backups)
        hbox.Add(backup_btn, 0, wx.ALL, border=4)
        psizer.Add(hbox, 0, wx.EXPAND)

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

    def _report(self, msg):
        self._test_output.AppendText('%s\n' % msg)

    def _current_port_and_rclass(self):
        """Best-known port and radio class for the tests."""
        port = clone.LAST_CLONE_RESULT.get('port')
        if not port:
            port = CONF.get('last_port', 'state')
        vendor = CONF.get('last_vendor', 'state')
        model = CONF.get('last_model', 'state')
        rclass = _get_rclass_for(vendor, model)
        return port, rclass

    @common.error_proof()
    def _test_port(self, event):
        """Open and close the serial port to verify it is usable."""
        port, rclass = self._current_port_and_rclass()
        if not port:
            self._report(_('No port selected or remembered yet'))
            return
        baud = getattr(rclass, 'BAUD_RATE', 9600)
        try:
            s = serial.Serial(port=port, baudrate=baud, timeout=0.5)
            s.close()
        except Exception as e:
            self._report(_('Failed to open %s: %s') % (port, e))
            return
        driver = ''
        try:
            link = os.path.realpath(
                '/sys/class/tty/%s/device/driver' % os.path.basename(port))
            driver = os.path.basename(link)
        except Exception:
            pass
        self._report(_('%s opened and closed fine at %i baud%s') % (
            port, baud, ' (%s)' % driver if driver else ''))

    @common.error_proof()
    def _identify_radio(self, event):
        """Perform the read-only programming-mode handshake.

        Only the standard ident exchange is executed; no block is read
        or written. Depending on the radio, it may need to be turned
        off and on again afterwards to leave programming mode.
        """
        port, rclass = self._current_port_and_rclass()
        if not port:
            self._report(_('No port selected or remembered yet'))
            return
        if rclass is None:
            self._report(_('Select a vendor and model in the clone '
                           'dialog first'))
            return
        if not issubclass(rclass, chirp_common.CloneModeRadio):
            self._report(_('%s %s is not a cable-programmable radio') % (
                rclass.VENDOR, rclass.MODEL))
            return
        try:
            s = serial.Serial(port=port, baudrate=rclass.BAUD_RATE,
                              timeout=1)
        except Exception as e:
            self._report(_('Failed to open %s: %s') % (port, e))
            return
        try:
            if hasattr(rclass, '_idents'):
                # UV-5R protocol family
                from chirp.drivers import uv5r
                radio = rclass(s)
                ident = uv5r._ident_radio(radio)
            elif hasattr(rclass, 'IDENT'):
                # H777/BF-888 protocol family
                from chirp.drivers import h777
                ident = h777._h777_enter_programming_mode(s, rclass)
            else:
                self._report(_('Handshake test not implemented for the '
                               '%s %s driver family') % (rclass.VENDOR,
                                                         rclass.MODEL))
                return
        except Exception as e:
            self._report(_('%s %s did not answer: %s') % (
                rclass.VENDOR, rclass.MODEL, e))
            return
        finally:
            try:
                s.close()
            except Exception:
                pass
        if ident:
            try:
                shown = ' '.join('%02X' % b for b in ident)
            except TypeError:
                shown = repr(ident)
            msg = _('%s %s answered: %s') % (rclass.VENDOR,
                                             rclass.MODEL, shown)
            self._report(msg)
        else:
            msg = _('%s %s did not answer') % (rclass.VENDOR,
                                               rclass.MODEL)
            self._report(msg)
        self._report(_('Only the handshake was executed; no data was '
                       'read or written'))

    @common.error_proof()
    def _open_last_trace(self, event):
        traces = sorted(glob.glob('/tmp/chirp-trace-*.txt'))
        if not traces:
            wx.MessageBox(_('No serial trace recorded yet in this '
                            'session'), _('Serial trace'),
                          wx.ICON_INFORMATION, parent=self)
            return
        wx.LaunchDefaultApplication(traces[-1])

    @common.error_proof()
    def _open_backups(self, event):
        from chirp import platform as chirp_platform
        backup_dir = chirp_platform.get_platform().config_file('backups')
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except Exception as e:
            LOG.warning('Failed to create backup dir: %s', e)
            return
        common.reveal_location(backup_dir)
