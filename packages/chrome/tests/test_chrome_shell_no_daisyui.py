import re

from organizeme_chrome.paths import chrome_templates_dir

# DaisyUI component class tokens the design-refresh restyle removes. Matched as whole class
# tokens (word-boundaried) so real replacement classes like "bg-mist" or "border-ink-2/10" don't
# false-positive against a bare substring like "menu"/"tab" appearing inside them.
_DAISYUI_CLASS_TOKENS = [
    "drawer",
    "drawer-toggle",
    "drawer-content",
    "drawer-side",
    "drawer-overlay",
    "menu",
    "btn",
    "btn-square",
    "btn-ghost",
    "btn-sm",
    "btn-block",
    "navbar",
    "tabs",
    "tabs-bordered",
    "tab-active",
    "base-100",
    "base-300",
]

_SHELL_TEMPLATES = [
    "chrome_authenticated_base.html",
    "macros/chrome_nav.html",
    "macros/chrome_tabs.html",
]


def test_shell_templates_contain_no_daisyui_classes() -> None:
    templates_dir = chrome_templates_dir()

    for relative_path in _SHELL_TEMPLATES:
        content = (templates_dir / relative_path).read_text(encoding="utf-8")
        # Only inspect actual class-attribute values (static `class="..."` and Alpine
        # `:class="..."`) - prose in {# ... #} doc comments (e.g. "tabs dynamically") legitimately
        # uses these English words and isn't a class name.
        class_values = re.findall(r':?class="([^"]*)"', content)

        for token in _DAISYUI_CLASS_TOKENS:
            for class_value in class_values:
                assert token not in class_value.split(), (
                    f"{relative_path} still contains {token!r} in class=\"{class_value}\""
                )
