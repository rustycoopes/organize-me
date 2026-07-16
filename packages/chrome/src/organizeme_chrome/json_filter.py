"""A Jinja `tojson` filter, since Starlette's `Jinja2Templates` (unlike Flask) doesn't register
one. Used to embed the current user's nav-group collapsed state as an Alpine `x-data` attribute.

Escapes the characters that could otherwise break out of an HTML attribute or a `</script>` tag,
mirroring Flask's `htmlsafe_json_dumps`, then marks the result `Markup`-safe so Jinja's normal
autoescaping doesn't double-escape it.
"""

import json

from markupsafe import Markup

_HTML_UNSAFE_CHARS = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    "'": "\\u0027",
}


def tojson_filter(value: object) -> Markup:
    dumped = json.dumps(value)
    for char, escaped in _HTML_UNSAFE_CHARS.items():
        dumped = dumped.replace(char, escaped)
    return Markup(dumped)
