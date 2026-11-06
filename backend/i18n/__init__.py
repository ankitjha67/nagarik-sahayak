"""Multilingual support across the Eighth Schedule.

    languages.py — the 22 scheduled languages plus English, with endonyms,
                   scripts, direction, and the States each is official in
    catalog.py   — interface strings, per language, each marked with how much
                   weight it can bear
    resolve.py   — lookup and bundling; a fallback is never silent

The rule the package exists to enforce: the app may serve a language it cannot
fully translate, but it must always say so. Silently rendering English while
appearing to have honoured a request for Santali tells the reader that English
is their language and leaves them no way to ask for better.
"""
from i18n.languages import LANGUAGES, get, normalise  # noqa: F401
# `resolve` is deliberately not re-exported: the name would shadow the
# i18n.resolve submodule, so `from i18n import resolve` would hand a caller the
# function instead of the module. Import it as i18n.resolve.resolve.
from i18n.resolve import bundle, catalogue, summary, t  # noqa: F401
