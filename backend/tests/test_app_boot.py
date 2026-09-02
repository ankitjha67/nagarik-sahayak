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
    "routes.forms", "routes.verification", "routes.review",
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
