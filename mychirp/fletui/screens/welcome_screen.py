import flet as ft

from mychirp.fletui.theme import (
    BORDER_RADIUS,
    SPACING,
    WELCOME_LOGO_SIZE,
    AppColors,
)

_ = lambda s: s


class WelcomeScreen(ft.Container):
    """Welcome splash: centered logo sized to at most 400px.

    Follows the active theme background (no more hardcoded dark
    background / oversized stretched logo).
    """

    def __init__(self, page: ft.Page, state):
        super().__init__()
        self._page = page
        self.state = state
        self.expand = True
        self._build()

    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_window

        logo_size = WELCOME_LOGO_SIZE
        self.content = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=SPACING.LG,
                controls=[
                    ft.Container(
                        content=ft.Image(
                            src="logo_mychirp.png",
                            width=logo_size,
                            height=logo_size,
                            fit=ft.BoxFit.CONTAIN,
                        ),
                        padding=SPACING.XL,
                    ),
                    ft.Text(
                        _("MyChirp"),
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        color=p.fg_text,
                    ),
                    ft.Text(
                        _("Modern radio programming software"),
                        size=14,
                        color=p.fg_muted,
                    ),
                    ft.Container(height=SPACING.SM),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=SPACING.LG,
                        controls=[
                            self._action_button(
                                p, ft.Icons.FILE_OPEN_OUTLINED,
                                _("Open file"),
                                self._on_open),
                            self._action_button(
                                p, ft.Icons.SETTINGS_INPUT_ANTENNA,
                                _("Download from radio"),
                                self._on_download),
                        ],
                    ),
                    ft.Container(height=SPACING.SM),
                    ft.Container(
                        padding=ft.Padding.symmetric(
                            horizontal=SPACING.XL, vertical=SPACING.SM),
                        bgcolor=p.bg_panel,
                        border_radius=BORDER_RADIUS["lg"],
                        border=ft.Border.all(
                            color=p.border_soft, width=1),
                        content=ft.Row(
                            spacing=SPACING.SM,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(
                                    ft.Icons.TIPS_AND_UPDATES_OUTLINED,
                                    size=16, color=p.fg_muted),
                                ft.Text(
                                    _("Use File > Open or Ctrl+D to "
                                      "download from a radio"),
                                    size=12, color=p.fg_muted),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _action_button(self, p, icon, label, on_click):
        return ft.FilledButton(content=label,
            icon=icon,
            on_click=on_click,
            style=ft.ButtonStyle(
                bgcolor=p.accent,
                color=ft.Colors.WHITE
                if not self.state.is_dark() else "#10231B",
                shape=ft.RoundedRectangleBorder(
                    radius=BORDER_RADIUS["md"]),
                padding=ft.Padding.symmetric(
                    horizontal=SPACING.LG, vertical=SPACING.MD),
            ),
        )

    def _on_open(self, e):
        if self.state.shell:
            self.state.shell.pick_open()

    def _on_download(self, e):
        if self.state.shell:
            self.state.shell.download_from_radio()

    def apply_theme(self):
        self._build()
        try:
            self.update()
        except AssertionError:
            pass
