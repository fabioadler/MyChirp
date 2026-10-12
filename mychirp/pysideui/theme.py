"""Qt/Qt6 theme for the PySide6 UI.

Maps the shared color tokens (mychirp.theme.AppColors) to QSS and
QPalette presets for light and dark modes.
"""

import logging

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from mychirp.theme import AppColors

LOG = logging.getLogger(__name__)


def _qcolor(token: str) -> QColor:
    """Convert '#AABBCC' or '#RRGGBBAA' tokens to QColor."""
    return QColor(token)


def build_palette(dark: bool) -> QPalette:
    """Build a QPalette from the semantic tokens."""
    c = AppColors.for_mode(dark)
    palette = QPalette()

    palette.setColor(
        QPalette.ColorRole.Window, _qcolor(c.bg_panel if dark else c.bg_window))
    palette.setColor(QPalette.ColorRole.WindowText, _qcolor(c.fg_text))
    palette.setColor(QPalette.ColorRole.Base, _qcolor(c.input))
    palette.setColor(QPalette.ColorRole.AlternateBase, _qcolor(c.bg_panel_alt))
    palette.setColor(QPalette.ColorRole.ToolTipBase, _qcolor(c.bg_panel_alt))
    palette.setColor(QPalette.ColorRole.ToolTipText, _qcolor(c.fg_text))
    palette.setColor(QPalette.ColorRole.Text, _qcolor(c.fg_text))
    palette.setColor(QPalette.ColorRole.Button, _qcolor(c.bg_panel))
    palette.setColor(QPalette.ColorRole.ButtonText, _qcolor(c.fg_text))
    palette.setColor(QPalette.ColorRole.BrightText, _qcolor(c.fg_text))
    palette.setColor(QPalette.ColorRole.Link, _qcolor(c.accent))
    palette.setColor(QPalette.ColorRole.Highlight, _qcolor(c.accent))
    palette.setColor(
        QPalette.ColorRole.HighlightedText, _qcolor(c.fg_text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, _qcolor(c.fg_muted))
    palette.setColor(QPalette.ColorRole.Shadow, _qcolor("#000000"))
    if dark:
        palette.setColor(QPalette.ColorRole.Base, _qcolor(c.bg_window))

    return palette


def build_stylesheet(dark: bool) -> str:
    """Generate QSS from the shared semantic tokens."""
    c = AppColors.for_mode(dark)
    menu_bg = c.bg_panel
    menu_fg = c.fg_text
    menu_sel = c.accent_container

    lines = [
        "QMainWindow, QDialog { background-color: %s; color: %s; }" % (
            c.bg_window, c.fg_text),
        "QMenuBar { background-color: %s; color: %s; "
        "border-bottom: 1px solid %s; }" % (menu_bg, menu_fg, c.border),
        "QMenuBar::item { background-color: transparent; padding: 6px 12px; "
        "border-radius: 6px; }",
        "QMenuBar::item:selected { background-color: %s; }" % menu_sel,
        "QMenu { background-color: %s; color: %s; border: 1px solid %s; "
        "padding: 4px; }" % (menu_bg, menu_fg, c.border_soft),
        "QMenu::item { padding: 6px 24px 6px 24px; border-radius: 4px; }",
        "QMenu::item:selected { background-color: %s; }" % menu_sel,
        "QMenu::separator { height: 1px; background-color: %s; "
        "margin: 4px 8px; }" % c.border_soft,
        "QToolBar { background-color: %s; border: none; padding: 4px; "
        "spacing: 4px; }" % menu_bg,
        "QToolButton { background-color: transparent; border: none; "
        "border-radius: 6px; padding: 6px 10px; color: %s; }" % menu_fg,
        "QToolButton:hover { background-color: %s; }" % menu_sel,
        "QToolButton:checked { background-color: %s; }" % c.accent_container,
        "QStatusBar { background-color: %s; color: %s; "
        "border-top: 1px solid %s; }" % (menu_bg, menu_fg, c.border),
        "QStatusBar::item { border: none; }",
        "QTabBar::tab { background-color: %s; color: %s; padding: 8px 16px; "
        "margin-right: 2px; border-top-left-radius: 6px; "
        "border-top-right-radius: 6px; }" % (c.bg_panel_alt, c.fg_muted),
        "QTabBar::tab:selected { background-color: %s; color: %s; }" % (
            c.bg_panel, c.fg_text),
        "QTabBar::tab:hover { background-color: %s; }" % menu_sel,
        "QTableView { gridline-color: %s; background-color: %s; "
        "alternate-background-color: %s; color: %s; "
        "selection-background-color: %s; selection-color: %s; "
        "border: 1px solid %s; border-radius: 4px; }" % (
            c.border_soft, c.table_row, c.table_row_alt, c.fg_text,
            c.table_selected, c.table_selected_fg, c.border_soft),
        "QTableView::item { padding: 4px; border: none; }",
        "QTableView QLineEdit, QTableView QComboBox { border: 1px solid %s; "
        "border-radius: 2px; padding: 1px 6px; margin: 0; min-height: 0; }" % (
            c.accent),
        "QHeaderView::section { background-color: %s; color: %s; padding: 8px; "
        "border: none; border-bottom: 2px solid %s; border-right: 1px solid %s; "
        "font-weight: 600; }" % (c.table_header, c.fg_text, c.border,
                                 c.border_soft),
        "QLineEdit, QTextEdit, QPlainTextEdit { background-color: %s; "
        "color: %s; border: 1px solid %s; border-radius: 6px; padding: 8px; "
        "selection-background-color: %s; }" % (
            c.input, c.fg_text, c.border, c.accent_container),
        "QLineEdit:focus, QTextEdit:focus { border: 2px solid %s; }" % c.accent,
        "QComboBox { background-color: %s; color: %s; border: 1px solid %s; "
        "border-radius: 6px; padding: 8px; min-height: 24px; }" % (
            c.input, c.fg_text, c.border),
        "QComboBox:hover { border-color: %s; }" % c.accent,
        "QComboBox::drop-down { border: none; width: 24px; }",
        "QComboBox QAbstractItemView { background-color: %s; color: %s; "
        "border: 1px solid %s; selection-background-color: %s; "
        "selection-color: %s; }" % (c.bg_panel, c.fg_text, c.border_soft,
                                    c.accent, c.fg_text),
        "QPushButton { background-color: %s; color: %s; border: none; "
        "border-radius: 6px; padding: 8px 16px; font-weight: 500; }" % (
            c.bg_panel_alt, c.fg_text),
        "QPushButton:hover { background-color: %s; }" % menu_sel,
        "QPushButton:pressed { background-color: %s; }" % c.accent_container,
        "QPushButton[accent=\"true\"] { background-color: %s; color: %s; }" % (
            c.accent, c.fg_text),
        "QPushButton[accent=\"true\"]:hover { background-color: %s; }" % (
            c.accent_hover),
        "QLabel { color: %s; }" % c.fg_text,
        "QLabel[muted=\"true\"] { color: %s; }" % c.fg_muted,
        "QLabel[heading=\"true\"] { font-size: 20px; font-weight: 700; "
        "color: %s; }" % c.fg_text,
        "QCheckBox { color: %s; spacing: 8px; }" % c.fg_text,
        "QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; "
        "border: 1px solid %s; }" % c.border,
        "QCheckBox::indicator:checked { background-color: %s; "
        "border-color: %s; }" % (c.accent, c.accent),
        "QSpinBox, QDoubleSpinBox { background-color: %s; color: %s; "
        "border: 1px solid %s; border-radius: 6px; padding: 6px; }" % (
            c.input, c.fg_text, c.border),
        "QProgressBar { background-color: %s; border: none; "
        "border-radius: 4px; text-align: center; color: %s; height: 12px; }" % (
            c.bg_panel_alt, c.fg_muted),
        "QProgressBar::chunk { background-color: %s; border-radius: 4px; }" % (
            c.accent),
        "QScrollBar:vertical { background-color: %s; width: 12px; "
        "border: none; }" % c.bg_panel,
        "QScrollBar::handle:vertical { background-color: %s; "
        "border-radius: 6px; min-height: 30px; }" % c.border,
        "QScrollBar::handle:vertical:hover { background-color: %s; }" % (
            c.accent),
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { "
        "height: 0; }",
        "QScrollBar:horizontal { background-color: %s; height: 12px; "
        "border: none; }" % c.bg_panel,
        "QScrollBar::handle:horizontal { background-color: %s; "
        "border-radius: 6px; min-width: 30px; }" % c.border,
        "QScrollBar::handle:horizontal:hover { background-color: %s; }" % (
            c.accent),
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { "
        "width: 0; }",
        "QSplitter::handle { background-color: %s; }" % c.border_soft,
        "QSplitter::handle:hover { background-color: %s; }" % c.accent,
        "QSplitter::handle:vertical { height: 2px; }",
        "QSplitter::handle:horizontal { width: 2px; }",
        "QGroupBox { border: 1px solid %s; border-radius: 8px; "
        "margin-top: 12px; padding-top: 12px; color: %s; }" % (
            c.border_soft, c.fg_text),
        "QGroupBox::title { subcontrol-origin: margin; left: 12px; "
        "padding: 0 6px; font-weight: 600; }",
        "QDialogButtonBox QPushButton { min-width: 96px; "
        "padding: 8px 20px; }",
        "QMessageBox QPushButton { min-width: 96px; padding: 8px 20px; }",
        "QMessageBox { background-color: %s; }" % c.bg_panel,
        "QMessageBox QLabel { color: %s; }" % c.fg_text,
    ]
    return "\n".join(lines)


def apply_theme(app: QApplication, dark: bool):
    """Apply palette + stylesheet globally."""
    app.setPalette(build_palette(dark))
    app.setStyleSheet(build_stylesheet(dark))
    # Readable default: +1pt over the platform font
    app_font = app.font()
    app_font.setPointSize(app_font.pointSize() + 1)
    app.setFont(app_font)
