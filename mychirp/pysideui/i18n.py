"""Localization for the flet UI.

Installs a lazy gettext ``_()`` that uses the CHIRP locale catalogs
shipped in ``mychirp/locale``. Falls back to the identity function
(English source strings) when no catalog matches.

The language is resolved from (in order): the ``lang`` key of the
chirp config ``state`` section, then the standard environment
variables (LANGUAGE/LC_ALL/LC_MESSAGES/LANG).
"""

import gettext
import logging
import os

LOG = logging.getLogger(__name__)

_catalogs_dir = None
_translation = None
_checked = False


def _locale_dir():
    global _catalogs_dir
    if _catalogs_dir is None:
        _catalogs_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "locale"))
    return _catalogs_dir


def available_languages():
    """Return the language codes that have a compiled catalog."""
    result = []
    try:
        for entry in sorted(os.listdir(_locale_dir())):
            mo = os.path.join(
                _locale_dir(), entry, "LC_MESSAGES", "CHIRP.mo")
            if os.path.exists(mo):
                result.append(entry)
    except OSError:
        pass
    return result


def _resolve_language():
    # Explicit user preference first
    try:
        from mychirp import config
        preferred = config.get().get("lang", "state")
        if preferred:
            return preferred
    except Exception:
        LOG.debug("Could not read language preference from config")

    # Then the standard environment chain
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return value.split(":")[0].split(".")[0]
    return None


def _install():
    global _translation, _checked
    if _checked:
        return
    _checked = True
    language = _resolve_language()
    if language and language != "C":
        try:
            _translation = gettext.translation(
                "CHIRP", localedir=_locale_dir(),
                languages=[language], fallback=None)
            LOG.debug("Loaded locale catalog for %s", language)
            _install_builtins()
            return
        except FileNotFoundError:
            LOG.debug("No locale catalog for %s; using source strings",
                      language)
        except Exception:
            LOG.exception("Failed to load locale catalog")
    _translation = gettext.NullTranslations()
    _install_builtins()


def _install_builtins():
    """Make the catalog-aware ``_`` visible to every module (upstream
    parity: CHIRP's wxui used to do ``builtins._ = wx.GetTranslation``).
    Drivers and chirp_common call ``_()`` without importing gettext;
    a no-op shim from mychirp/__init__.py covers the pre-GUI window."""
    import builtins
    builtins._ = _


def _(message):
    """Translate ``message`` using the active catalog (lazy install)."""
    if _translation is None:
        _install()
    return _translation.gettext(message)
