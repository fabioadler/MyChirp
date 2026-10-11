import logging

import flet as ft

from mychirp import chirp_common
from mychirp.fletui.services.radio_service import get_service
from mychirp.fletui.theme import (
    BORDER_RADIUS,
    MEMORIES_PAGE_SIZE,
    SPACING,
    AppColors,
)

LOG = logging.getLogger(__name__)
_ = lambda s: s


def _visible_columns(features) -> list[str]:
    """Determine which memory columns this radio supports."""
    checks = {
        "freq": True,
        "name": lambda: getattr(features, "has_name", False),
        "tmode": lambda: bool(getattr(features, "valid_tmodes", None)),
        "rtone": lambda: bool(getattr(features, "valid_tones", None)),
        "ctone": lambda: bool(getattr(features, "valid_tones", None)),
        "dtcs": lambda: bool(getattr(features, "valid_dtcs_codes", None)),
        "duplex": lambda: bool(getattr(features, "valid_duplexes", None)),
        "offset": lambda: getattr(features, "has_offset", True),
        "mode": lambda: bool(getattr(features, "valid_modes", None)),
        "tuning_step": lambda: bool(
            getattr(features, "valid_tuning_steps", None)),
        "skip": lambda: bool(getattr(features, "valid_skips", None)),
        "power": lambda: bool(
            getattr(features, "valid_power_levels", None)
        ) or getattr(features, "has_variable_power", False),
        "comment": lambda: getattr(features, "has_comment", False),
    }
    result = []
    for name, check in checks.items():
        try:
            ok = check() if callable(check) else check
        except Exception:
            ok = False
        if ok:
            result.append(name)
    return result


COLUMN_LABELS = {
    "loc": _("Loc"),
    "freq": _("Frequency"),
    "name": _("Name"),
    "tmode": _("Tone Mode"),
    "rtone": _("Tone"),
    "ctone": _("ToneSql"),
    "dtcs": _("DTCS Code"),
    "duplex": _("Duplex"),
    "offset": _("Offset"),
    "mode": _("Mode"),
    "tuning_step": _("Tune Step"),
    "skip": _("Skip"),
    "power": _("Power"),
    "comment": _("Comment"),
}


def _render(name, mem) -> str:
    """Render a memory attribute for display."""
    if mem is None or mem.empty:
        return ""
    try:
        if name == "freq":
            return chirp_common.format_freq(mem.freq)
        if name == "offset":
            return chirp_common.format_freq(mem.offset)
        if name == "power":
            return str(mem.power) if mem.power else ""
        if name in ("rtone", "ctone"):
            return "%.1f" % getattr(mem, name)
        if name == "tuning_step":
            return "%.1f" % getattr(mem, name)
        return str(getattr(mem, name, ""))
    except Exception as e:
        LOG.debug("render %s failed: %s", name, e)
        return ""


