"""Provider-neutral path-rule-derivation logic (infra/path_rules.py), extracted from
infra/gcp_lb/generate_url_map.py so a second generator (Slice 2's local Caddyfile generator) can
import it without duplicating the logic — see docs/adr/local-dev-environment-local-reverse-
proxy.md. These cases are duplicated from tests/test_url_map_generator.py's pre-extraction
suite (which still passes unchanged, proving the relocation didn't alter behavior) rather than
moved, so that suite keeps covering the GCP-specific call site end to end.
"""

import pytest
from organizeme_chrome.registry import AppEntry, AppNavItem
from organizeme_chrome.static_paths import static_mount_path

from infra.path_rules import HOST_PATHS, generate_path_rules


def test_host_paths_route_to_the_host_backend() -> None:
    rules = generate_path_rules(apps=[])

    assert len(rules) == 1
    assert rules[0].service == "host-backend"
    assert set(rules[0].paths) == set(HOST_PATHS)


def test_app_nav_paths_route_to_that_apps_backend() -> None:
    apps = [
        AppEntry(
            service_name="organizeme",
            nav=[AppNavItem("/dashboard", "Dashboard"), AppNavItem("/upload", "Upload")],
            settings_tabs=[],
        )
    ]

    rules = generate_path_rules(apps=apps)

    host_rule = next(r for r in rules if r.service == "host-backend")
    app_rule = next(r for r in rules if r.service == "organizeme-backend")
    assert set(host_rule.paths) == set(HOST_PATHS)
    # Every app rule also carries its static-asset wildcard rule (Slice 3) alongside its nav paths.
    assert set(app_rule.paths) == {"/dashboard", "/upload", f"{static_mount_path('organizeme')}/*"}


