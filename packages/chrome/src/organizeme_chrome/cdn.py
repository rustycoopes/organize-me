"""CDN-hosted script references that are out of scope for the compiled-CSS build pipeline.

Alpine.js is a JS framework, not part of the Tailwind/DaisyUI styling stack this package now
compiles - it stays CDN-loaded until/unless a future feature decides otherwise.
"""

ALPINE_CDN = "https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"
