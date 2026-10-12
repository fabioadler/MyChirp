"""Backend-neutral shared design tokens for MyChirp.

Pure Python color/spacing constants used by both the Flet and PySide6
UIs. Kept GUI-toolkit-free so the backend and every UI share one
source of truth for the visual identity.
"""


class Palette:
    """Semantic palette for a single mode."""

    def __init__(self, **roles):
        self.__dict__.update(roles)


def _with_opacity(alpha: float, hex_color: str) -> str:
    """Approximate flet's with_opacity (premultiplied over the same bg
    is not needed for QSS which supports rgba() strings)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(round(alpha * 255))
    return "#%02x%02x%02x%02x" % (r, g, b, a)


class AppColors:
    """Semantic color tokens with light and dark variants.

    Mirrors the design tokens from docs/ui-redesign.md so all UIs
    share the same visual identity. SCRIM/SHADOW entries use #RRGGBBAA
    so QSS `rgba()` mapping works without flet.
    """

    # ----- Light mode -----
    L_BG_WINDOW = "#F6F7F9"
    L_BG_PANEL = "#FFFFFF"
    L_BG_PANEL_ALT = "#F1F3F5"
    L_BG_PENDING = "#FFF4D6"
    L_BG_IMMUTABLE = "#F0F1F3"
    L_FG_TEXT = "#1A1C1E"
    L_FG_MUTED = "#5A6069"
    L_ACCENT = "#1A6B8F"
    L_ACCENT_HOVER = "#155874"
    L_ACCENT_CONTAINER = "#D6EBF4"
    L_ON_ACCENT_CONTAINER = "#0F4359"
    L_ACCENT_DOWNLOAD = "#1E7B4F"
    L_ACCENT_UPLOAD = "#B3541E"
    L_ERROR = "#B3261E"
    L_ERROR_CONTAINER = "#FDE7E5"
    L_SUCCESS = "#1E7B4F"
    L_WARNING = "#B3541E"
    L_BORDER = "#D8DCE0"
    L_BORDER_SOFT = "#E6E9ED"
    L_NAV = "#FFFFFF"
    L_NAV_SELECTED = "#1A6B8F"
    L_NAV_SELECTED_FG = "#FFFFFF"
    L_TAB = "#FFFFFF"
    L_TAB_ACTIVE_FG = "#1A6B8F"
    L_TABLE_HEADER = "#EEF1F4"
    L_TABLE_ROW = "#FFFFFF"
    L_TABLE_ROW_ALT = "#F6F7F9"
    L_TABLE_SELECTED = "#1A6B8F"
    L_TABLE_SELECTED_FG = "#FFFFFF"
    L_INPUT = "#FFFFFF"
    L_SCRIM = _with_opacity(0.45, "#1A1C1E")
    L_SHADOW = _with_opacity(0.10, "#1A1C1E")

    # ----- Dark mode -----
    D_BG_WINDOW = "#1E1F24"
    D_BG_PANEL = "#26272C"
    D_BG_PANEL_ALT = "#222329"
    D_BG_PENDING = "#3A3320"
    D_BG_IMMUTABLE = "#2B2C31"
    D_FG_TEXT = "#E8EAED"
    D_FG_MUTED = "#9AA1AC"
    D_ACCENT = "#5FB2CE"
    D_ACCENT_HOVER = "#7AC4DC"
    D_ACCENT_CONTAINER = "#1F3A47"
    D_ON_ACCENT_CONTAINER = "#BCE4F2"
    D_ACCENT_DOWNLOAD = "#4CAF7D"
    D_ACCENT_UPLOAD = "#E08A4F"
    D_ERROR = "#F2B8B5"
    D_ERROR_CONTAINER = "#54261F"
    D_SUCCESS = "#4CAF7D"
    D_WARNING = "#E08A4F"
    D_BORDER = "#383B42"
    D_BORDER_SOFT = "#2E3036"
    D_NAV = "#1E1F24"
    D_NAV_SELECTED = "#5FB2CE"
    D_NAV_SELECTED_FG = "#10231B"
    D_TAB = "#26272C"
    D_TAB_ACTIVE_FG = "#5FB2CE"
    D_TABLE_HEADER = "#2B2C31"
    D_TABLE_ROW = "#26272C"
    D_TABLE_ROW_ALT = "#222329"
    D_TABLE_SELECTED = "#5FB2CE"
    D_TABLE_SELECTED_FG = "#10231B"
    D_INPUT = "#2B2C31"
    D_SCRIM = _with_opacity(0.55, "#000000")
    D_SHADOW = _with_opacity(0.35, "#000000")

    @classmethod
    def for_mode(cls, dark: bool) -> Palette:
        prefix = "D_" if dark else "L_"
        roles = {}
        for name in dir(cls):
            if name.startswith(prefix):
                role = name[len(prefix):].lower()
                roles[role] = getattr(cls, name)
        return Palette(**roles)


# Spacing (logical pixels)
BORDER_RADIUS = {"sm": 4, "md": 8, "lg": 12, "full": 9999}


class SPACING:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24


BREAKPOINT_SM = 600
BREAKPOINT_MD = 900
BREAKPOINT_LG = 1280

WELCOME_LOGO_SIZE = 300

MEMORIES_PAGE_SIZE = 25