def test_app_nav_paths_already_owned_by_host_are_not_duplicated() -> None:
    # "organizeme" nav includes /profile, which is also a Host path (auth-owned). The Host rule
    # must win — a path can't appear in two path rules in the same URL map.
    apps = [
        AppEntry(
            service_name="organizeme",
            nav=[AppNavItem("/profile", "Profile"), AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[],
        )
    ]

    rules = generate_path_rules(apps=apps)

    all_paths = [p for rule in rules for p in rule.paths]
    assert all_paths.count("/profile") == 1
    host_rule = next(r for r in rules if r.service == "host-backend")
    assert "/profile" in host_rule.paths
    app_rule = next(r for r in rules if r.service == "organizeme-backend")
    assert "/profile" not in app_rule.paths
    assert "/dashboard" in app_rule.paths


def test_generated_rules_are_driven_by_the_registry_not_hand_maintained() -> None:
    # Prove the generator is a pure function of its input (the registry) rather than a
    # hand-maintained list: a made-up service/path not present in any real registry entry today
    # still produces a matching path rule.
    apps = [
        AppEntry(service_name="future-app", nav=[AppNavItem("/future-thing", "Future")], settings_tabs=[])
    ]

    rules = generate_path_rules(apps=apps)

    future_rule = next(r for r in rules if r.service == "future-app-backend")
    assert future_rule.paths == ["/future-thing", f"{static_mount_path('future-app')}/*"]


def test_second_neg_slot_placeholder_is_ready_for_event_creator() -> None:
    # R6 attaches Event Creator as a second app-registry entry; the generator must already
    # support routing a second app's paths to a distinct backend without code changes here.
    apps = [
        AppEntry(service_name="organizeme", nav=[AppNavItem("/dashboard", "Dashboard")], settings_tabs=[]),
        AppEntry(service_name="event-creator", nav=[AppNavItem("/events", "Events")], settings_tabs=[]),
    ]

    rules = generate_path_rules(apps=apps)

    services = {r.service for r in rules}
    assert services == {"host-backend", "organizeme-backend", "event-creator-backend"}


def test_two_non_host_apps_claiming_the_same_path_is_rejected() -> None:
    # gcloud's url-map import would reject two path rules claiming the same path as ambiguous;
    # catch the registry authoring mistake here instead, with a clear error naming both apps.
    apps = [
        AppEntry(service_name="organizeme", nav=[AppNavItem("/shared", "Shared")], settings_tabs=[]),
        AppEntry(service_name="event-creator", nav=[AppNavItem("/shared", "Shared")], settings_tabs=[]),
    ]

    with pytest.raises(ValueError, match="/shared"):
        generate_path_rules(apps=apps)


def test_app_api_prefixes_produce_a_wildcard_path_rule_for_that_apps_backend() -> None:
    # R7 (#178): the generator must route an app's own API/fragment routes (declared via
    # api_prefixes), not just its nav pages — else the LB falls through to the Host default for
    # everything else the app actually serves.
    apps = [
        AppEntry(
            service_name="event-creator",
            nav=[AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[],
            api_prefixes=["/api/v1/storage-config", "/settings/event-creator"],
        )
    ]

    rules = generate_path_rules(apps=apps)

    app_rule = next(r for r in rules if r.service == "event-creator-backend")
    assert "/dashboard" in app_rule.paths
    # Bare-prefix requests (e.g. GET/PUT /api/v1/storage-config with nothing after it) must be
    # covered too — GCP's `/*` wildcard only matches paths with something after the trailing `/`,
    # never the bare prefix itself. A regression here silently misroutes those to the Host.
    assert "/api/v1/storage-config" in app_rule.paths
    assert "/api/v1/storage-config/*" in app_rule.paths
    assert "/settings/event-creator" in app_rule.paths
    assert "/settings/event-creator/*" in app_rule.paths


def test_app_api_prefixes_do_not_collide_with_the_hosts_fixed_auth_routes() -> None:
    # The Host's own fixed HOST_PATHS list (auth pages, etc.) and an app's api_prefixes describe
    # disjoint path spaces (exact paths vs. wildcard prefixes); an app declaring an api_prefix must
    # never be silently swallowed by / conflict with the Host's own rule.
    apps = [
        AppEntry(
            service_name="event-creator",
            nav=[],
            settings_tabs=[],
            api_prefixes=["/api/v1/storage-config"],
        )
    ]

    rules = generate_path_rules(apps=apps)

    host_rule = next(r for r in rules if r.service == "host-backend")
    app_rule = next(r for r in rules if r.service == "event-creator-backend")
    assert not set(host_rule.paths) & set(app_rule.paths)
    assert "/api/v1/storage-config" in app_rule.paths
    assert "/api/v1/storage-config/*" in app_rule.paths
    assert set(host_rule.paths) == set(HOST_PATHS)


def test_two_apps_claiming_the_same_api_prefix_is_rejected() -> None:
    apps = [
        AppEntry(
            service_name="organizeme", nav=[], settings_tabs=[], api_prefixes=["/api/v1/shared"]
        ),
        AppEntry(
            service_name="event-creator", nav=[], settings_tabs=[], api_prefixes=["/api/v1/shared"]
        ),
    ]

    with pytest.raises(ValueError, match="/api/v1/shared"):
        generate_path_rules(apps=apps)


def test_app_with_no_nav_or_api_prefixes_still_gets_a_rule_for_its_static_wildcard() -> None:
    # Slice 3: every registered app now contributes a PathRule regardless of nav/api_prefixes,
    # since the static-asset wildcard is unconditionally part of its route surface — unlike
    # before this slice, an app couldn't end up with zero paths and simply be omitted.
    apps = [AppEntry(service_name="doc-library", nav=[], settings_tabs=[])]

    rules = generate_path_rules(apps=apps)

    app_rule = next(r for r in rules if r.service == "doc-library-backend")
    assert app_rule.paths == [f"{static_mount_path('doc-library')}/*"]


def test_app_static_asset_prefix_produces_a_wildcard_only_path_rule() -> None:
    # Slice 3 (organize-me#255): static_mount_path() is the shared helper both this generator and
    # each app's own FastAPI static mount derive from — asserting via the helper (not a
    # reconstructed string) so this test would catch the two drifting apart.
    apps = [
        AppEntry(
            service_name="doc-library", nav=[AppNavItem("/doc-library", "Doc Library")], settings_tabs=[]
        )
    ]

    rules = generate_path_rules(apps=apps)

    app_rule = next(r for r in rules if r.service == "doc-library-backend")
    prefix = static_mount_path("doc-library")
    assert f"{prefix}/*" in app_rule.paths
    # Unlike api_prefixes' bare-path rule, only the wildcard form is emitted here — a bare
    # `/doc-library/static` with nothing after it has no file for StaticFiles to serve anyway.
    assert prefix not in app_rule.paths


def test_static_asset_prefix_rule_generated_for_every_app_and_environment() -> None:
    apps = [
        AppEntry(service_name="organizeme", nav=[AppNavItem("/dashboard", "Dashboard")], settings_tabs=[]),
        AppEntry(service_name="event-creator", nav=[AppNavItem("/events", "Events")], settings_tabs=[]),
    ]

    qa_rules = generate_path_rules(apps=apps)
    prod_rules = generate_path_rules(apps=apps, backend_suffix="-prod")

    for rules, suffix in [(qa_rules, ""), (prod_rules, "-prod")]:
        for name in ("organizeme", "event-creator"):
            app_rule = next(r for r in rules if r.service == f"{name}-backend{suffix}")
            assert f"{static_mount_path(name)}/*" in app_rule.paths


def test_two_apps_claiming_the_same_static_prefix_is_rejected() -> None:
    # Not reachable via distinct service_names today (the prefix derives 1:1 from service_name),
    # but the generator should fail loudly rather than silently misroute if the registry ever
    # assigns the same service_name to two entries.
    apps = [
        AppEntry(service_name="doc-library", nav=[], settings_tabs=[]),
        AppEntry(service_name="doc-library", nav=[AppNavItem("/other", "Other")], settings_tabs=[]),
    ]

    with pytest.raises(ValueError, match=r"doc-library/static/\*"):
        generate_path_rules(apps=apps)


def test_backend_suffix_renames_every_backend_for_a_second_environment() -> None:
    # R12: prod needs its own distinctly-named backend services/NEGs (GCP resource names are
    # global, and QA already owns the unsuffixed ones) without duplicating the generator.
    apps = [
        AppEntry(service_name="organizeme", nav=[AppNavItem("/dashboard", "Dashboard")], settings_tabs=[]),
        AppEntry(service_name="event-creator", nav=[AppNavItem("/events", "Events")], settings_tabs=[]),
    ]

    rules = generate_path_rules(apps=apps, backend_suffix="-prod")

    services = {r.service for r in rules}
    assert services == {"host-backend-prod", "organizeme-backend-prod", "event-creator-backend-prod"}


def test_qa_unavailable_app_is_skipped_for_qa_but_included_for_prod() -> None:
    # organize-me#257: ha-dashboard has no QA Cloud Run service/backend
    # (docs/adr/ha-dashboard-no-qa-environment.md) — generating QA's URL map must not emit a path
    # rule for a backend service that was never provisioned there, while prod (which does have the
    # backend) is unaffected.
    apps = [
        AppEntry(
            service_name="ha-dashboard",
            nav=[AppNavItem("/ha-dashboard", "HA Dashboard")],
            settings_tabs=[],
            qa_available=False,
        )
    ]

    qa_rules = generate_path_rules(apps=apps)
    prod_rules = generate_path_rules(apps=apps, backend_suffix="-prod")

    assert {r.service for r in qa_rules} == {"host-backend"}
    prod_rule = next(r for r in prod_rules if r.service == "ha-dashboard-backend-prod")
    assert "/ha-dashboard" in prod_rule.paths
    assert f"{static_mount_path('ha-dashboard')}/*" in prod_rule.paths


def test_apply_qa_filter_false_includes_qa_unavailable_apps_regardless_of_backend_suffix() -> None:
    # infra/local_dev/generate_caddyfile.py (local-dev-environment Slice 2) needs every
    # registered app's rule regardless of its qa_available flag - there's only one local
    # environment, so GCP's QA/prod distinction doesn't apply.
    apps = [
        AppEntry(
            service_name="ha-dashboard",
            nav=[AppNavItem("/ha-dashboard", "HA Dashboard")],
            settings_tabs=[],
            qa_available=False,
        )
    ]

    rules = generate_path_rules(apps=apps, apply_qa_filter=False)

    assert {r.service for r in rules} == {"host-backend", "ha-dashboard-backend"}
    ha_rule = next(r for r in rules if r.service == "ha-dashboard-backend")
    assert "/ha-dashboard" in ha_rule.paths


def test_qa_available_defaults_to_true_so_existing_apps_are_unaffected() -> None:
    apps = [
        AppEntry(service_name="organizeme", nav=[AppNavItem("/dashboard", "Dashboard")], settings_tabs=[])
    ]

    rules = generate_path_rules(apps=apps)

    assert any(r.service == "organizeme-backend" for r in rules)
