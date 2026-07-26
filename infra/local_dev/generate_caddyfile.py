"""Renders a local Caddyfile from `infra.path_rules.generate_path_rules()` plus a port map — the
local stand-in for `infra/gcp_lb/generate_url_map.py`'s GCP URL map. See
docs/adr/local-dev-environment-local-reverse-proxy.md.

Run directly to print the generated Caddyfile for the current registry + `infra/local_dev/ports.py`:
    uv run python -m infra.local_dev.generate_caddyfile
"""

from organizeme_chrome.registry import AppEntry

from infra.local_dev.ports import CADDY_LOCAL_PORT, HOST_SERVICE_NAME
from infra.path_rules import HOST_BACKEND, generate_path_rules


def _local_service_name(rule_service: str) -> str:
    # Both `host-backend` and `organizeme-backend` (see infra/gcp_lb/provision.sh's "Backend
    # services" step) point at the same running process in every environment — the Host — so
    # both resolve to this one `ports.py` entry locally too.
    if rule_service == HOST_BACKEND:
        return HOST_SERVICE_NAME
    return rule_service.removesuffix("-backend")


def _handle_block(port: int, *, matcher_name: str | None, matcher_paths: list[str]) -> list[str]:
    lines = []
    if matcher_name is not None:
        lines.append(f"\t@{matcher_name} path {' '.join(matcher_paths)}")
        lines.append(f"\thandle @{matcher_name} {{")
    else:
        lines.append("\thandle {")
    lines.append(f"\t\treverse_proxy localhost:{port} {{")
    # Caddy's reverse_proxy buffers by default; without an immediate flush, event-creator's SSE
    # endpoint (processing-run progress, once that app is onboarded from Slice 4 on) would arrive
    # in one lump instead of streaming — see docs/adr/local-dev-environment-local-reverse-proxy.md
    # "Consequences". Applied to every route rather than special-cased to one path, since there's
    # no real perf cost to immediate flushing on a local proxy.
    lines.append("\t\t\tflush_interval -1")
    lines.append("\t\t}")
    lines.append("\t}")
    return lines


def generate_caddyfile(
    apps: list[AppEntry], ports: dict[str, int], *, caddy_port: int = CADDY_LOCAL_PORT
) -> str:
    """Pure function over the *entire* registry (not any launcher-session subset) plus the port
    map — an app absent from `ports` (not yet onboarded into local dev) is simply omitted from
    the generated config, surfacing as a clean 404/connection-refused through Caddy rather than
    raising. `apply_qa_filter=False`: an app's lack of a QA deployment (`qa_available=False`,
    e.g. ha-dashboard) is a GCP-specific distinction that has no bearing on local dev — there's
    only one local environment, so that app must still get a rule here if it has a local port."""
    rules = generate_path_rules(apps, apply_qa_filter=False)

    lines = [f":{caddy_port} {{"]
    for rule in rules:
        port = ports.get(_local_service_name(rule.service))
        if port is None:
            continue
        lines.extend(_handle_block(port, matcher_name=rule.service, matcher_paths=rule.paths))

    # Mirrors the GCP URL map's own `defaultService` (always the Host) — any path not covered by
    # a more specific rule above (e.g. /health, the Host's own unprefixed /static/*) falls through
    # to the Host here too, instead of a bare 404 that would diverge from real routing.
    default_port = ports.get(HOST_SERVICE_NAME)
    if default_port is not None:
        lines.extend(_handle_block(default_port, matcher_name=None, matcher_paths=[]))

    lines.append("}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    # Side-effect import, same reason as infra/gcp_lb/generate_url_map.py: configures
    # organizeme_chrome's registry source against the Host's own in-process APPS before
    # generate_path_rules() (inside generate_caddyfile()) calls list_apps().
    from app.core import registry as _registry  # noqa: F401
    from organizeme_chrome.registry import list_apps

    from infra.local_dev.ports import PORTS

    print(generate_caddyfile(list_apps(), PORTS))
