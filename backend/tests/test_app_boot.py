"""Verify the application actually assembles and serves.

Every other test exercises a module in isolation. None of them would catch the
failure that matters most in practice: a bad import, a circular dependency, or a
router that silently fails to mount, leaving a deploy that starts and then 404s
everything.

The database is stubbed because a generated Prisma client needs a live MongoDB.
That is deliberate — the point here is wiring, not persistence, and the checks
below use only endpoints that serve from bundled data or pure computation.
"""
import importlib
import os
import sys
import types

import pytest


# Modules that must all import cleanly. A circular import or a reference to a
# name that no longer exists shows up here first.
BACKEND_MODULES = [
    "config", "models", "database",
    "validation", "identity_index", "eligibility_engine", "fraud_detection",
    "field_rules", "form_extractor", "pdf_generator", "pdf_filler",
    "data.gov_forms",
    "services.v3_bridge", "services.form_seeder", "services.application_guard",
    "services.review_queue", "services.review_context",
    "routes.auth", "routes.chat", "routes.profile", "routes.schemes",
    "routes.pdf", "routes.demo", "routes.v2",
    "routes.discovery", "routes.exams", "routes.reports", "routes.notifications",
    "routes.forms", "routes.verification", "routes.review", "routes.dpdp",
    "routes.kyc", "routes.i18n",
    "i18n.languages", "i18n.catalog", "i18n.resolve",
    "kyc.methods", "kyc.matching", "kyc.aadhaar_offline", "kyc.service",
    "dpdp.classifier", "dpdp.registry", "dpdp.engine", "dpdp.consent",
    "dpdp.retention", "dpdp.ownership", "dpdp.crypto", "dpdp.profile_store",
    "dpdp.file_vault", "dpdp.terms", "dpdp.statutes", "dpdp.grievance",
    "dpdp.incident", "dpdp.aadhaar_policy", "dpdp.nomination",
]


@pytest.fixture(scope="module")
def stubbed_env():
    """Stub only what genuinely requires a live external service."""
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("ADMIN_SECRET", "test-secret")
    os.environ.setdefault("IDENTITY_HASH_SALT", "test-salt")
    for name in ("prisma", "motor", "motor.motor_asyncio", "agnost"):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["prisma"].Prisma = lambda: types.SimpleNamespace()
    sys.modules["prisma"].Json = lambda x: x
    sys.modules["motor.motor_asyncio"].AsyncIOMotorClient = lambda *a, **k: {}
    yield


@pytest.fixture(scope="module")
def client(stubbed_env):
    import server
    from starlette.testclient import TestClient

    # raise_server_exceptions=False so a handler that needs a live database
    # reports 500 instead of aborting the run — routing is what is under test.
    return TestClient(server.app, raise_server_exceptions=False)


class TestModuleImports:
    @pytest.mark.parametrize("module", BACKEND_MODULES)
    def test_module_imports(self, stubbed_env, module):
        importlib.import_module(module)


class TestApplicationAssembly:
    def test_server_imports(self, stubbed_env):
        import server
        assert server.app is not None

    def test_lifecycle_handlers_registered(self, client):
        """Startup seeds the government form catalog; losing it empties the app."""
        import server
        assert len(server.app.router.on_startup) >= 1
        assert len(server.app.router.on_shutdown) >= 1

    def test_cors_middleware_present(self, client):
        import server
        names = [m.cls.__name__ for m in server.app.user_middleware]
        assert "CORSMiddleware" in names

    def test_every_route_module_contributes_routes(self, stubbed_env):
        from routes import register_all_routes
        paths = {r.path for r in register_all_routes().routes}
        # One representative path per route module, so a module that stops
        # registering is caught rather than silently disappearing.
        for expected in [
            "/api/auth/send-otp", "/api/chat", "/api/profile/{user_id}",
            "/api/schemes", "/api/generate-pdf", "/api/demo/status",
            "/api/v2/schemes", "/api/discovery/status", "/api/exams",
            "/api/reports/schemes-excel", "/api/notifications/preferences/{user_id}",
            "/api/forms/catalog", "/api/verify/application", "/api/review/queue",
            "/api/dpdp/notice", "/api/dpdp/my-data/{user_id}",
            "/api/dpdp/terms", "/api/dpdp/accessibility",
            "/api/dpdp/nominee/{user_id}",
            "/api/kyc/methods", "/api/kyc/aadhaar/offline-xml",
            "/api/forms/catalog-states",
            "/api/i18n/languages", "/api/i18n/bundle/{code}",
        ]:
            assert expected in paths, f"{expected} is not registered"