class MemoryEditDialog(ft.AlertDialog):
    """Modal dialog to edit a single memory with typed controls."""

    def __init__(self, page, state, shell_view, mem, on_saved):
        super().__init__(modal=True)
        self._page = page
        self.state = state
        self.shell_view = shell_view
        self.mem = mem
        self.on_saved = on_saved
        self.fields = {}
        self._build()

    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel
        self.title = ft.Text(
            _("Edit Memory %s") % self._loc_label(), color=p.fg_text)
        self._content = ft.Container(
            width=420, height=420,
            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=SPACING.SM,
                              controls=self._build_fields(p)))
        self.content = self._content
        self.actions = [
            ft.TextButton(
                _("Cancel"), on_click=lambda e: self._page.close(self)),
            ft.FilledButton(
                _("Save"), on_click=self._on_save),
        ]

    def _loc_label(self):
        m = self.mem
        return m.extd_number if getattr(m, "extd_number", None) else m.number

    def _build_fields(self, p):
        features = self.shell_view.eset.features
        controls = []
        editable = not self.mem.immutable if hasattr(
            self.mem, "immutable") else True

        for name in self.shell_view.columns:
            if name not in ("rtone", "ctone") and name not in \
                    ("tmode", "duplex", "mode", "skip", "power",
                     "tuning_step", "dtcs"):
                if name in ("freq", "offset", "name", "comment",
                            "rtone", "ctone"):
                    pass
            value = _render(name, self.mem)
            label = COLUMN_LABELS.get(name, name.title())

            field = self._make_field(p, name, label, value, features)
            if field is not None:
                field.disabled = not editable
                self.fields[name] = field
                controls.append(
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=110,
                                content=ft.Text(
                                    label, size=12, color=p.fg_muted)),
                            field,
                        ],
                        spacing=SPACING.SM,
                    )
                )
        return controls

    def _make_field(self, p, name, label, value, features):
        input_bg = p.input
        border = ft.Border.all(1, p.border)
        radius = ft.RoundedRectangleBorder(radius=BORDER_RADIUS["sm"])

        def dropdown(options, current):
            opts = [ft.dropdown.Option(str(o)) for o in options]
            return ft.Dropdown(
                options=opts, value=current if current in [
                    str(o) for o in options] else None,
                bgcolor=input_bg, border=border, border_radius=radius,
                text_style=ft.TextStyle(color=p.fg_text, size=13),
                dense=True, expand=True)

        def textfield(current, keyboard=None, hint=None):
            return ft.TextField(
                value=current, bgcolor=input_bg, border=border,
                border_radius=radius, text_size=13,
                text_color=p.fg_text, dense=True, expand=True,
                keyboard_type=keyboard, hint_text=hint)

        try:
            if name == "freq":
                return textfield(value, ft.KeyboardType.NUMBER)
            if name == "offset":
                return textfield(value, ft.KeyboardType.NUMBER)
            if name in ("name", "comment"):
                return textfield(value)
            if name in ("rtone", "ctone"):
                return dropdown(
                    ["%.1f" % t for t in chirp_common.TONES], value)
            if name == "dtcs":
                return dropdown(
                    [str(c) for c in chirp_common.DTCS_CODES], value)
            if name == "tmode":
                return dropdown(features.valid_tmodes, value)
            if name == "duplex":
                return dropdown(features.valid_duplexes, value)
            if name == "mode":
                return dropdown(features.valid_modes, value)
            if name == "skip":
                return dropdown(features.valid_skips, value)
            if name == "tuning_step":
                return dropdown(
                    ["%.1f" % t for t in features.valid_tuning_steps], value)
            if name == "power":
                levels = getattr(features, "valid_power_levels", None)
                if levels:
                    return dropdown([str(l) for l in levels], value)
                return None
        except Exception:
            LOG.exception("Failed building field %s", name)
            return None
        return None

    def _parse(self, name, raw):
        """Convert the raw control value into the memory attribute."""
        if raw is None or raw == "":
            if name in ("rtone", "ctone"):
                return 88.5
            if name in ("freq", "offset"):
                return 0
            return ""
        if name == "freq":
            return chirp_common.parse_freq(raw)
        if name == "offset":
            return chirp_common.parse_freq(raw)
        if name in ("rtone", "ctone"):
            return float(raw)
        if name == "dtcs":
            return int(raw)
        if name == "tuning_step":
            return float(raw)
        return raw

    def _on_save(self, e):
        try:
            for name, field in self.fields.items():
                raw = field.value if field.value is not None else ""
                setattr(self.mem, name, self._parse(name, str(raw)))
        except ValueError as ve:
            p = AppColors.for_mode(self.state.is_dark())
            self.content = ft.Container(
                width=420, height=60,
                content=ft.Text(
                    _("Invalid value: %s") % ve, color=p.error))
            self._page.update()
            return

        service = get_service(self._page)

        def done(job):
            if job.error:
                self.state.set_status(_("Failed to save memory"))
            else:
                self.shell_view.eset.memories[self.mem.number] = self.mem
                self.shell_view.eset.modified = True
                self.shell_view.refresh_rows()
                self.state.set_status(
                    _("Memory %s updated") % self._loc_label())
                self.on_saved()
            self._page.close(self)

        service.set_memory(self.shell_view.eset.radio, self.mem, done)


