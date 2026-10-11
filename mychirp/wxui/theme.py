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

"""Central theme infrastructure for the wxui.

Implements the design-token approach recorded in docs/ui-redesign.md:
a semantic palette with light and dark variants (adapted from the
UI/UX Pro Max guidance), a 4px spacing scale, and helpers that apply
the palette to a window tree without touching native widgets that
would look wrong when painted (menus, native buttons).

The mode (system/light/dark) is persisted in the existing chirp config
under the 'state' section and can be changed at runtime; registered
top-level windows are re-styled when it changes.
"""

import logging

import wx

from mychirp.wxui import config

LOG = logging.getLogger(__name__)

CONF = config.get()

# 4px-based spacing scale (see docs/ui-redesign.md)
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

# Semantic palette: light (base) and dark (role remapping)
LIGHT = {
    'BG_WINDOW': '#F6F7F9',
    'BG_PANEL': '#FFFFFF',
    'BG_GRID_ALT': '#F1F3F5',
    'BG_PENDING': '#FFF4D6',
    'BG_IMMUTABLE': '#F0F1F3',
    'FG_TEXT': '#1A1C1E',
    'FG_MUTED': '#5A6069',
    'ACCENT': '#1A6B8F',
    'ACCENT_DOWNLOAD': '#1E7B4F',
    'ACCENT_UPLOAD': '#B3541E',
    'ERROR': '#B3261E',
    'BORDER': '#D8DCE0',
}

DARK = {
    'BG_WINDOW': '#1E1F24',
    'BG_PANEL': '#26272C',
    'BG_GRID_ALT': '#222329',
    'BG_PENDING': '#3A3320',
    'BG_IMMUTABLE': '#2B2C31',
    'FG_TEXT': '#E8EAED',
    'FG_MUTED': '#9AA1AC',
    'ACCENT': '#5FB2CE',
    'ACCENT_DOWNLOAD': '#4CAF7D',
    'ACCENT_UPLOAD': '#E08A4F',
    'ERROR': '#F2B8B5',
    'BORDER': '#383B42',
}

MODE_SYSTEM = 'system'
MODE_LIGHT = 'light'
MODE_DARK = 'dark'
MODES = (MODE_SYSTEM, MODE_LIGHT, MODE_DARK)

# Default to dark mode
_configured_mode = CONF.get('theme_mode', 'state') or MODE_DARK
if _configured_mode not in MODES:
    _configured_mode = MODE_DARK

_listeners = []
_windows = []


def system_prefers_dark():
    """Return True if the desktop prefers a dark appearance."""
    try:
        return wx.SystemSettings.GetAppearance().IsDark()
    except Exception:
        return False


def get_mode():
    """Return the configured mode: system, light or dark."""
    return _configured_mode


def is_dark():
    """Return True if the effective palette is the dark one."""
    if _configured_mode == MODE_SYSTEM:
        return system_prefers_dark()
    return _configured_mode == MODE_DARK


def set_mode(mode):
    """Set the theme mode, persist it and restyle registered windows."""
    global _configured_mode
    if mode not in MODES:
        raise ValueError('Unknown theme mode %r' % mode)
    _configured_mode = mode
    CONF.set('theme_mode', mode, 'state')
    for window in list(_windows):
        apply(window)
    for callback in list(_listeners):
        try:
            callback(mode)
        except Exception:
            LOG.exception('Theme listener failed')


def on_mode_change(callback):
    """Register a callback invoked on every mode change."""
    _listeners.append(callback)


def role(name):
    """Return the raw hex string for a semantic role."""
    palette = DARK if is_dark() else LIGHT
    try:
        return palette[name]
    except KeyError:
        raise KeyError('Unknown theme role %r' % name)


def color(name):
    """Return a wx.Colour for a semantic role.

    The color is built from raw RGB components (not the string
    constructor) so that it works even before a wx.App is created.
    """
    hexstr = role(name).lstrip('#')
    return wx.Colour(int(hexstr[0:2], 16),
                     int(hexstr[2:4], 16),
                     int(hexstr[4:6], 16))


def register(window):
    """Register a top-level window to restyle on mode changes."""
    if window not in _windows:
        _windows.append(window)
    apply(window)


def _style_window_tree(window, panel_color, text_color):
    for child in window.GetChildren():
        # Windows that manage their own colors (e.g. the welcome
        # splash) are exempt from theming
        if getattr(child, '_theme_exempt', False):
            continue
        try:
            if isinstance(child, (wx.Panel, wx.ScrolledWindow)):
                child.SetBackgroundColour(panel_color)
                _style_window_tree(child, panel_color, text_color)
            elif isinstance(child, wx.grid.Grid):
                child.SetLabelBackgroundColour(panel_color)
                child.SetLabelTextColour(text_color)
                child.SetLabelFont(child.GetLabelFont())
                child.SetDefaultCellBackgroundColour(
                    color('BG_PANEL'))
                child.SetDefaultCellTextColour(text_color)
                child.SetBackgroundColour(panel_color)
            elif isinstance(child, (wx.TextCtrl, wx.ListCtrl,
                                    wx.TreeCtrl, wx.ListBox,
                                    wx.Choice, wx.ComboCtrl,
                                    wx.CheckListBox)):
                child.SetBackgroundColour(color('BG_PANEL'))
                child.SetForegroundColour(text_color)
            elif isinstance(child, (wx.StaticText, wx.StaticLine,
                                    wx.StatusBar, wx.Gauge,
                                    wx.html.HtmlWindow)):
                child.SetForegroundColour(text_color)
                if not isinstance(child, (wx.StaticLine, wx.Gauge)):
                    child.SetBackgroundColour(color('BG_WINDOW'))
            elif isinstance(child, (wx.Notebook, wx.aui.AuiNotebook,
                                    wx.Listbook, wx.Choicebook,
                                    wx.Treebook)):
                child.SetBackgroundColour(color('BG_WINDOW'))
                _style_window_tree(child, panel_color, text_color)
            elif isinstance(child, (wx.Dialog, wx.Frame)):
                _style_window_tree(child, panel_color, text_color)
            # Native menus and buttons are left to the platform theme
        except Exception:
            LOG.exception('Failed to style %r', child)


def apply(window):
    """Apply the current theme to a window and its children."""
    try:
        window_color = color('BG_WINDOW')
        panel_color = color('BG_PANEL')
        text_color = color('FG_TEXT')
    except Exception:
        LOG.exception('Failed to resolve theme colors')
        return
    try:
        window.SetBackgroundColour(window_color)
        _style_window_tree(window, panel_color, text_color)
        window.Refresh()
    except Exception:
        LOG.exception('Failed to apply theme to %r', window)
