import flet as ft

from mychirp.fletui.theme.colors import AppColors, Palette
from mychirp.fletui.theme.spacing import (
    BORDER_RADIUS,
    BREAKPOINT_LG,
    BREAKPOINT_MD,
    BREAKPOINT_SM,
    MEMORIES_PAGE_SIZE,
    SPACING,
    WELCOME_LOGO_SIZE,
)

_ = lambda s: s


def get_theme(dark: bool) -> ft.Theme:
    """Build a flet Theme seeded by the MyChirp accent."""
    accent = AppColors.D_ACCENT if dark else AppColors.L_ACCENT
    return ft.Theme(
        color_scheme_seed=accent,
        visual_density=ft.VisualDensity.COMPACT,
    )


def text(color, size=14, weight=ft.FontWeight.W_400, **kw):
    """Shorthand for a themed ft.Text."""
    return ft.Text(color=color, size=size, weight=weight, **kw)


__all__ = [
    "AppColors",
    "BORDER_RADIUS",
    "BREAKPOINT_LG",
    "BREAKPOINT_MD",
    "BREAKPOINT_SM",
    "MEMORIES_PAGE_SIZE",
    "SPACING",
    "WELCOME_LOGO_SIZE",
    "Palette",
    "get_theme",
    "text",
]
