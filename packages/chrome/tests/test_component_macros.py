from collections.abc import Iterator

import pytest
from conftest import FakeRegistrySource
from jinja2 import Environment
from markupsafe import Markup

from organizeme_chrome.registry import AppEntry, configure_registry_source, reset_registry_source
from organizeme_chrome.templating import register_chrome


@pytest.fixture(autouse=True)
def _configure_sample_registry() -> Iterator[None]:
    # register_chrome() calls get_app(), which needs a configured RegistrySource - see
    # test_templating.py's identical fixture.
    configure_registry_source(FakeRegistrySource([AppEntry(service_name="organizeme", nav=[], settings_tabs=[])]))
    yield
    reset_registry_source()


def _render(env: Environment, template: str, macro: str, *args: object, **kwargs: object) -> str:
    module = env.get_template(template).module
    return str(getattr(module, macro)(*args, **kwargs))


def _env() -> Environment:
    env = Environment()
    register_chrome(env, app_service_name="organizeme")
    return env


def test_button_renders_a_real_button_by_default() -> None:
    html = _render(_env(), "components/button.html", "button", "Save")

    assert "<button" in html
    assert 'type="button"' in html
    assert "Save" in html
    assert "bg-flame" in html  # primary variant, default


def test_button_secondary_and_ghost_variants_use_distinct_classes() -> None:
    secondary = _render(_env(), "components/button.html", "button", "Go", variant="secondary")
    ghost = _render(_env(), "components/button.html", "button", "Go", variant="ghost")

    assert "bg-cobalt" in secondary
    assert "border-ink-2/30" in ghost


def test_button_rejects_an_unknown_variant() -> None:
    from jinja2 import UndefinedError

    with pytest.raises(UndefinedError):
        _render(_env(), "components/button.html", "button", "Go", variant="not-a-variant")


def test_button_renders_an_anchor_when_href_is_given() -> None:
    html = _render(_env(), "components/button.html", "button", "Docs", href="/docs")

    assert "<a" in html
    assert 'href="/docs"' in html
    assert "<button" not in html


def test_button_disabled_sets_native_attribute() -> None:
    html = _render(_env(), "components/button.html", "button", "Save", disabled=True)

    assert "disabled" in html


def test_button_density_changes_padding_scale() -> None:
    product = _render(_env(), "components/button.html", "button", "Go", density="product")
    marketing = _render(_env(), "components/button.html", "button", "Go", density="marketing")

    assert "px-3" in product
    assert "px-5" in marketing


def test_input_renders_label_and_associated_field() -> None:
    html = _render(_env(), "components/input.html", "input", "email", "Email", required=True)

    assert 'for="field-email"' in html
    assert 'id="field-email"' in html
    assert 'name="email"' in html
    assert "required" in html


def test_input_without_error_has_no_invalid_wiring() -> None:
    html = _render(_env(), "components/input.html", "input", "email", "Email")

    assert 'aria-invalid' not in html
    assert 'role="alert"' not in html


def test_input_error_marks_field_invalid_and_renders_message() -> None:
    html = _render(
        _env(), "components/input.html", "input", "password", "Password", error="Too short."
    )

    assert 'aria-invalid="true"' in html
    assert 'aria-describedby="field-password-error"' in html
    assert 'id="field-password-error"' in html
    assert 'role="alert"' in html
    assert "Too short." in html
    assert "border-flame" in html


def test_input_renders_optional_minlength_and_autocomplete() -> None:
    html = _render(
        _env(),
        "components/input.html",
        "input",
        "password",
        "Password",
        type="password",
        minlength=8,
        autocomplete="new-password",
    )

    assert 'minlength="8"' in html
    assert 'autocomplete="new-password"' in html


def test_alert_static_message_uses_variant_classes_and_icon() -> None:
    html = _render(_env(), "components/alert.html", "alert", "Could not save.", variant="danger")

    assert 'role="alert"' in html
    assert "Could not save." in html
    assert "bg-flame-tint" in html
    assert "<svg" in html


def test_alert_x_show_wires_visibility_and_defaults_x_text_to_it() -> None:
    html = _render(_env(), "components/alert.html", "alert", variant="danger", x_show="error")

    assert 'x-show="error"' in html
    assert "x-cloak" in html
    assert 'x-text="error"' in html


def test_alert_info_variant_uses_cobalt() -> None:
    html = _render(_env(), "components/alert.html", "alert", "Saved.", variant="info")

    assert "bg-cobalt-tint" in html


def test_badge_uses_variant_classes() -> None:
    html = _render(_env(), "components/badge.html", "badge", "New", variant="primary")

    assert "New" in html
    assert "bg-flame-tint" in html


def test_status_dot_hides_status_text_when_no_label_given() -> None:
    html = _render(_env(), "components/status_dot.html", "status_dot", "success")

    assert 'class="sr-only"' in html
    assert "bg-sage" in html


def test_status_dot_shows_visible_label_when_given() -> None:
    html = _render(_env(), "components/status_dot.html", "status_dot", "danger", label="Offline")

    assert "Offline" in html
    assert "bg-flame" in html


def test_card_shell_renders_title_and_caller_body() -> None:
    env = _env()
    card_shell = getattr(env.get_template("components/card_shell.html").module, "card_shell")

    html = str(card_shell(title="Storage", caller=lambda: Markup("<p>Body</p>")))

    assert "Storage" in html
    assert "<p>Body</p>" in html


def test_card_shell_omits_heading_when_no_title() -> None:
    env = _env()
    card_shell = getattr(env.get_template("components/card_shell.html").module, "card_shell")

    html = str(card_shell(caller=lambda: Markup("<p>Body</p>")))

    assert "<h2" not in html
