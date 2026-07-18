from organizeme_chrome.registry import AppEntry


class FakeRegistrySource:
    def __init__(self, apps: list[AppEntry]) -> None:
        self._apps = apps

    def get_apps(self) -> list[AppEntry]:
        return self._apps
