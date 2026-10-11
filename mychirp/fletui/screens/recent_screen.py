import os
import time

import flet as ft

from mychirp.fletui.theme import (
    BORDER_RADIUS,
    SPACING,
    AppColors,
)
from mychirp.fletui.i18n import _

_FILE_ICON = ft.Icons.SETTINGS_INPUT_ANTENNA


class RecentFileCard(ft.Container):
    """One recent-file entry: icon, name, path and last-modified."""

    def __init__(self, page, state, filename, on_open):
        super().__init__()
        self._page = page
        self._filename = filename
        p = AppColors.for_mode(state.is_dark())
        base = os.path.basename(filename)
        dirname = os.path.dirname(filename) or filename
        try:
            stamp = os.path.getmtime(filename)
            modified = time.strftime("%d/%m/%Y %H:%M", time.localtime(stamp))
            size = os.path.getsize(filename) // 1024
            extra = _("%s · %i KB") % (modified, size)
        except OSError:
            extra = _("file not found")

        self.bgcolor = p.bg_panel
        self.border = ft.Border.all(1, p.border_soft)
        self.border_radius = BORDER_RADIUS["md"]
        self.padding = ft.Padding.all(SPACING.MD)
        self.ink = True
        self.on_click = lambda e: on_open(filename)
        self.content = ft.Row(
            spacing=SPACING.MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(_FILE_ICON, size=28, color=p.accent),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text(
                            base, size=14, weight=ft.FontWeight.W_600,
                            color=p.fg_text,
                            overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            dirname, size=11, color=p.fg_muted,
                            overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(extra, size=10, color=p.fg_muted),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.OPEN_IN_NEW,
                    icon_size=18,
                    icon_color=p.fg_muted,
                    tooltip=_("Open"),
                    on_click=lambda e: on_open(filename),
                ),
            ],
        )


class RecentFilesScreen(ft.Container):
    """Recent images tab: the last files opened by the user.

    Responsive themed list; each entry reopens the radio with one
    click. Follows the active theme on every mode change.
    """

    def __init__(self, page: ft.Page, state):
        super().__init__()
        self._page = page
        self.state = state
        self.expand = True
        self._build()

    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel
        self.border_radius = BORDER_RADIUS["lg"]
        self.padding = ft.Padding.all(SPACING.LG)
        recents = self.state.get_recent_files()
        exists = [f for f in recents if os.path.exists(f)]

        if exists:
            cards = [
                ft.Container(
                    col={"xs": 12, "sm": 6, "md": 4},
                    content=RecentFileCard(
                        self._page, self.state, fn, self._on_open),
                )
                for fn in exists
            ]
            body = ft.ResponsiveRow(
                controls=cards,
                spacing=SPACING.MD,
                run_spacing=SPACING.MD,
            )
        else:
            body = ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=SPACING.MD,
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color=p.fg_muted),
                    ft.Text(
                        _("No recent files yet"),
                        size=15, color=p.fg_muted),
                    ft.Text(
                        _("Files you open will appear here"),
                        size=12, color=p.fg_muted),
                ],
            )

        self.content = ft.Column(
            expand=True,
            spacing=SPACING.LG,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text(
                            _("Recent files"),
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=p.fg_text),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            icon_color=p.fg_muted,
                            tooltip=_("Refresh"),
                            on_click=lambda e: self.refresh(),
                        ),
                    ],
                ),
                ft.Divider(color=p.border_soft),
                body,
            ],
        )

    def _on_open(self, filename):
        if self.state.shell:
            self.state.shell.open_file(filename)

    def refresh(self):
        self._build()
        try:
            self.update()
        except (AssertionError, RuntimeError):
            pass

    def apply_theme(self):
        self.refresh()
