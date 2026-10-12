import logging

import flet as ft

from mychirp.fletui.services.app_state import EditorSetState
from mychirp.fletui.services.radio_service import (
    get_service,
    list_serial_ports,
    list_vendors,
    list_models,
    model_label_to_class,
)
from mychirp.fletui.theme import (
    BORDER_RADIUS,
    SPACING,
    AppColors,
)
from mychirp.fletui.i18n import _

LOG = logging.getLogger(__name__)


class CloneDialog(ft.AlertDialog):
    """Modern clone dialog: Vendor → Model → Port, with progress.

    Mirrors the original CHIRP clone dialog layout (Port, Vendor,
    Model fields) restyled with the MyChirp design tokens.
    """

    def __init__(self, page: ft.Page, state, mode: str, eset=None):
        super().__init__(modal=True)
        self._page = page
        self.state = state
        self.mode = mode  # "download" | "upload"
        self.eset = eset
        self._vendors = list_vendors()
        self._models = []
        self._ports = list_serial_ports()
        self._build()

    # ----- layout -----
    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel
        downloading = self.mode == "download"

        if downloading:
            title = _("Download from radio")
            icon = ft.Icons.SETTINGS_INPUT_ANTENNA
        else:
            title = _("Upload to radio")
            icon = ft.Icons.BACKUP

        self.title = ft.Container(
            bgcolor=p.bg_panel_alt,
            border_radius=ft.BorderRadius.only(
                top_left=BORDER_RADIUS["lg"],
                top_right=BORDER_RADIUS["lg"]),
            padding=ft.Padding.symmetric(
                horizontal=SPACING.LG, vertical=SPACING.MD),
            content=ft.Row(
                spacing=SPACING.SM,
                controls=[
                    ft.Icon(icon, color=p.accent, size=24),
                    ft.Column(
                        spacing=0,
                        tight=True,
                        controls=[
                            ft.Text(title, color=p.fg_text,
                                    weight=ft.FontWeight.BOLD, size=17),
                            ft.Text(
                                _("Clone radio settings") if downloading
                                else _("Write settings back to radio"),
                                size=11, color=p.fg_muted),
                        ]),
                ]))

        input_common = dict(
            bgcolor=p.input,
            border=ft.Border.all(1, p.border),
            border_radius=BORDER_RADIUS["md"],
            text_style=ft.TextStyle(color=p.fg_text, size=13),
            dense=True,
        )

        def section(text, icon):
            return ft.Row(
                spacing=SPACING.SM,
                controls=[
                    ft.Icon(icon, size=14, color=p.fg_muted),
                    ft.Text(text, size=12, weight=ft.FontWeight.BOLD,
                            color=p.fg_muted,
                            ),
                ])

        self.vendor_dd = ft.Dropdown(
            label=_("Vendor"),
            options=[ft.dropdown.Option(v) for v in self._vendors],
            on_select=self._on_vendor,
            **input_common)
        self.model_dd = ft.Dropdown(
            label=_("Model"),
            options=[],
            on_select=self._on_model,
            **input_common)
        self.port_dd = ft.Dropdown(
            label=_("Port"),
            options=[ft.dropdown.Option(pt) for pt in self._ports],
            **input_common)

        if not downloading and self.eset:
            # Upload uses the current radio model; lock the fields
            vendor = getattr(self.eset.radio, "VENDOR", "")
            model = getattr(self.eset.radio, "MODEL", "")
            self.vendor_dd.value = vendor
            self.vendor_dd.disabled = True
            self._models = list_models(vendor)
            self.model_dd.options = [
                ft.dropdown.Option(m) for m in self._models]
            want = "%s %s" % (model, getattr(
                self.eset.radio, "VARIANT", "") or "")
            want = want.strip()
            if want in self._models:
                self.model_dd.value = want
            self.model_dd.disabled = True
            # Still pre-fill the last used port
            port = self.state.conf.get("clone_last_port", "state") or ""
            if port and port in self._ports:
                self.port_dd.value = port
        elif downloading:
            # Restore the last used vendor/model/port
            self._load_last_selection()

        self.progress = ft.ProgressBar(
            value=0, color=p.accent,
            bgcolor=p.bg_panel_alt,
            border_radius=BORDER_RADIUS["full"],
            visible=False)
        self.progress_label = ft.Text(
            "", size=12, color=p.fg_muted, visible=False,
            overflow=ft.TextOverflow.ELLIPSIS)

        # Vertical column layout (form-style, one field per row)
        self.content = ft.Container(
            width=420,
            content=ft.Column(
                spacing=SPACING.LG,
                tight=True,
                controls=[
                    ft.Column(
                        spacing=SPACING.MD,
                        tight=True,
                        controls=[
                            *([section(_("Radio"), ft.Icons.RADIO),
                                self.vendor_dd,
                                self.model_dd]
                              if downloading else []),
                            section(_("Connection"),
                                    ft.Icons.SETTINGS_INPUT_COMPONENT),
                            self.port_dd,
                        ]),
                    self.progress,
                    self.progress_label,
                ],
            ))

        self.start_btn = ft.FilledButton(
            icon=(
                ft.Icons.DOWNLOADING
                if downloading else ft.Icons.UPLOAD),
            content=title,
            on_click=self._on_start,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS["md"]),
                padding=ft.Padding.symmetric(
                    horizontal=SPACING.LG, vertical=SPACING.MD),
            ))
        self.actions = [
            ft.TextButton(_("Cancel"), on_click=self._close),
            self.start_btn,
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    # ----- handlers -----
    def _on_vendor(self, e):
        vendor = e.control.value
        if not vendor:
            return
        self._models = list_models(vendor)
        self.model_dd.options = [
            ft.dropdown.Option(m) for m in self._models]
        self.model_dd.value = None
        if self._page:
            self.model_dd.update()

    def _on_model(self, e):
        if self._page:
            self.model_dd.update()

    # ----- last selection persistence -----
    def _load_last_selection(self):
        """Pre-fill vendor/model/port from the last successful clone."""
        conf = self.state.conf
        vendor = conf.get("clone_last_vendor", "state") or ""
        model = conf.get("clone_last_model", "state") or ""
        port = conf.get("clone_last_port", "state") or ""
        if vendor and vendor in self._vendors:
            self.vendor_dd.value = vendor
            self._models = list_models(vendor)
            self.model_dd.options = [
                ft.dropdown.Option(m) for m in self._models]
            if model and model in self._models:
                self.model_dd.value = model
        if port and port in self._ports:
            self.port_dd.value = port

    def _save_last_selection(self):
        conf = self.state.conf
        if self.mode == "download":
            if self.vendor_dd.value:
                conf.set("clone_last_vendor", self.vendor_dd.value,
                         "state")
            if self.model_dd.value:
                conf.set("clone_last_model", self.model_dd.value, "state")
        if self.port_dd.value:
            conf.set("clone_last_port", self.port_dd.value, "state")
        conf.save()

    def _close(self, e=None):
        self._page.pop_dialog()

    def _validate(self):
        if self.mode == "download":
            if not self.vendor_dd.value:
                return _("Select a vendor")
            if not self.model_dd.value:
                return _("Select a model")
        if not self.port_dd.value:
            return _("Select a port")
        return None

    def _on_start(self, e):
        error = self._validate()
        if error:
            self.progress_label.value = error
            self.progress_label.color = AppColors.for_mode(
                self.state.is_dark()).error
            self.progress_label.visible = True
            self._page.update()
            return

        service = get_service(self._page)
        port = self.port_dd.value

        if self.mode == "download":
            vendor = self.vendor_dd.value
            rclass = model_label_to_class(vendor, self.model_dd.value)
            if rclass is None:
                self.progress_label.value = _("Model not found")
                self._page.update()
                return
            self._save_last_selection()
            self._start_ui()
            service.download_radio(
                rclass, port,
                on_done=self._download_done,
                on_progress=self._on_progress)
        else:
            self._save_last_selection()
            self._start_ui()
            service.upload_radio(
                self.eset.radio, port,
                on_done=self._upload_done,
                on_progress=self._on_progress)

    def _start_ui(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.start_btn.disabled = True
        self.progress.visible = True
        self.progress.color = (
            p.accent_download if self.mode == "download"
            else p.accent_upload)
        self.progress_label.visible = True
        self.progress_label.color = p.fg_muted
        self.progress_label.value = (
            _("Communicating with radio..."))
        self._page.update()

    def _on_progress(self, status):
        try:
            self.progress.value = (
                status.cur / status.max) if status.max else 0
            self.progress_label.value = status.msg or ""
        except Exception:
            pass
        if self._page:
            self._page.update()

    def _download_done(self, job):
        self.progress.visible = False
        self.start_btn.disabled = False
        if job.error:
            self.progress_label.value = str(job.error)
            self.progress_label.color = AppColors.for_mode(
                self.state.is_dark()).error
            self._page.update()
            return
        radio = job.result
        base = "%s_%s" % (getattr(radio, "VENDOR", "Radio"),
                          getattr(radio, "MODEL", ""))
        filename = "%s.img" % base.replace(" ", "_")
        eset = EditorSetState(radio, filename)
        self.state.add_editorset(eset)
        self.state.set_status(
            _("Downloaded %s") % eset.radio_label)
        self._close()

    def _upload_done(self, job):
        self.progress.visible = False
        self.start_btn.disabled = False
        if job.error:
            self.progress_label.value = str(job.error)
            self.progress_label.color = AppColors.for_mode(
                self.state.is_dark()).error
            self._page.update()
            return
        self.state.set_status(_("Upload complete"))
        self._close()
