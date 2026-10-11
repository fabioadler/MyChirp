import sys

import flet as ft

from mychirp import CHIRP_VERSION
from mychirp.fletui.theme import (
    BORDER_RADIUS,
    SPACING,
    AppColors,
)
from mychirp.fletui.i18n import _



class AboutDialog(ft.AlertDialog):
    """About dialog with MyChirp branding, credits and company logo.

    Layout (matching the wxui implementation):
      [MyChirp logo] MyChirp <version> (based on CHIRP)
      [Original project: CHIRP Project + link]
      [MyChirp version by Fábio Adler de Luna Gomes]
      [Empresa: company logo]
      [Python / Flet info] [docs] [license]
    """

    DEVELOPER = "Fábio Adler de Luna Gomes"

    def __init__(self, page: ft.Page, state):
        super().__init__(modal=True)
        self._page = page
        self.state = state
        self._build()

    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel

        self.title = ft.Text(_("About MyChirp"), color=p.fg_text,
                             weight=ft.FontWeight.BOLD)

        def section_box(child):
            return ft.Container(
                padding=ft.Padding.all(SPACING.MD),
                bgcolor=p.bg_panel_alt,
                border_radius=BORDER_RADIUS["md"],
                border=ft.Border.all(color=p.border_soft, width=1),
                content=child)

        self.content = ft.Container(
            width=420,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                spacing=SPACING.MD,
                tight=True,
                controls=[
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding.only(top=SPACING.SM),
                        content=ft.Image(
                            src="mychirp_logo_transparente.png",
                            width=120, height=120,
                            fit=ft.BoxFit.CONTAIN),
                    ),
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                        controls=[
                            ft.Text(
                                "MyChirp %s" % CHIRP_VERSION,
                                size=18, weight=ft.FontWeight.BOLD,
                                color=p.fg_text),
                            ft.Text(
                                _("Based on the CHIRP project"),
                                size=12, color=p.fg_muted),
                        ]),
                    section_box(ft.Column(
                        spacing=SPACING.XS,
                        controls=[
                            ft.Text(
                                _("Original project"),
                                size=11, weight=ft.FontWeight.BOLD,
                                color=p.accent),
                            ft.Text(
                                "CHIRP Project — chirpmyradio.com",
                                size=13, color=p.fg_text),
                            ft.Text(
                                "Copyright Dan Smith and CHIRP "
                                "contributors, GPLv3",
                                size=11, color=p.fg_muted),
                        ])),
                    section_box(ft.Column(
                        spacing=SPACING.XS,
                        controls=[
                            ft.Text(
                                _("MyChirp version"),
                                size=11, weight=ft.FontWeight.BOLD,
                                color=p.accent),
                            ft.Text(
                                _("Developed/modified by: %s")
                                % self.DEVELOPER,
                                size=13, color=p.fg_text),
                        ])),
                    ft.Container(
                        alignment=ft.Alignment.CENTER,
                        content=ft.Image(
                            src="logo_empresa.png",
                            width=100,
                            fit=ft.BoxFit.CONTAIN),
                    ),
                    ft.Text(
                        "Python %s.%s.%s · Flet"
                        % (sys.version_info.major,
                           sys.version_info.minor,
                           sys.version_info.micro),
                        size=11, color=p.fg_muted,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=SPACING.LG,
                        controls=[
                            ft.TextButton(
                                _("Documentation"),
                                url=(
                                    "https://chirpmyradio.com/"
                                    "projects/chirp/wiki/"
                                    "Documentation")),
                            ft.TextButton(
                                _("License GPLv3"),
                                url=(
                                    "https://www.gnu.org/licenses/"
                                    "gpl-3.0.html")),
                        ]),
                ]))

        self.actions = [
            ft.FilledButton(_("OK"), on_click=lambda e: self._page.close(self)),
        ]
        self.actions_alignment = ft.MainAxisAlignment.CENTER
