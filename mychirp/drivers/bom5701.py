# Copyright 2026 BOMVINK BOM-5701 contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.

"""BOMVINK BOM-5701 driver (aux-block-first UV-5R clone).

Separated from uv5r.py so the original UV-5R driver stays untouched.
"""

import gettext
import logging

from mychirp import chirp_common, directory
from mychirp.drivers.uv5r import BaofengUV5R, _download_full_window

LOG = logging.getLogger(__name__)
_ = gettext.gettext


class UV5RAuxFirstClone(BaofengUV5R):
    """Shared base for UV-5R clones that end the clone session as soon
    as the main block transfer completes.

    Validated on a BOMVINK BOM-5701 (serial traces plus real-hardware
    downloads AND a byte-identical read/write/read round-trip, see
    chirpmyradio.com issue #12332): any request issued after the main
    block completes is ignored until the radio is power-cycled, while
    aux-area requests are served normally before the main block is
    transferred. The download therefore reads the aux block first and
    appends it after the main block, and the upload writes the aux
    block first. These radios also NACK the write issued immediately
    after an accepted one (commit window), so uploads retry each
    block, and they need a short cooldown between clone sessions.
    Both directions produce and expect byte-for-byte standard UV-5R
    images (0x1948 bytes).

    Observed units report a blank (all 0xFF) firmware version string,
    so image files cannot be matched against the usual basetype list;
    a dedicated match_model() accepts exactly that signature.
    """
    _aux_first = True

    @classmethod
    def get_prompts(cls):
        rp = chirp_common.RadioPrompts()
        rp.experimental = \
            ('This driver is based on the observed behavior of this '
             'radio family (see chirpmyradio.com issue #12332). The '
             'radio ends the clone session when the main block '
             'transfer completes, so the download reads the auxiliary '
             'memory block before the main block and the upload writes '
             'it first, retrying each block until the radio accepts '
             'it. Both directions are validated on real hardware '
             '(byte-identical round-trip). Always keep a downloaded '
             'backup. Proceed at your own risk!')
        rp.pre_download = _(
            "1. Turn radio off.\n"
            "2. Connect cable to mic/spkr connector.\n"
            "3. Make sure connector is firmly connected.\n"
            "4. Turn radio on (volume may need to be set at 100%).\n"
            "5. Ensure that the radio is tuned to channel with no"
            " activity.\n"
            "6. Click OK to download image from device.\n")
        rp.pre_upload = _(
            "1. Turn radio off.\n"
            "2. Connect cable to mic/spkr connector.\n"
            "3. Make sure connector is firmly connected.\n"
            "4. Turn radio on (volume may need to be set at 100%).\n"
            "5. Ensure that the radio is tuned to channel with no"
            " activity.\n"
            "6. Click OK to upload image to device.\n\n"
            "NOTE: If a clone session just ran (including a failed "
            "one), wait a few seconds before starting, because the "
            "radio needs a short cooldown between sessions. Keep a "
            "backup of the downloaded image.")
        return rp

    @classmethod
    def match_model(cls, filedata, filename):
        if len(filedata) == 0x1948:
            # These units report a blank (all 0xFF) firmware version
            # string, so match on that instead of the basetype list.
            version = filedata[cls._fw_ver_file_start:cls._fw_ver_file_stop]
            return version == b"\xff" * (cls._fw_ver_file_stop -
                                         cls._fw_ver_file_start)
        return False

    def download_full_window(self, status_fn=None):
        """Live read of the complete 8 KiB cable-visible window.

        Returns the raw radio-address-space bytes (0x0000-0x2000),
        which include the calibration area at 0x1800-0x1EC0 that the
        standard image does not cover. Read-only: no write command is
        ever issued. See _download_full_window in uv5r for evidence.
        """
        return _download_full_window(self, status_fn=status_fn)


@directory.register
class BOMVINKBOM5701(UV5RAuxFirstClone):
    """BOMVINK BOM-5701.

    Downloads validated on real hardware (two byte-identical repeated
    reads; see issue #12332). The radio presents channels 000-126
    (127 channels), so the memory bounds are narrowed accordingly even
    though the image layout is the standard 128-slot UV-5R format.

    Band-limit areas in these units are often blank (0xFF) in the aux
    block; the VHF/UHF range settings in Other Settings are clamped in
    the memobj before being built, so values out of the declared range
    become hardware defaults instead of failing to initialize.
    """
    VENDOR = "BOMVINK"
    MODEL = "BOM-5701"

    # Hardware band edges measured on real units (MHz)
    _vhf_range = (128000000, 176000000)
    _uhf_range = (384000000, 524000000)
    # MHz bounds for the lower/upper limit settings
    _LIMIT_RANGES = {
        "vhf": (128, 176),
        "uhf": (384, 524),
    }

    def get_features(self):
        rf = super().get_features()
        # The radio presents channels 000-126
        rf.memory_bounds = (0, 126)
        return rf

    def _clamp_limit_memobj(self):
        """Fix the VHF/UHF band-limit memobj values so the Other
        Settings menu always shows them initialized. Out-of-range
        bytes (e.g. blank 0xFF areas reading as 16665) become the
        hardware defaults: lower -> band min, upper -> band max."""
        limit = "limits_old" if self._is_orig() else "limits_new"
        obj = getattr(self._memobj, limit)
        for band in ("vhf", "uhf"):
            lim = getattr(obj, band)
            vmin, vmax = self._LIMIT_RANGES[band]
            for field in ("lower", "upper"):
                raw = getattr(lim, field, None)
                try:
                    value = int(raw)
                except Exception:
                    continue
                if vmin <= value <= vmax:
                    continue
                setattr(lim, field, vmin if field == "lower" else vmax)

    def _get_settings(self):
        self._clamp_limit_memobj()
        return super()._get_settings()
