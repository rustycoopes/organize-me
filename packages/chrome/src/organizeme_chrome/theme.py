"""Dark/light mode selector.

Python (User.dark_mode, read at request time) is the single source of truth for *which* mode is
active; the compiled Tailwind CSS (tokens.css's @custom-variant dark) is the source of truth for
*what each mode looks like*. See docs/adr/design-refresh-dark-mode-css-strategy.md.
"""

from typing import Literal


def theme_attr(dark_mode: bool) -> Literal["dark", ""]:
    return "dark" if dark_mode else ""