class TestRoutingWorks:
    """Requests through the real app, not a hand-assembled router."""

    def test_root_endpoint(self, client):
        r = client.get("/api/")
        assert r.status_code == 200
        assert "version" in r.json()

    def test_unknown_path_is_404(self, client):
        """Confirms the router is mounted — a 404 here, not a 500 or a hang."""
        assert client.get("/api/no-such-endpoint").status_code == 404

    def test_form_catalog_serves_without_a_database(self, client):
        """The app must be usable on a fresh deploy with no data seeded yet."""
        r = client.get("/api/forms/catalog")
        assert r.status_code == 200
        assert r.json()["count"] >= 5

    def test_field_validation_serves(self, client):
        r = client.post("/api/verify/fields",
                        json={"profile": {"aadhaar_number": "123456789012"}})
        assert r.status_code == 200 and r.json()["blocking"] is True

    def test_eligibility_serves(self, client):
        r = client.post("/api/verify/eligibility", json={
            "profile": {"age": 70, "is_bpl": "Yes"},
            "scheme_name": "Indira Gandhi National Old Age Pension",
        })
        assert r.status_code == 200 and r.json()["eligible"] is True

    def test_reviewer_routes_are_gated(self, client):
        """Reviewer data describes suspicion about named people."""
        assert client.get("/api/review/queue").status_code == 403

    def test_admin_routes_are_gated(self, client):
        assert client.post("/api/forms/refresh", json={}).status_code == 403

    def test_citizen_case_status_is_not_gated(self, client):
        """People are entitled to know their own application is being checked."""
        assert client.get("/api/review/my-cases/anyone").status_code == 200

    def test_terms_of_service_is_public(self, client):
        """IT Rules 3(1)(a): the user agreement must be published."""
        r = client.get("/api/dpdp/terms")
        assert r.status_code == 200
        body = r.json()
        assert body["critical_disclosures"] and body["your_obligations"]

    def test_privacy_notice_is_public(self, client):
        """s5: a person must be able to read the notice before handing over data."""
        r = client.get("/api/dpdp/notice")
        assert r.status_code == 200
        assert r.json()["purposes"] and r.json()["your_rights"]

    def test_dpdp_compliance_routes_are_gated(self, client):
        assert client.get("/api/dpdp/compliance/registry").status_code == 403
        assert client.get("/api/dpdp/compliance/audit").status_code == 403

    def test_rights_routes_reject_anonymous_callers(self, client):
        """Without this, changing the id in the path reads another person's data."""
        assert client.get("/api/dpdp/my-data/someone").status_code == 401

    def test_rights_routes_reject_cross_user_access(self, client):
        r = client.get("/api/dpdp/my-data/victim", headers={"X-User-Id": "attacker"})
        assert r.status_code == 403


