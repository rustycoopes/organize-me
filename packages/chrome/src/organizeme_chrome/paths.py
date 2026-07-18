"""Filesystem paths into this installed package.

Consuming services need these to point their own Tailwind build at chrome's templates (content
glob, for JIT class scanning) and tokens CSS (@import), without hardcoding a guessed
site-packages path. See docs/adr/design-refresh-per-service-tailwind-build.md in the organize-me
repo.
"""

from pathlib import Path


def chrome_package_dir() -> Path:
    """The root of this installed package (.../site-packages/organizeme_chrome)."""
    return Path(__file__).resolve().parent


def chrome_templates_dir() -> Path:
    return chrome_package_dir() / "templates"


def chrome_tokens_css_path() -> Path:
    return chrome_package_dir() / "static" / "css" / "tokens.css"


def chrome_fonts_dir() -> Path:
    return chrome_package_dir() / "static" / "fonts"
