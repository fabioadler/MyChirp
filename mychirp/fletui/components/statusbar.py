import flet as ft

from mychirp.fletui.theme import (
    BORDER_RADIUS,
    SPACING,
    AppColors,
)


class StatusBar(ft.Container):
    """Themed 3-field status bar (message | radio | modified).

    Follows the active theme on every mode change, fixing the old
    "white status bar" issue from the wxui.
    """

    def __init__(self, page: ft.Page, state):
        super().__init__()
        self._page = page
        self.state = state
        self.field_message = ft.Text(
            "", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS,
            expand=True)
        self.field_radio = ft.Text(
            "", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
        self.field_modified = ft.Text(
            "", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
        self.expand = False
        self._build()

    def _build(self):
        p = self.state_palette()
        self.height = 30
        self.padding = ft.Padding.symmetric(horizontal=SPACING.MD)
        self.bgcolor = p.bg_panel_alt
        self.border = ft.Border(
            top=ft.BorderSide(color=p.border, width=1),
            bottom=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            left=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            right=ft.BorderSide(0, ft.Colors.TRANSPARENT),
        )
        self.content = ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.INFO_OUTLINE, size=14, color=p.fg_muted),
                self.field_message,
                ft.VerticalDivider(
                    width=1, thickness=1, color=p.border_soft),
                ft.Icon(
                    ft.Icons.SETTINGS_INPUT_ANTENNA,
                    size=14, color=p.fg_muted),
                self.field_radio,
                ft.VerticalDivider(
                    width=1, thickness=1, color=p.border_soft),
                ft.Icon(
                    ft.Icons.SAVE_OUTLINED, size=14, color=p.fg_muted),
                self.field_modified,
            ],
            spacing=SPACING.SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._apply_text_colors(p)

    def state_palette(self):
        return AppColors.for_mode(self.state.is_dark())

    def _apply_text_colors(self, p):
        for field in (self.field_message, self.field_radio,
                      self.field_modified):
            field.color = p.fg_muted

    def apply_theme(self):
        self._build()
        try:
            self.update()
        except AssertionError:
            pass

    def set_status(self, message: str, field: int = 0):
        fields = (
            self.field_message, self.field_radio, self.field_modified)
        if 0 <= field < len(fields):
            fields[field].value = message
            try:
                self.update()
            except AssertionError:
                pass
