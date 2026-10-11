from enum import IntEnum


class SPACING(IntEnum):
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


BORDER_RADIUS = {
    "sm": 6,
    "md": 10,
    "lg": 14,
    "xl": 20,
    "full": 9999,
}

# Responsive breakpoints (px)
BREAKPOINT_SM = 600
BREAKPOINT_MD = 900
BREAKPOINT_LG = 1200

# Memory table pagination
MEMORIES_PAGE_SIZE = 25

# Welcome logo max size (px)
WELCOME_LOGO_SIZE = 400
