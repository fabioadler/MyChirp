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
from mychirp.fletui.i18n import _

LOG = logging.getLogger(__name__)


class BanksScreen(ft.Container):
    """Bank membership editor (CHIRP parity: banks tab).

    One row per non-empty memory, one checkbox column per bank.
    Toggling calls BankModel.add/remove_memory_to_mapping — the same
    data layer the wxui bank editor used.
    """

    def __init__(self, page: ft.Page, state, eset):
        super().__init__()
        self._page = page
        self.state = state
        self.eset = eset
        self._bankmodel = eset.radio.get_bank_model()
        self.page_index = 0
        self.expand = True
        self._build()

    # ----- layout -----
    def _build(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.bgcolor = p.bg_panel
        self.border_radius = BORDER_RADIUS["lg"]
        self.info_text = ft.Text("", size=12, color=p.fg_muted)
        self.table = self._build_table(p)
        self.content = ft.Column(
            expand=True,
            spacing=SPACING.MD,
            controls=[
                ft.Row(
                    spacing=SPACING.MD,
                    controls=[
                        ft.Text(
                                            _("Banks"),
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
                self.info_text,
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                        controls=[self.table]),
                ),
            ],
        )

    def _build_table(self, p):
        # Flet requires at least one column: seed a placeholder so the
        # table mounts cleanly before refresh() fills it in
        return ft.DataTable(
            columns=[
                ft.DataColumn(label=ft.Text(
                    _("Banks"), size=12, weight=ft.FontWeight.BOLD,
                    color=p.fg_text))
            ],
            rows=[],
            heading_row_height=40,
            data_row_min_height=38,
            data_row_max_height=38,
            border=ft.Border.all(1, p.border_soft),
            border_radius=BORDER_RADIUS["md"],
            horizontal_margin=SPACING.SM,
            column_spacing=SPACING.MD,
            expand=True,
        )

    # ----- data -----
    def refresh(self):
        p = AppColors.for_mode(self.state.is_dark())
        try:
            banks = list(self._bankmodel.get_mappings())
        except Exception:
            LOG.exception("Failed to list banks")
            banks = []

        memories = [
            m for m in self.eset.memories.values()
            if not m.empty and isinstance(m.number, int)
        ]
        memories.sort(key=lambda m: m.number)

        total = len(memories)
        pages = max(1, -(-total // MEMORIES_PAGE_SIZE))
        self.page_index = min(self.page_index, pages - 1)
        start = self.page_index * MEMORIES_PAGE_SIZE
        page_mems = memories[start:start + MEMORIES_PAGE_SIZE]

        self.table.columns = [
            ft.DataColumn(label=ft.Text(
                _("Loc"), size=12, weight=ft.FontWeight.BOLD,
                color=p.fg_text)),
            ft.DataColumn(label=ft.Text(
                _("Name"), size=12, weight=ft.FontWeight.BOLD,
                color=p.fg_text)),
        ] + [
            ft.DataColumn(label=ft.Text(
                bank.get_name(), size=12, weight=ft.FontWeight.BOLD,
                color=p.fg_text))
            for bank in banks
        ]

        rows = []
        for mem in page_mems:
            try:
                member_indexes = {
                    b.get_index()
                    for b in self._bankmodel.get_memory_mappings(mem)}
            except Exception:
                LOG.exception("Failed mappings for %s", mem.number)
                member_indexes = set()
            cells = [
                ft.DataCell(ft.Text(
                    str(mem.number), size=12, color=p.fg_text)),
                ft.DataCell(ft.Text(
                    mem.name or "", size=12, color=p.fg_text)),
            ]
            for bank in banks:
                present = bank.get_index() in member_indexes
                cells.append(ft.DataCell(ft.Checkbox(
                    value=present,
                    active_color=p.accent,
                    on_change=lambda e, m=mem, b=bank: self._toggle(m, b, e),
                )))
            rows.append(ft.DataRow(cells=cells))
        self.table.rows = rows

        self.info_text.value = (
            _("%i banks · %i channels · showing %i-%i")
            % (len(banks), total,
               start + 1 if total else 0,
               min(start + len(page_mems), total)))
        try:
            self.update()
        except (AssertionError, RuntimeError):
            pass

    def _toggle(self, mem, bank, e):
        present = bool(e.control.value)
        service = get_service(self._page)

        def _apply():
            if present:
                self._bankmodel.add_memory_to_mapping(mem, bank)
            else:
                self._bankmodel.remove_memory_from_mapping(mem, bank)
            return True

        def done(job):
            if job.error:
                self.state.set_status(_("Bank update failed"))
                LOG.exception("bank toggle failed")
            else:
                self.eset.modified = True
                self.state.set_status(
                    _("Channel %i %s bank %s") % (
                        mem.number,
                        _("added to") if present else _("removed from"),
                        bank.get_name()))

        from mychirp.fletui.services.radio_service import RadioJob
        job = RadioJob(_apply, radio=self.eset.radio)
        service._run_async(job, done)

    # ----- theme -----
    def apply_theme(self):
        p = AppColors.for_mode(self.state.is_dark())
        self.table.border = ft.Border.all(1, p.border_soft)
        self.refresh()
