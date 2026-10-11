import flet as ft

from mychirp.fletui.theme import AppColors


class MyTabs(ft.Container):
    """Dynamic tabs wrapper for the flet 1.0 TabBar/TabBarView API.

    Keeps a list of (label, icon, view) tabs and exposes the classic
    add/remove/select API on top of the new Tabs model.
    """

    def __init__(self, page: ft.Page, state, on_change=None):
        super().__init__()
        self._page = page
        self.state = state
        self._on_change_cb = on_change
        self._entries: list[dict] = []

        self.tab_bar = ft.TabBar(tabs=[], scrollable=True)
        # expand=True is required: TabBarView (a Flutter PageView) must
        # receive bounded height constraints, otherwise it renders
        # "height is unbounded"
        self.tab_view = ft.TabBarView(controls=[], expand=True)
        self.tabs_ctrl = ft.Tabs(
            length=0,
            content=ft.Column(
                controls=[self.tab_bar, self.tab_view],
                spacing=0,
                expand=True,
            ),
            expand=True,
            selected_index=0,
            on_change=self._handle_change,
        )
        self.expand = True
        self.content = self.tabs_ctrl

    # ----- public API -----
    @property
    def selected_index(self) -> int:
        return self.tabs_ctrl.selected_index or 0

    def set_selected(self, index: int):
        if 0 <= index < len(self._entries):
            self.tabs_ctrl.selected_index = index

    def add_tab(self, label, icon, view, select=True):
        self._entries.append({"label": label, "icon": icon, "view": view})
        self._rebuild()
        if select:
            self.set_selected(len(self._entries) - 1)

    def insert_tab(self, index: int, label, icon, view, select=False):
        """Insert a tab at @index keeping the others in order."""
        index = max(0, min(index, len(self._entries)))
        self._entries.insert(
            index, {"label": label, "icon": icon, "view": view})
        self._rebuild()
        if select:
            self.set_selected(index)

    def remove_tab(self, index: int):
        if 0 <= index < len(self._entries):
            self._entries.pop(index)
            self._rebuild()
            self.set_selected(min(
                self.tabs_ctrl.selected_index or 0,
                max(0, len(self._entries) - 1)))

    def clear_tabs(self):
        self._entries.clear()
        self._rebuild()

    def view_at(self, index: int):
        if 0 <= index < len(self._entries):
            return self._entries[index]["view"]
        return None

    def index_of(self, view) -> int | None:
        for i, entry in enumerate(self._entries):
            if entry["view"] is view:
                return i
        return None

    @property
    def count(self) -> int:
        return len(self._entries)

    # ----- internals -----
    def _rebuild(self):
        self.tab_bar.tabs = [
            ft.Tab(label=e["label"], icon=e["icon"])
            for e in self._entries
        ]
        self.tab_view.controls = [e["view"] for e in self._entries]
        self.tabs_ctrl.length = len(self._entries)
        if self._is_mounted():
            try:
                self.update()
            except (AssertionError, RuntimeError):
                pass

    def _is_mounted(self) -> bool:
        try:
            return self.page is not None
        except RuntimeError:
            return False

    def _handle_change(self, e):
        if self._on_change_cb:
            try:
                self._on_change_cb(e)
            except Exception:
                pass
