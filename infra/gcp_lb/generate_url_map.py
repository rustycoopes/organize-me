"""Renders the GCP Load Balancer's URL-map as YAML from `infra.path_rules.generate_path_rules()` —
see that module for how path rules are derived from the R3 app-registry
(organizeme_chrome.registry). This file owns only the GCP-specific parts: the
`gcloud compute url-maps import` YAML schema (backend-service resource-path refs, path matchers,
host rules) and the CLI entrypoint.

Run directly to print the generated URL map as YAML for `gcloud compute url-maps import`:
    uv run python -m infra.gcp_lb.generate_url_map
"""

# Side-effect import: configures organizeme_chrome's registry source against the Host's own
# in-process APPS (registry-decoupling, organize-me#218) before generate_path_rules() below calls
# list_apps() - see app/core/registry.py's module docstring.
from app.core import registry as _registry  # noqa: F401

# Re-exported explicitly (the `as X` form) for tests/test_url_map_generator.py's existing
# `from infra.gcp_lb.generate_url_map import ...` call site — mypy --strict's
# no_implicit_reexport would otherwise flag these as private to this module.
from infra.path_rules import HOST_BACKEND as HOST_BACKEND
from infra.path_rules import HOST_PATHS as HOST_PATHS
from infra.path_rules import PathRule as PathRule
from infra.path_rules import generate_path_rules as generate_path_rules


def _backend_service_ref(name: str) -> str:
    """`gcloud compute url-maps import`'s YAML schema expects backend services as a resource
    path, not a bare name — a bare name is silently misresolved rather than rejected."""
    return f"global/backendServices/{name}"


def to_url_map_yaml(rules: list[PathRule], *, name: str, default_service: str) -> str:
    """Renders `rules` as a `gcloud compute url-maps import` YAML document."""
    default_ref = _backend_service_ref(default_service)
    lines = [
        f"name: {name}",
        f"defaultService: {default_ref}",
        "pathMatchers:",
        "  - name: app-registry-path-matcher",
        f"    defaultService: {default_ref}",
        "    pathRules:",
    ]
    for rule in rules:
        lines.append(f"      - service: {_backend_service_ref(rule.service)}")
        lines.append("        paths:")
        for path in rule.paths:
            lines.append(f"          - {path}")
    lines.append("hostRules:")
    lines.append("  - hosts:")
    lines.append("      - $LB_HOST")
    lines.append("    pathMatcher: app-registry-path-matcher")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    # provision.sh / provision-prod.sh select which environment's URL map to render; qa stays the
    # default so the existing R5 call site (`uv run python -m infra.gcp_lb.generate_url_map`, no
    # args) is unaffected.
    env = sys.argv[1] if len(sys.argv) > 1 else "qa"
    suffix = "" if env == "qa" else f"-{env}"
    print(
        to_url_map_yaml(
            generate_path_rules(backend_suffix=suffix),
            name=f"organizeme-{env}-url-map",
            default_service=f"{HOST_BACKEND}{suffix}",
        )
    )
