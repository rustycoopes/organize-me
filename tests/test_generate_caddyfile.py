"""infra/local_dev/generate_caddyfile.py: pure-function unit tests against constructed AppEntry
objects and a constructed port map — no real Caddy binary/filesystem/subprocess — mirroring
tests/test_path_rules.py and tests/test_url_map_generator.py's existing style.
"""

from organizeme_chrome.registry import AppEntry, AppNavItem
from organizeme_chrome.static_paths import static_mount_path

from infra.local_dev.generate_caddyfile import generate_caddyfile
from infra.path_rules import HOST_PATHS


def test_host_paths_route_to_the_hosts_own_port() -> None:
    caddyfile = generate_caddyfile([], {"organizeme": 8000}, caddy_port=10000)

    assert caddyfile.startswith(":10000 {")
    assert "@host-backend path" in caddyfile
    for path in HOST_PATHS:
        assert path in caddyfile
    assert "reverse_proxy localhost:8000" in caddyfile


def test_organizeme_backend_and_host_backend_share_the_same_port() -> None:
    # host-backend and organizeme-backend are two distinct GCP backend services that both point
    # at the same running process (see infra/gcp_lb/provision.sh) - locally that's one port.
    apps = [
        AppEntry(
            service_name="organizeme",
            nav=[AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[],
        )
    ]

    caddyfile = generate_caddyfile(apps, {"organizeme": 8000}, caddy_port=10000)

    assert "@host-backend" in caddyfile
    assert "@organizeme-backend" in caddyfile
    assert caddyfile.count("reverse_proxy localhost:8000") >= 2


def test_app_with_its_own_port_gets_its_own_reverse_proxy_rule() -> None:
    apps = [
        AppEntry(
            service_name="event-creator",
            nav=[AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[],
        )
    ]

    caddyfile = generate_caddyfile(
        apps, {"organizeme": 8000, "event-creator": 8001}, caddy_port=10000
    )

    assert "@event-creator-backend path" in caddyfile
    assert "/dashboard" in caddyfile
    assert f"{static_mount_path('event-creator')}/*" in caddyfile
    assert "reverse_proxy localhost:8001" in caddyfile


def test_app_absent_from_ports_is_omitted_rather_than_raising() -> None:
    # Proves the generator is a pure function of the whole registry, not the launcher's
    # session-selected subset: doc-library has a path rule (from the registry) but no local port
    # assigned yet - it must simply not appear, not raise.
    apps = [
        AppEntry(service_name="organizeme", nav=[], settings_tabs=[]),
        AppEntry(
            service_name="doc-library",
            nav=[AppNavItem("/doc-library", "Doc Library")],
            settings_tabs=[],
        ),
    ]

    caddyfile = generate_caddyfile(apps, {"organizeme": 8000}, caddy_port=10000)

    assert "doc-library" not in caddyfile


def test_registry_wide_rules_included_regardless_of_which_apps_were_started_this_session() -> None:
    # The port map can carry entries for apps the launcher never actually started this session
    # (e.g. already onboarded via ports.py in a later slice, just not passed to --apps) - the
    # generator must still emit their rules, proving it isn't scoped to a launcher session.
    apps = [
        AppEntry(service_name="organizeme", nav=[], settings_tabs=[]),
        AppEntry(
            service_name="event-creator",
            nav=[AppNavItem("/events", "Events")],
            settings_tabs=[],
        ),
        AppEntry(
            service_name="doc-library",
            nav=[AppNavItem("/doc-library", "Doc Library")],
            settings_tabs=[],
        ),
    ]
    ports = {"organizeme": 8000, "event-creator": 8001, "doc-library": 8002}

    caddyfile = generate_caddyfile(apps, ports, caddy_port=10000)

    assert "@event-creator-backend" in caddyfile
    assert "@doc-library-backend" in caddyfile
    assert "reverse_proxy localhost:8001" in caddyfile
    assert "reverse_proxy localhost:8002" in caddyfile


def test_unmatched_paths_fall_through_to_the_host_by_default() -> None:
    # Mirrors the GCP URL map's own defaultService (always the Host) - e.g. /health isn't in
    # HOST_PATHS nor any app's nav, but must still route somewhere sane rather than 404.
    caddyfile = generate_caddyfile([], {"organizeme": 8000}, caddy_port=10000)

    assert "\thandle {\n" in caddyfile
    # The bare fallback handle block is the last one, after every named-matcher block.
    assert caddyfile.rstrip().endswith("}")


def test_every_reverse_proxy_block_flushes_immediately_for_sse_readiness() -> None:
    apps = [
        AppEntry(
            service_name="event-creator",
            nav=[AppNavItem("/dashboard", "Dashboard")],
            settings_tabs=[],
        )
    ]

    caddyfile = generate_caddyfile(
        apps, {"organizeme": 8000, "event-creator": 8001}, caddy_port=10000
    )

    assert caddyfile.count("flush_interval -1") == caddyfile.count("reverse_proxy")


def test_caddy_port_controls_the_listen_address() -> None:
    caddyfile = generate_caddyfile([], {"organizeme": 8000}, caddy_port=12345)

    assert caddyfile.startswith(":12345 {")


def test_default_caddy_port_matches_ports_module_constant() -> None:
    from infra.local_dev.ports import CADDY_LOCAL_PORT

    caddyfile = generate_caddyfile([], {"organizeme": 8000})

    assert caddyfile.startswith(f":{CADDY_LOCAL_PORT} {{")


def test_qa_unavailable_app_still_gets_a_local_rule_when_it_has_a_port() -> None:
    # ha-dashboard sets qa_available=False in the real registry (no QA Cloud Run deployment) -
    # generate_path_rules() drops such apps when called with its GCP-facing defaults, but that
    # QA/prod distinction is meaningless locally (there's only one local environment), so the
    # Caddyfile generator must not inherit that filtering. Regression test for a bug where
    # generate_caddyfile(apps, ports) silently omitted a qa_available=False app even though it
    # had a local port assigned.
    apps = [
        AppEntry(
            service_name="ha-dashboard",
            nav=[AppNavItem("/ha-dashboard", "HA Dashboard")],
            settings_tabs=[],
            qa_available=False,
        )
    ]

    caddyfile = generate_caddyfile(
        apps, {"organizeme": 8000, "ha-dashboard": 8003}, caddy_port=10000
    )

    assert "@ha-dashboard-backend" in caddyfile
    assert "/ha-dashboard" in caddyfile
    assert "reverse_proxy localhost:8003" in caddyfile
