"""Slice R5: the LB's URL-map path rules must be generated from the R3 app-registry
(organizeme_chrome.registry), not hand-maintained — see infra/gcp_lb/generate_url_map.py.
"""

import pytest
import yaml
from organizeme_chrome.registry import AppEntry, AppNavItem

from infra.gcp_lb.generate_url_map import HOST_PATHS, generate_path_rules, to_url_map_yaml


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
    assert set(app_rule.paths) == {"/dashboard", "/upload"}


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
    assert future_rule.paths == ["/future-thing"]


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


def test_url_map_yaml_references_backend_services_by_full_resource_path() -> None:
    # Bare service names are silently misresolved by `gcloud compute url-maps import` — the
    # schema expects a resource path (or self-link), not a short name.
    apps = [AppEntry(service_name="organizeme", nav=[AppNavItem("/dashboard", "Dashboard")], settings_tabs=[])]
    rules = generate_path_rules(apps=apps)

    rendered = to_url_map_yaml(rules, name="organizeme-qa-url-map", default_service="host-backend")
    # $LB_HOST is a provision.sh-substituted placeholder, not valid YAML on its own — swap in a
    # real host string before parsing.
    parsed = yaml.safe_load(rendered.replace("$LB_HOST", "organizeme.qa.russcoopersoftware.com"))

    assert parsed["name"] == "organizeme-qa-url-map"
    assert parsed["defaultService"] == "global/backendServices/host-backend"
    matcher = parsed["pathMatchers"][0]
    assert matcher["defaultService"] == "global/backendServices/host-backend"
    services_by_path_rule = {
        tuple(rule["paths"]): rule["service"] for rule in matcher["pathRules"]
    }
    assert services_by_path_rule[tuple(HOST_PATHS)] == "global/backendServices/host-backend"
    assert services_by_path_rule[("/dashboard",)] == "global/backendServices/organizeme-backend"
    assert parsed["hostRules"][0]["hosts"] == ["organizeme.qa.russcoopersoftware.com"]
    assert parsed["hostRules"][0]["pathMatcher"] == "app-registry-path-matcher"
