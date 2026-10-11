import logging
import os

import flet as ft

from mychirp import chirp_common
from mychirp.fletui.components.statusbar import StatusBar
from mychirp.fletui.components.tabs import MyTabs
from mychirp.fletui.screens.memories_screen import MemoriesScreen
from mychirp.fletui.screens.recent_screen import RecentFilesScreen
from mychirp.fletui.screens.settings_screen import SettingsScreen
from mychirp.fletui.screens.welcome_screen import WelcomeScreen
from mychirp.fletui.services.app_state import get_state
from mychirp.fletui.theme import (
    BORDER_RADIUS,
    SPACING,
    AppColors,
)
from mychirp.fletui.i18n import _

LOG = logging.getLogger(__name__)



class RadioTabsView(ft.Column):
    """Inner notebook of one opened radio: Memories | Settings."""

    def __init__(self, page: ft.Page, state, eset):
        super().__init__()
        self._page = page
        self.state = state
        self.eset = eset
        self.expand = True
        self.spacing = 0
        self.memories = MemoriesScreen(page, state, eset)
        self.settings = (
            SettingsScreen(page, state, eset) if eset.has_settings() else None)
        self.inner_tabs = MyTabs(page, state)
        self.inner_tabs.add_tab(
            _("Memories"), ft.Icons.VIEW_LIST_OUTLINED,
            self.memories, select=False)
        if self.settings:
            self.inner_tabs.add_tab(
                _("Settings"), ft.Icons.TUNE, self.settings, select=False)
        self.inner_tabs.set_selected(0)
        self.controls = [self.inner_tabs]

    def refresh_data(self):
        self.memories.load_memories()

    def apply_theme(self):
        self.memories.apply_theme()
        if self.settings:
            self.settings.apply_theme()


