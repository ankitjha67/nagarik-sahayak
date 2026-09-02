"""Seeder payloads must match the Prisma models they are written to.

This exists because of a bug it would have caught. `seed_from_catalog` passed
the raw catalog entry straight to `prisma.formtemplate.create`, while the live
refresh path correctly built a payload through `_template_data`. The catalog
entry carries snake_case keys (`official_pdf_url`, `is_scanned`) and plain
Python lists where the client needs `Json()`, so every seed raised — and the
seed loop catches per-scheme exceptions into an `errors` list, so a deployment
came up with an empty form catalog and a log line nobody read.

The unit suite could not catch it: exercising it needs a generated Prisma
client and a live MongoDB. So the schema is parsed as text instead, and the
payload builders are checked against the field names it declares. That is a
weaker guarantee than a round-trip against a real database, and it is the one
available without one.
"""
import re
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parents[1] / "prisma" / "schema.prisma"


def model_fields(model: str) -> set[str]:
    """Scalar and relation field names declared on one Prisma model."""
    text = SCHEMA.read_text(encoding="utf-8")
    match = re.search(rf"^model {model} \{{(.*?)^\}}", text, re.S | re.M)
    assert match, f"model {model} not found in schema.prisma"
    fields = set()
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith(("//", "@@")):
            continue
        name = line.split()[0]
        if name.isidentifier():
            fields.add(name)
    return fields


class _Json:
    """Stand-in for prisma.Json so payload builders run without the client."""

    def __init__(self, value):
        self.value = value


@pytest.fixture
def seeder(monkeypatch):
    """Import the seeder with a `Json` that is distinguishable from a raw list.

    The stub is installed unconditionally. test_app_boot puts a module-scoped
    `prisma` stub in sys.modules whose Json is the identity function, which
    would make "is this value wrapped?" unanswerable — the test would pass
    alone and fail in a full run, for a reason having nothing to do with the
    code under test.
    """
    import sys
    import types

    module = sys.modules.get("prisma")
    if module is None:
        module = types.ModuleType("prisma")
        monkeypatch.setitem(sys.modules, "prisma", module)
    monkeypatch.setattr(module, "Json", _Json, raising=False)

    from services import form_seeder
    return form_seeder


class TestFormTemplatePayload:
    def test_every_key_exists_on_the_model(self, seeder):
        from data.gov_forms import get_catalog

        allowed = model_fields("FormTemplate")
        payload = seeder._template_data(get_catalog()[0])
        unknown = set(payload) - allowed
        assert not unknown, (
            f"_template_data emits {sorted(unknown)}, which FormTemplate does "
            "not declare — Prisma rejects the write and the seed fails silently")

    def test_no_snake_case_keys_leak_through(self, seeder):
        from data.gov_forms import get_catalog

        payload = seeder._template_data(get_catalog()[0])
        snake = [k for k in payload if "_" in k]
        assert not snake, f"catalog keys leaked into the payload: {snake}"

    def test_json_columns_are_wrapped(self, seeder):
        from data.gov_forms import get_catalog

        payload = seeder._template_data(get_catalog()[0])
        for key in ("extractedFields", "sections", "eligibilityCriteria"):
            assert not isinstance(payload[key], (list, dict)), \
                f"{key} must be wrapped in Json() before it reaches Prisma"

    def test_level_and_state_are_carried(self, seeder):
        from data.gov_forms import get_by_name

        central = seeder._template_data(get_by_name("PM-KISAN Samman Nidhi"))
        assert central["level"] == "Central" and central["state"] == ""

        state = seeder._template_data(
            get_by_name("Lakshmir Bhandar (West Bengal)"))
        assert state["level"] == "State" and state["state"] == "West Bengal"

    def test_state_is_never_null(self, seeder):
        """A null would be dropped by an equality filter, hiding every Central
        scheme from every State view."""
        from data.gov_forms import get_catalog

        for entry in get_catalog():
            assert seeder._template_data(entry)["state"] is not None

    def test_every_catalog_entry_builds_a_payload(self, seeder):
        from data.gov_forms import get_catalog

        allowed = model_fields("FormTemplate")
        for entry in get_catalog():
            payload = seeder._template_data(entry)
            assert not set(payload) - allowed, entry["schemeName"]
            assert payload["schemeName"] == entry["schemeName"]
            assert payload["totalFields"] == len(entry["extractedFields"])


class TestSchemePayload:
    def test_every_key_exists_on_the_model(self, seeder):
        import asyncio
        import inspect

        # _upsert_scheme builds its payload inline, so read it out of the
        # source rather than executing a coroutine that needs a database.
        source = inspect.getsource(seeder._upsert_scheme)
        keys = set(re.findall(r'^\s{8}"(\w+)":', source, re.M))
        allowed = model_fields("Scheme")
        assert keys, "could not read the Scheme payload keys"
        assert not keys - allowed, f"unknown Scheme fields: {sorted(keys - allowed)}"
        assert {"level", "state"} <= keys, \
            "Scheme rows without level/state cannot back a State filter"
        assert asyncio.iscoroutinefunction(seeder._upsert_scheme)


class TestSeedUsesTheBuilder:
    def test_the_catalog_seed_does_not_pass_a_raw_entry(self, seeder):
        """The exact regression. A raw entry reaching Prisma fails every write
        into an errors list, so the app boots with no forms and no alarm."""
        import inspect

        source = inspect.getsource(seeder.seed_from_catalog)
        assert "_upsert_template(entry)" not in source
        assert "_template_data(entry)" in source
