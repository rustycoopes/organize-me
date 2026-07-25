from organizeme_chrome.static_paths import static_mount_path


def test_static_mount_path_returns_the_service_scoped_prefix() -> None:
    assert static_mount_path("doc-library") == "/doc-library/static"


def test_static_mount_path_has_no_trailing_slash() -> None:
    assert not static_mount_path("event-creator").endswith("/")


def test_static_mount_path_is_pure_given_the_same_service_name() -> None:
    assert static_mount_path("ha-dashboard") == static_mount_path("ha-dashboard")