class AppShell(ft.Container):
    """Main application layout: AppBar + editor tabs + status bar.

    Fully responsive and 100% theme-aware: every element rebuilds its
    colors from the current palette on every mode change.
    """

    def __init__(self, page: ft.Page):
        super().__init__()
        self._page = page
        self.state = get_state(page)
        self.state.shell = self
        self._tab_map: list = []  # list of (eset | None) per outer tab
        self.expand = True
        self._build()

        self._picker = ft.FilePicker()
        # flet 1.0: FilePicker is a service, not an overlay control
        # (adding it to overlay raises "Unknown control: FilePicker").
        # pick_files/save_file are async service methods that return
        # their result directly (on_result only fires for PickFiles
        # actions), so flows await them via page.run_task.
        page.services.append(self._picker)

        # Global keyboard shortcuts (flet 1.0 removed MenuItemButton
        # shortcuts, so we handle keys at the page level)
        page.on_keyboard_event = self._on_keyboard

    def _on_keyboard(self, e: ft.KeyboardEvent):
        if not e.ctrl and not e.meta:
            if e.key == "F5":
                self.refresh_current()
            return
        handlers = {
            "o": self.pick_open,
            "s": self.save_current,
            "d": self.download_from_radio,
            "u": self.upload_to_radio,
            "w": self.close_current,
        }
        handler = handlers.get((e.key or "").lower())
        if handler:
            handler()

    # ----- construction -----
    def _build(self):
        p = self.palette()
        self.bgcolor = p.bg_window

        self.welcome = WelcomeScreen(self._page, self.state)
        self.recents = RecentFilesScreen(self._page, self.state)

        self.outer_tabs = MyTabs(self._page, self.state,
                                 on_change=self._on_tab_change)
        self.outer_tabs.add_tab(
            _("Welcome"), ft.Icons.WAVING_HAND_OUTLINED, self.welcome,
            select=False)
        self.outer_tabs.add_tab(
            _("Recent files"), ft.Icons.HISTORY, self.recents,
            select=False)

        self.statusbar = StatusBar(self._page, self.state)

        self.content = ft.Column(
            controls=[
                self._build_appbar(p),
                ft.Container(
                    content=self.outer_tabs,
                    expand=True,
                    padding=ft.Padding.all(0),
                ),
                self.statusbar,
            ],
            spacing=0,
            expand=True,
        )
        self._tab_map = [None, None]
        self._update_radio_field()

    def palette(self):
        return AppColors.for_mode(self.state.is_dark())

    def _build_appbar(self, p):
        return ft.Container(
            bgcolor=p.bg_panel,
            border=ft.Border(
                bottom=ft.BorderSide(color=p.border, width=1),
                top=ft.BorderSide(0, ft.Colors.TRANSPARENT),
                left=ft.BorderSide(0, ft.Colors.TRANSPARENT),
                right=ft.BorderSide(0, ft.Colors.TRANSPARENT),
            ),
            padding=ft.Padding.symmetric(horizontal=SPACING.SM),
            content=ft.Row(
                controls=[
                    ft.Image(
                        src="mychirp_logo_transparente.png",
                        height=30,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                    ft.Text(
                        "MyChirp",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=p.fg_text,
                    ),
                    self._build_menubar(p),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=(
                            ft.Icons.DARK_MODE
                            if self.state.is_dark()
                            else ft.Icons.LIGHT_MODE),
                        icon_color=p.fg_muted,
                        tooltip=_("Toggle Light/Dark theme"),
                        on_click=lambda e: self.state.toggle_theme(),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(
                                radius=BORDER_RADIUS["sm"]),
                        ),
                    ),
                ],
                spacing=SPACING.SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _build_menubar(self, p):
        style = ft.ButtonStyle(
            color=p.fg_text,
            bgcolor={
                ft.ControlState.HOVERED: p.bg_panel_alt,
            },
            shape=ft.RoundedRectangleBorder(radius=BORDER_RADIUS["sm"]),
        )

        file_menu = ft.SubmenuButton(
            content=_("File"),
            style=style,
            controls=[
                ft.MenuItemButton(
                    content=_("Open..."),
                    leading=ft.Icons.FILE_OPEN_OUTLINED,
                    on_click=lambda e: self.pick_open(),
                ),
                ft.Divider(height=1, color=p.border_soft),
                ft.MenuItemButton(
                    content=_("Save"),
                    leading=ft.Icons.SAVE_OUTLINED,
                    on_click=lambda e: self.save_current(),
                ),
                ft.MenuItemButton(
                    content=_("Save As..."),
                    leading=ft.Icons.SAVE_AS_OUTLINED,
                    on_click=lambda e: self.save_current(as_new=True),
                ),
                ft.Divider(height=1, color=p.border_soft),
                ft.MenuItemButton(
                    content=_("Restore last session"),
                    leading=ft.Icons.RESTORE,
                    on_click=lambda e: self.restore_session(),
                ),
                ft.MenuItemButton(
                    content=_("Close Tab"),
                    leading=ft.Icons.CLOSE,
                    on_click=lambda e: self.close_current(),
                ),
            ],
        )

        radio_menu = ft.SubmenuButton(
            content=_("Radio"),
            style=style,
            controls=[
                ft.MenuItemButton(
                    content=_("Download from radio"),
                    leading=ft.Icons.SETTINGS_INPUT_ANTENNA,
                    on_click=lambda e: self.download_from_radio(),
                ),
                ft.MenuItemButton(
                    content=_("Upload to radio"),
                    leading=ft.Icons.BACKUP,
                    on_click=lambda e: self.upload_to_radio(),
                ),
            ],
        )

        view_menu = ft.SubmenuButton(
            content=_("View"),
            style=style,
            controls=[
                ft.MenuItemButton(
                    content=(
                        _("Switch to Light Theme")
                        if self.state.is_dark()
                        else _("Switch to Dark Theme")),
                    leading=(
                        ft.Icons.LIGHT_MODE
                        if self.state.is_dark()
                        else ft.Icons.DARK_MODE),
                    on_click=lambda e: self.state.toggle_theme(),
                ),
                ft.MenuItemButton(
                    content=_("Refresh data"),
                    leading=ft.Icons.REFRESH,
                    on_click=lambda e: self.refresh_current(),
                ),
                ft.MenuItemButton(
                    content=(
                        _("Disable session restore")
                        if self.state.session_restore_enabled()
                        else _("Enable session restore")),
                    leading=(
                        ft.Icons.CHECK_BOX
                        if self.state.session_restore_enabled()
                        else ft.Icons.CHECK_BOX_OUTLINE_BLANK),
                    on_click=lambda e: self.toggle_session_restore(),
                ),
            ],
        )

        help_menu = ft.SubmenuButton(
            content=_("Help"),
            style=style,
            controls=[
                ft.MenuItemButton(
                    content=_("About"),
                    leading=ft.Icons.INFO_OUTLINE,
                    on_click=lambda e: self.show_about(),
                ),
            ],
        )

        return ft.MenuBar(
            controls=[file_menu, radio_menu, view_menu, help_menu],
            style=ft.MenuStyle(
                alignment=ft.Alignment.CENTER_LEFT,
             ),
         )

    # ----- file actions -----
    def pick_open(self):
        async def _flow():
            files = await self._picker.pick_files(
                dialog_title=_("Open radio image"),
                allowed_extensions=["img", "csv", "chirp"],
                file_type=ft.FilePickerFileType.CUSTOM,
            )
            if files:
                self.open_file(files[0].path)
        self._page.run_task(_flow)

    def open_file(self, filename):
        from mychirp.fletui.services.radio_service import get_service
        self.state.set_status(_("Opening %s...") % filename)
        service = get_service(self._page)

        def done(job):
            if job.error:
                self.state.set_status("")
                self._error_dialog(_("Failed to open file"), job.error)
                return
            radio = job.result
            from mychirp.fletui.services.app_state import EditorSetState
            eset = EditorSetState(radio, filename)
            self.state.push_recent_file(filename)
            self.recents.refresh()
            self.state.add_editorset(eset)
            self.state.set_status(
                _("Loaded %s") % os.path.basename(filename))
            self.refresh_current()

        service.open_file(filename, done)

    def save_current(self, as_new=False, target=None):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Nothing to save"))
            return
        if target is None and as_new:
            async def _flow():
                path = await self._picker.save_file(
                    dialog_title=_("Save radio image"),
                    file_name=eset.default_filename,
                    allowed_extensions=["img", "csv"],
                    file_type=ft.FilePickerFileType.CUSTOM,
                )
                if path:
                    self.save_current(target=path)
            self._page.run_task(_flow)
            return
        filename = target or eset.filename
        eset.filename = filename
        from mychirp.fletui.services.radio_service import get_service
        service = get_service(self._page)
        self.state.set_status(_("Saving to %s...") % filename)

        def done(job):
            if job.error:
                self._error_dialog(_("Failed to save"), job.error)
            else:
                eset.modified = False
                self.state.set_status(_("Saved %s") % filename)
                self._update_radio_field()

        service.save_radio(eset.radio, filename, done)

    def close_current(self):
        eset = self.current_editorset
        if eset:
            self.state.remove_editorset(eset)

    def restore_session(self):
        """Reopen the radios from the previous session (menu action)."""
        restored = self.state.restore_session()
        if restored:
            self.state.set_status(
                _("Restored %i radio(s)") % restored)
        else:
            self.state.set_status(_("Nothing to restore"))

    def toggle_session_restore(self):
        enabled = not self.state.session_restore_enabled()
        self.state.set_session_restore(enabled)
        self.state.set_status(
            _("Session restore enabled") if enabled
            else _("Session restore disabled"))
        # Rebuild the menu so the item label/state updates
        p = self.palette()
        self.content.controls[0] = self._build_appbar(p)
        try:
            self.update()
        except (AssertionError, RuntimeError):
            pass

    def refresh_current(self):
        view = self._current_view()
        if view:
            view.refresh_data()
            if view.settings:
                view.settings.load_settings()

    # ----- radio actions -----
    def download_from_radio(self):
        from mychirp.fletui.dialogs.clone_dialog import CloneDialog
        dlg = CloneDialog(self._page, self.state, mode="download")
        self._page.open(dlg)

    def upload_to_radio(self):
        eset = self.current_editorset
        if not eset:
            self.state.set_status(_("Open a radio first"))
            return
        from mychirp.fletui.dialogs.clone_dialog import CloneDialog
        dlg = CloneDialog(self._page, self.state, mode="upload", eset=eset)
        self._page.open(dlg)

    # ----- about -----
    def show_about(self):
        from mychirp.fletui.dialogs.about_dialog import AboutDialog
        self._page.open(AboutDialog(self._page, self.state))

    def _error_dialog(self, title, error):
        def close(e):
            self._page.close(dlg)

        p = self.palette()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, color=p.fg_text),
            content=ft.Text(str(error), color=p.fg_muted),
            actions=[
                ft.TextButton(_("OK"), on_click=close),
            ],
        )
        self._page.open(dlg)

    # ----- tabs management -----
    def _welcome_index(self) -> int | None:
        """Index of the Welcome tab, or None when it is not open."""
        for i in range(self.outer_tabs.count):
            if self.outer_tabs.view_at(i) is self.welcome:
                return i
        return None

    def add_radio_tab(self, eset, select=True):
        view = RadioTabsView(self._page, self.state, eset)
        # Remove the welcome tab once a real radio is opened
        # (the Recent files tab stays available)
        welcome_index = self._welcome_index()
        if welcome_index is not None:
            self._tab_map.pop(welcome_index)
            self.outer_tabs.remove_tab(welcome_index)
        self._tab_map.append(eset)
        self.outer_tabs.add_tab(
            eset.tab_title, ft.Icons.SETTINGS_INPUT_ANTENNA, view,
            select=select)
        self._update_radio_field()

    def remove_radio_tab(self, eset):
        if eset in self._tab_map:
            index = self._tab_map.index(eset)
            self._tab_map.pop(index)
            self.outer_tabs.remove_tab(index)
            if not any(es is not None for es in self._tab_map):
                # No radios left: bring the Welcome tab back at front
                self._tab_map.insert(0, None)
                self.outer_tabs.insert_tab(
                    0, _("Welcome"), ft.Icons.WAVING_HAND_OUTLINED,
                    self.welcome, select=True)
        self._update_radio_field()

    def _current_view(self) -> RadioTabsView | None:
        view = self.outer_tabs.view_at(self.outer_tabs.selected_index)
        if isinstance(view, RadioTabsView):
            return view
        return None

    @property
    def current_editorset(self):
        index = self.outer_tabs.selected_index
        if 0 <= index < len(self._tab_map):
            eset = self._tab_map[index]
            return eset
        return None

    def _on_tab_change(self, e):
        self._update_radio_field()

    def _update_radio_field(self):
        eset = self.current_editorset
        if eset:
            radio_label = eset.radio_label
            modified = _("Unsaved changes") if eset.modified else ""
            self.set_status(radio_label, field=1)
            self.set_status(modified, field=2)
        else:
            self.set_status("", field=1)
            self.set_status("", field=2)

    # ----- theme -----
    def set_status(self, message, field=0):
        self.statusbar.set_status(message, field)

    def apply_theme(self):
        """Rebuild the whole shell with the new palette."""
        selected = self.outer_tabs.selected_index
        radio_views = [
            self.outer_tabs.view_at(i)
            for i in range(self.outer_tabs.count)
        ]
        self._build()
        for view in radio_views:
            if isinstance(view, RadioTabsView):
                # One broken view must never abort the whole re-theme
                # (that would leave the appbar/statusbar stale)
                try:
                    view.apply_theme()
                except Exception:
                    LOG.exception("apply_theme failed for radio tab")
                self._tab_map.append(view.eset)
                self.outer_tabs.add_tab(
                    view.eset.tab_title,
                    ft.Icons.SETTINGS_INPUT_ANTENNA, view)
        self.outer_tabs.set_selected(min(
            selected, max(0, self.outer_tabs.count - 1)))
        self._update_radio_field()
        try:
            self.update()
        except (AssertionError, RuntimeError):
            pass
