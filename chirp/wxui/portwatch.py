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

"""Serial port hotplug detection.

Watches the system serial ports and reports added/removed devices so
the UI can tell the user when a programming cable (and possibly a
radio) is plugged in. Detection is passive: it only enumerates ports,
never opens them.
"""

import logging

import serial.tools.list_ports
import wx

_ = wx.GetTranslation
LOG = logging.getLogger(__name__)

# Well-known USB serial adapter chips used in programming cables.
# Anything unknown is still described by its raw VID:PID.
KNOWN_USB_CHIPS = {
    (0x1A86, 0x7523): 'WCH CH340 USB serial',
    (0x1A86, 0x55D4): 'WCH CH9102 USB serial',
    (0x067B, 0x2303): 'Prolific PL2303 USB serial',
    (0x0403, 0x6001): 'FTDI FT232 USB serial',
    (0x10C4, 0xEA60): 'Silicon Labs CP210x USB serial',
}


def describe_port(port):
    """Human-oriented description of a serial port device."""
    chip = KNOWN_USB_CHIPS.get((port.vid, port.pid))
    if chip:
        return '%s (%s)' % (port.device, chip)
    if port.vid is not None:
        desc = '%s (%04X:%04X %s)' % (port.device, port.vid,
                                      port.pid or 0,
                                      port.description or 'USB serial')
        return desc
    return port.device


def diff_ports(old, new):
    """Return (added, removed) port descriptions between two lists."""
    old_devices = {p.device: p for p in old}
    new_devices = {p.device: p for p in new}
    added = [new_devices[d] for d in
             sorted(set(new_devices) - set(old_devices))]
    removed = [old_devices[d] for d in
               sorted(set(old_devices) - set(new_devices))]
    return added, removed


class PortWatcher(wx.EvtHandler):
    """Periodically enumerates serial ports and reports changes.

    Intentionally poll-based: udev events are Linux-specific, while
    pyserial enumeration works on every platform CHIRP supports. The
    timer only runs while started, and the check never opens a port.
    """

    INTERVAL_MS = 2000

    def __init__(self, on_added=None, on_removed=None):
        super().__init__()
        self._on_added = on_added
        self._on_removed = on_removed
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._check)
        self._last = []

    def snapshot(self):
        try:
            return list(serial.tools.list_ports.comports())
        except Exception:
            LOG.exception('Failed to enumerate serial ports')
            return []

    def start(self):
        self._last = self.snapshot()
        self._timer.Start(self.INTERVAL_MS)

    def stop(self):
        self._timer.Stop()

    def _check(self, event):
        current = self.snapshot()
        added, removed = diff_ports(self._last, current)
        self._last = current
        if added and self._on_added:
            for port in added:
                try:
                    self._on_added(port)
                except Exception:
                    LOG.exception('PortWatcher added callback failed')
        if removed and self._on_removed:
            for port in removed:
                try:
                    self._on_removed(port)
                except Exception:
                    LOG.exception('PortWatcher removed callback failed')
