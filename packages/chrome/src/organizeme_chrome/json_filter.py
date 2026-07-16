"""A Jinja `tojson` filter, since Starlette's `Jinja2Templates` (unlike Flask) doesn't register
one. Used to embed the current user's nav-group collapsed state as an Alpine `x-data` attribute.

Deliberately NOT Flask's `htmlsafe_json_dumps` approach (replacing HTML-special characters with
JS unicode escapes like `\\u0022`): that only works for content placed inside a `<script>` body,
where HTML-entity decoding never happens. Here the JSON is embedded inside an HTML *attribute*
value, where the browser's HTML parser decodes entities (`&#34;` -> `"`) before Alpine ever reads
the attribute and evaluates it as JS. Standard HTML-entity escaping is therefore both correct and
sufficient: it protects the surrounding attribute markup, and is fully reversed by the time Alpine
parses the string, so the `"` characters JSON needs as string delimiters arrive intact.
"""

import json

from markupsafe import Markup, escape


def tojson_filter(value: object) -> Markup:
    return Markup(escape(json.dumps(value)))