class TestKycRouting:
    """The KYC surface must be reachable, honest, and never a gate."""

    def test_method_list_is_public_and_marks_what_is_unavailable(self, client):
        r = client.get("/api/kyc/methods")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 10
        assert body["kycIsOptional"] is True
        # A method needing a UIDAI licence is listed and marked, not hidden.
        licensed = [m for m in body["methods"] if m["key"] == "aadhaar_otp_ekyc"]
        assert licensed and licensed[0]["usable"] is False

    def test_verification_endpoints_require_a_signed_in_caller(self, client):
        """These carry identity documents; an anonymous caller must not reach them."""
        assert client.post("/api/kyc/aadhaar/secure-qr", json={}).status_code == 401
        assert client.post("/api/kyc/self-declaration", json={}).status_code == 401

    def test_a_malformed_qr_gets_a_bilingual_400_not_a_500(self, client):
        r = client.post("/api/kyc/aadhaar/secure-qr",
                        json={"qr": "http://example.com", "profile": {}},
                        headers={"X-User-Id": "u1"})
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert detail["errorHindi"]

    def test_an_unlisted_method_is_404_not_a_silent_success(self, client):
        assert client.get("/api/kyc/methods/magic-wand").status_code == 404

    def test_scheme_gap_never_reports_a_block(self, client):
        r = client.post("/api/kyc/scheme-gap",
                        json={"outcomes": [], "schemeName": "Ayushman Bharat PM-JAY"},
                        headers={"X-User-Id": "u1"})
        assert r.status_code == 200 and r.json()["canStillApply"] is True

    def test_catalog_can_be_filtered_by_state(self, client):
        r = client.get("/api/forms/catalog?state=Bihar")
        assert r.status_code == 200
        levels = {f["level"] for f in r.json()["forms"]}
        assert "Central" in levels, "a State view must still show Central schemes"
        states = {f["state"] for f in r.json()["forms"] if f["level"] == "State"}
        assert states == {"Bihar"}

    def test_catalog_states_are_listed_for_a_picker(self, client):
        r = client.get("/api/forms/catalog-states")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 10 and body["centralSchemes"] >= 10
        assert all(s["totalAvailable"] > s["stateSchemes"] for s in body["states"])


class TestLanguageRouting:
    """A language picker must be reachable before sign-in, like the notice."""

    def test_language_list_is_public(self, client):
        r = client.get("/api/i18n/languages")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] >= 22
        # Endonyms, or the picker is unusable by the people it is for.
        assert all(l["endonym"] for l in body["languages"])

    def test_a_bundle_serves_every_key_in_any_language(self, client):
        for code in ("ta", "ur", "sat", "klingon"):
            r = client.get(f"/api/i18n/bundle/{code}")
            assert r.status_code == 200, code
            assert r.json()["strings"]["nav.schemes"]

    def test_an_unchecked_translation_warns_the_reader(self, client):
        """Manipuri now has text, and the warning is what makes shipping it
        honest — the reader is the only person who could spot an error, and
        only if told to look."""
        body = client.get("/api/i18n/bundle/mni").json()
        assert body["fullyTranslated"] is True
        assert body["lowConfidence"] is True
        assert body["qualityWarning"] and body["qualityWarningHindi"]

    def test_a_solid_draft_carries_no_standing_warning(self, client):
        body = client.get("/api/i18n/bundle/ta").json()
        assert body["lowConfidence"] is False
        assert not body["qualityWarning"]

    def test_suggestion_follows_the_accept_language_header(self, client):
        r = client.get("/api/i18n/suggest",
                       headers={"Accept-Language": "ml-IN,ml;q=0.9"})
        assert r.status_code == 200 and r.json()["recommended"] == "ml"

    def test_suggestion_prefers_the_citizens_state(self, client):
        r = client.get("/api/i18n/suggest?state=Tamil%20Nadu",
                       headers={"Accept-Language": "hi-IN"})
        assert r.json()["recommended"] == "ta"

    def test_coverage_reports_grade_rather_than_a_bare_percentage(self, client):
        """Full coverage must never read as full confidence."""
        body = client.get("/api/i18n/coverage").json()
        summary = body["summary"]
        assert summary["withTranslations"] == 22
        assert summary["nativelyReviewed"] == 0
        assert summary["lowConfidence"], \
            "22 of 22 with no caveat is the misleading number"
        qualities = {l["quality"] for l in body["byLanguage"]}
        assert {"draft", "low_confidence"} <= qualities

    def test_the_notice_does_not_claim_more_languages_than_it_has(self, client):
        """The interface reaches 14 languages; the consent notice reaches two.
        Reporting them as one number would misstate the validity of a consent."""
        body = client.get("/api/dpdp/languages").json()
        assert set(body["available_now"]) == {"en", "hi"}
        translated_ui = [l for l in body["eighth_schedule"]
                         if l["interface_translated"]]
        assert len(translated_ui) > len(body["available_now"])