class MemoriesScreen(ft.Container):
    """Paginated memory grid following the active theme."""

    def __init__(self, page: ft.Page, state, eset):
        super().__init__()
        self._page = page
        self.state = state
        self.eset = eset
        self.columns = ["loc"] + _visible_columns(eset.features)
        self.page_index = 0
        self.filter_text = ""
        self.hide_empty = False
        self._rows_cache = []
        self.expand = True
        self._build()

    # ----- layout -----
    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel
        self.border_radius = BORDER_RADIUS["lg"]

        self.search_field = ft.TextField(
            hint_text=_("Filter channels..."),
            prefix_icon=ft.Icons.SEARCH,
            bgcolor=p.input,
            border=ft.Border.all(1, p.border),
            border_radius=BORDER_RADIUS["sm"],
            text_size=13, text_color=p.fg_text, dense=True,
            on_submit=lambda e: self.apply_filter(),
        )
        self.hide_empty_switch = ft.Switch(
            label=_("Hide empty"),
            value=self.hide_empty,
            active_color=p.accent,
            label_style=ft.TextStyle(color=p.fg_muted, size=12),
            on_change=lambda e: self.toggle_hide_empty(),
        )
        self.table = self._build_table(p)
        self.pagination_info = ft.Text("", size=12, color=p.fg_muted)
        self._apply()

    def _build_table(self, p):
        headers = ft.DataRow(
            color=p.table_header,
            cells=[
                ft.DataCell(
                    ft.Text(
                        COLUMN_LABELS.get(col, col.title()),
                        size=12, weight=ft.FontWeight.BOLD,
                        color=p.fg_text))
                for col in self.columns
            ])
        # DataTable body is filled in refresh_rows()
        return ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text("")) for _ in self.columns
            ],
            rows=[],
            heading_row_height=40,
            data_row_min_height=38,
            data_row_max_height=38,
            border=ft.TableBorder.all(1, p.border_soft),
            border_radius=ft.BorderRadius(BORDER_RADIUS["md"]),
            horizontal_margin=SPACING.SM,
            column_spacing=SPACING.MD,
            expand=True,
        )

    def _apply(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.content = ft.Column(
            expand=True,
            spacing=SPACING.MD,
            controls=[
                ft.Row(
                    spacing=SPACING.MD,
                    controls=[
                        ft.Container(width=220, content=self.search_field),
                        self.hide_empty_switch,
                        ft.Container(expand=True),
                        self._page_button(p, ft.Icons.FIRST_PAGE,
                                          lambda: self._goto(0)),
                        self._page_button(p, ft.Icons.CHEVRON_LEFT,
                                          lambda: self._goto(
                                              self.page_index - 1)),
                        self.pagination_info,
                        self._page_button(p, ft.Icons.CHEVRON_RIGHT,
                                          lambda: self._goto(
                                              self.page_index + 1)),
                    ],
                ),
                ft.Container(
                    expand=True,
                    border_radius=BORDER_RADIUS["md"],
                    content=ft.Column(
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                        controls=[self.table]),
                ),
            ],
        )

    def _page_button(self, p, icon, handler):
        return ft.IconButton(
            icon=icon, icon_size=16, icon_color=p.fg_muted,
            bgcolor=p.bg_panel_alt,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS["sm"])),
            on_click=lambda e: handler(),
        )

    # ----- data -----
    def load_memories(self):
        service = get_service(self._page)
        self.state.set_status(_("Reading memories..."))

        def done(job):
            if job.error:
                self.state.set_status(_("Failed to read memories"))
                self._error(job.error)
                return
            self.eset.memories = job.result
            self.state.set_status(
                _("%i channels loaded") % len(job.result))
            self.refresh_rows()

        service.load_memories(self.eset.radio, done)

    def _filtered_rows(self):
        items = sorted(
            self.eset.memories.items(),
            key=lambda kv: (
                isinstance(kv[0], str), kv[0]))
        rows = []
        for number, mem in items:
            if self.hide_empty and mem.empty:
                continue
            if self.filter_text:
                haystack = " ".join(
                    _render(c, mem) for c in self.columns).lower()
                if self.filter_text.lower() not in haystack:
                    continue
            rows.append(mem)
        return rows

    def refresh_rows(self):
        p = AppColors.for_mode(self.state.is_dark())
        self._rows_cache = self._filtered_rows()
        total = len(self._rows_cache)
        pages = max(1, -(-total // MEMORIES_PAGE_SIZE))
        self.page_index = min(self.page_index, pages - 1)
        start = self.page_index * MEMORIES_PAGE_SIZE
        page_rows = self._rows_cache[start:start + MEMORIES_PAGE_SIZE]

        data_rows = []
        for i, mem in enumerate(page_rows):
            selected = False
            data_rows.append(self._make_row(p, mem, start + i))
        self.table.rows = data_rows
        self.pagination_info.value = _("%i-%i / %i") % (
            start + 1 if total else 0,
            min(start + len(page_rows), total), total)
        self._apply_table_colors(p)
        try:
            self.update()
        except AssertionError:
            pass

    def _make_row(self, p, mem, index):
        alt = index % 2 == 1
        return ft.DataRow(
            on_select_changed=lambda e, m=mem: self._edit_memory(m),
            color=p.table_row_alt if alt else p.table_row,
            cells=[
                ft.DataCell(ft.Text(
                    self._loc_value(mem), size=12, color=p.fg_text))
                if col == "loc"
                else ft.DataCell(ft.Text(
                    _render(col, mem), size=12, color=p.fg_text))
                for col in self.columns
            ],
        )

    def _loc_value(self, mem):
        return mem.extd_number if getattr(
            mem, "extd_number", None) else str(mem.number)

    def _apply_table_colors(self, p):
        self.table.border = ft.TableBorder.all(1, p.border_soft)
        for cell in self.table.columns:
            pass
        # header row colors are baked into rows via DataTable heading
        self.table.heading_row_color = p.table_header

    def _edit_memory(self, mem):
        def on_saved():
            self.refresh_rows()

        dlg = MemoryEditDialog(
            self._page, self.state, self, mem, on_saved)
        self._page.open(dlg)

    # ----- actions -----
    def apply_filter(self):
        self.filter_text = self.search_field.value or ""
        self.page_index = 0
        self.refresh_rows()

    def toggle_hide_empty(self):
        self.hide_empty = self.hide_empty_switch.value
        self.page_index = 0
        self.refresh_rows()

    def _goto(self, index):
        total = len(self._rows_cache)
        pages = max(1, -(-total // MEMORIES_PAGE_SIZE))
        self.page_index = max(0, min(index, pages - 1))
        self.refresh_rows()

    def _error(self, error):
        p = AppColors.for_mode(self.state.is_dark())
        self.table.rows = []
        self.content = ft.Container(
            expand=True, alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=SPACING.MD,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE,
                            size=48, color=p.error),
                    ft.Text(str(error), color=p.fg_muted, size=13),
                ],
            ),
        )
        try:
            self.update()
        except AssertionError:
            pass

    # ----- theme -----
    def apply_theme(self):
        self._build()
        self._apply()
        self.refresh_rows()
