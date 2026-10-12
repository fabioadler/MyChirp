import logging

import flet as ft

from mychirp import settings as chirp_settings
from mychirp.fletui.services.radio_service import get_service
from mychirp.fletui.theme import (
    BORDER_RADIUS,
    BREAKPOINT_MD,
    SPACING,
    AppColors,
)
from mychirp.fletui.i18n import _

LOG = logging.getLogger(__name__)


class SettingsScreen(ft.Container):
    """Settings editor: responsive side navigation + themed forms.

    Wide layout uses a NavigationRail on the left (like the wxui
    Treebook); narrow layout collapses it into a Dropdown.
    """

    def __init__(self, page: ft.Page, state, eset):
        super().__init__()
        self._page = page
        self.state = state
        self.eset = eset
        self.groups: list = []
        self.current_group = None
        self._group_fields: dict[str, list] = {}
        self.expand = True
        self._build()

    # ----- layout -----
    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel
        self.border_radius = BORDER_RADIUS["lg"]
        self.loading = ft.Container(
            expand=True, alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(color=p.accent))
        self.content = self.loading
        self._wide = (self._page.width or 0) >= BREAKPOINT_MD
        if self.groups:
            self._render_groups()

    def _render_groups(self):
        p = AppColors.for_mode(self.state.is_dark())
        if not self.groups:
            self.content = self._empty_state(p)
            return

        group_labels = [g.get_shortname() for g in self.groups]
        selected = 0
        if self.current_group:
            for i, g in enumerate(self.groups):
                if g is self.current_group:
                    selected = i
                    break
            else:
                self.current_group = self.groups[0]
        else:
            self.current_group = self.groups[0]

        self.rail = ft.NavigationRail(
            selected_index=selected,
            label_type=ft.NavigationRailLabelType.ALL,
            bgcolor=p.bg_panel_alt,
            extended=True,
            min_width=210,
            min_extended_width=230,
            group_alignment=-0.9,
            indicator_shape=ft.RoundedRectangleBorder(
                radius=BORDER_RADIUS["sm"]),
            on_change=self._on_rail_change,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                            label=label,
                )
                for label in group_labels
            ],
        )

        self.mobile_group_selector = ft.Dropdown(
            value=group_labels[selected] if group_labels else None,
            options=[
                ft.dropdown.Option(i, label)
                for i, label in enumerate(group_labels)
            ],
            bgcolor=p.input,
            border=ft.Border.all(1, p.border),
            border_radius=BORDER_RADIUS["sm"],
            text_style=ft.TextStyle(color=p.fg_text, size=13),
            dense=True,
            on_select=self._on_mobile_select,
        )

        self.group_body = ft.Container(
            expand=True,
            padding=ft.Padding.all(SPACING.LG),
            content=self._group_content(self.current_group),
        )

        wide = (self._page.width or 0) >= BREAKPOINT_MD
        if wide:
            self.content = ft.Row(
                expand=True,
                controls=[
                    self.rail,
                    ft.VerticalDivider(
                        width=1, thickness=1, color=p.border),
                    self.group_body,
                ],
                spacing=0,
            )
        else:
            self.content = ft.Column(
                expand=True,
                spacing=SPACING.MD,
                controls=[
                    ft.Container(
                        padding=ft.Padding.all(SPACING.MD),
                        content=self.mobile_group_selector),
                    self.group_body,
                ],
            )

    def _empty_state(self, p):
        return ft.Container(
            expand=True, alignment=ft.Alignment.CENTER,
            content=ft.Text(
                _("No settings available"), color=p.fg_muted))

    def _group_content(self, group) -> ft.Control:
        p = AppColors.for_mode(self.state.is_dark())
        fields = self._group_fields.setdefault(id(group), [])
        fields.clear()

        rows = []
        for element in group.values():
            if isinstance(element, chirp_settings.RadioSettingGroup):
                rows.append(self._section_header(p, element))
                for sub in element.values():
                    if isinstance(sub, chirp_settings.RadioSetting):
                        rows.append(self._setting_row(p, sub))
            elif isinstance(element, chirp_settings.RadioSetting):
                rows.append(self._setting_row(p, element))

        apply_btn = ft.FilledButton(
            icon=ft.Icons.CHECK,
            content=_("Apply to radio"),
            on_click=self._on_apply,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS["md"]),
                padding=ft.Padding.symmetric(
                    horizontal=SPACING.LG, vertical=SPACING.MD),
            ),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=SPACING.SM,
            controls=[
                ft.Text(
                    group.get_shortname(),
                    size=20, weight=ft.FontWeight.BOLD, color=p.fg_text),
                ft.Divider(color=p.border_soft),
                *rows,
                ft.Container(height=SPACING.LG),
                ft.Row([apply_btn]),
                ft.Container(height=SPACING.XL),
            ],
        )

    def _section_header(self, p, group):
        return ft.Container(
            margin=ft.Margin.only(top=SPACING.MD),
            content=ft.Text(
                group.get_shortname(),
                size=13, weight=ft.FontWeight.BOLD,
                color=p.accent),
        )

    def _setting_row(self, p, setting):
        value = setting.value
        mutable = value.get_mutable()
        label = setting.get_shortname()
        control = self._control_for_value(p, value, mutable)

        doc = setting.__doc__
        return ft.Container(
            padding=ft.Padding.symmetric(vertical=SPACING.XS),
            content=ft.Row(
                spacing=SPACING.MD,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=200,
                        content=ft.Column(
                            spacing=0,
                            controls=[
                                ft.Text(
                                    label, size=13, color=p.fg_text,
                                    weight=ft.FontWeight.W_500),
                                *(
                                    [ft.Text(
                                        doc, size=10, color=p.fg_muted,
                                        no_wrap=False)]
                                    if doc else []),
                            ],
                        ),
                    ),
                    ft.Container(expand=True, content=control),
                ],
            ),
        )

    def _control_for_value(self, p, value, mutable):
        input_bg = p.input
        border = ft.Border.all(1, p.border)
        radius = ft.RoundedRectangleBorder(radius=BORDER_RADIUS["sm"])
        common = dict(
            bgcolor=input_bg, border=border, border_radius=radius,
            dense=True, expand=True, disabled=not mutable,
            text_style=ft.TextStyle(color=p.fg_text, size=13),
        )

        if isinstance(value, chirp_settings.RadioSettingValueBoolean):
            return ft.Switch(
                value=bool(value.get_value()),
                active_color=p.accent,
                disabled=not mutable,
                data=value,
            )
        if isinstance(value, chirp_settings.RadioSettingValueList):
            options = value.get_options()
            current = str(value.get_value())
            opts = [ft.dropdown.Option(str(o)) for o in options]
            if current not in [str(o) for o in options]:
                opts.append(ft.dropdown.Option(current))
            return ft.Dropdown(
                options=opts, value=current, data=value, **common)
        if isinstance(value, (
                chirp_settings.RadioSettingValueInteger,
                chirp_settings.RadioSettingValueFloat)):
            return ft.TextField(
                value=str(value.get_value()), data=value,
                keyboard_type=ft.KeyboardType.NUMBER, **common)
        if isinstance(value, chirp_settings.RadioSettingValueString):
            return ft.TextField(
                value=str(value.get_value()), data=value, **common)
        # Unknown value type: read-only text
        return ft.TextField(
            value=str(value.get_value()), read_only=True,
            bgcolor=input_bg, border=border, border_radius=radius,
            dense=True, expand=True, disabled=True,
            text_style=ft.TextStyle(color=p.fg_muted, size=13))

    # ----- data -----
    def load_settings(self):
        service = get_service(self._page)
        self.state.set_status(_("Reading settings..."))

        def done(job):
            if job.error:
                self.state.set_status(_("Failed to read settings"))
                LOG.exception("settings load failed: %s", job.error)
                self.groups = []
                self._build()
                try:
                    self.update()
                except (AssertionError, RuntimeError):
                    pass
                return
            try:
                self._parse_settings(job.result)
            except Exception:
                LOG.exception("Failed parsing settings")
                self.groups = []
            self.state.set_status(_("Settings loaded"))
            self._build()
            try:
                self.update()
            except (AssertionError, RuntimeError):
                pass

        service.load_settings(self.eset.radio, done)

    def _parse_settings(self, result):
        """Flatten RadioSettings into top-level groups list."""
        self.groups = []
        if result is None:
            return
        for group in result:
            self.groups.append(group)

    def _collect_values(self):
        """Read control values back into the RadioSetting objects."""
        for fields in self._group_fields.values():
            for control in fields:
                value = control.data
                try:
                    if isinstance(control, ft.Switch):
                        value.set_value(bool(control.value))
                    elif control.value is not None:
                        value.set_value(control.value)
                except Exception as e:
                    LOG.debug("set failed: %s", e)

    def _walk_controls(self, container):
        """Yield all input controls of the current group body."""
        result = []
        stack = [container]
        while stack:
            node = stack.pop()
            if isinstance(node, (ft.Switch, ft.Dropdown, ft.TextField)):
                result.append(node)
            children = getattr(node, "controls", None) or \
                getattr(node, "content", None)
            if isinstance(children, list):
                stack.extend(children)
            elif children is not None:
                stack.append(children)
            col = getattr(node, "columns", None)
            if col:
                stack.extend(col)
        return result

    def _on_apply(self, e):
        self._collect_values()
        service = get_service(self._page)
        self.state.set_status(_("Applying settings..."))

        def done(job):
            if job.error:
                self.state.set_status(_("Failed to apply settings"))
                self._apply_error(job.error)
            else:
                self.eset.modified = True
                self.state.set_status(_("Settings applied"))

        service.save_settings(
            self.eset.radio, self._settings_object(), done)

    def _settings_object(self):
        return self.groups

    def _apply_error(self, error):
        p = AppColors.for_mode(self.state.is_dark())
        dlg = ft.AlertDialog(
            title=ft.Text(_("Error applying settings"),
                          color=p.fg_text),
            content=ft.Text(str(error), color=p.fg_muted),
            actions=[ft.TextButton(
                _("OK"), on_click=lambda e: self._page.pop_dialog())],
        )
        self._page.show_dialog(dlg)

    # ----- navigation -----
    def _on_rail_change(self, e):
        index = e.control.selected_index
        if 0 <= index < len(self.groups):
            self.current_group = self.groups[index]
            p = AppColors.for_mode(self.state.is_dark())
            self.group_body.content = self._group_content(
                self.current_group)
            try:
                self.update()
            except (AssertionError, RuntimeError):
                pass

    def _on_mobile_select(self, e):
        try:
            index = int(e.control.value)
        except (TypeError, ValueError):
            return
        if 0 <= index < len(self.groups):
            self.current_group = self.groups[index]
            self.group_body.content = self._group_content(
                self.current_group)
            try:
                self.update()
            except (AssertionError, RuntimeError):
                pass

    # ----- theme -----
    def apply_theme(self):
        self._build()
        if self.groups and self.current_group:
            p = AppColors.for_mode(self.state.is_dark())
            self.group_body.content = self._group_content(
                self.current_group)
        try:
            self.update()
        except (AssertionError, RuntimeError):
            pass
