# Unified acceptance entrypoint.
# main.py always calls test_entry.run() after reset.

GAME_PATH = "/sd/game"

# Set to "FORMAL" to restore formal app startup behavior.
MODE = "TEST"
TEST_MAX_FRAMES = 300


def _gc_collect():
    try:
        import gc

        gc.collect()
    except Exception:
        pass


def _prefer_root_path():
    import sys

    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)


def _ensure_game_path_preferred():
    import sys

    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)
    sys.path.insert(0, GAME_PATH)


def _reset_import_cache():
    import sys

    purge = []
    for name in sys.modules:
        if name in ("app", "config", "assets", "state"):
            purge.append(name)
            continue
        if name == "engine" or name.startswith("engine."):
            purge.append(name)
            continue
        if name == "actors" or name.startswith("actors."):
            purge.append(name)
            continue

    i = 0
    while i < len(purge):
        name = purge[i]
        i += 1
        if name in sys.modules:
            del sys.modules[name]

    _gc_collect()


def _import_root_first():
    _prefer_root_path()
    _reset_import_cache()
    import app
    return app


def _import_sd_first():
    if not _sd_game_app_available():
        raise ImportError("sd game app unavailable")
    _ensure_game_path_preferred()
    _reset_import_cache()
    import app
    return app


def _import_sd_fallback():
    if not _sd_game_app_available():
        raise ImportError("sd game app unavailable")
    _ensure_game_path_preferred()
    _reset_import_cache()
    import app
    return app


def _fmt_exc(exc):
    try:
        return "%s: %s" % (exc.__class__.__name__, exc)
    except Exception:
        return "%r" % (exc,)


def _print_trace(prefix, exc):
    print("%s=%s" % (prefix, _fmt_exc(exc)))
    try:
        import sys

        sys.print_exception(exc)
    except Exception:
        pass


def _print_sd_mount_marker():
    try:
        import os

        os.listdir("/sd")
        print("TEST_ENTRY_SD_MOUNT_OK")
    except Exception:
        print("TEST_ENTRY_SD_MOUNT_FAIL")


def _sd_game_app_available():
    try:
        import os

        os.stat("/sd/game/app.py")
        return True
    except Exception:
        return False


def _detect_app_source(app):
    try:
        path = str(getattr(app, "__file__", ""))
    except Exception:
        path = ""
    if path.startswith("/sd/"):
        return "sd"
    if path:
        return "root"
    return "unknown"


def _import_app():
    root_exc = None
    _gc_collect()

    # 1) Root/internal flash first.
    try:
        return _import_root_first()
    except Exception as exc:
        root_exc = exc

    # 1b) Retry root once after cache purge to reduce transient heap pressure.
    try:
        _gc_collect()
        app = _import_root_first()
        _print_trace("TEST_ENTRY_ROOT_IMPORT_FAIL", root_exc)
        print("TEST_ENTRY_ROOT_IMPORT_RETRY_OK")
        return app
    except Exception:
        pass

    # 2) /sd/game fallback if root app or its dependencies fail.
    try:
        _gc_collect()
        app = _import_sd_fallback()
        _print_trace("TEST_ENTRY_ROOT_IMPORT_FAIL", root_exc)
        return app
    except Exception as sd_exc:
        _print_trace("TEST_ENTRY_ROOT_IMPORT_FAIL", root_exc)
        _print_trace("TEST_ENTRY_SD_IMPORT_FAIL", sd_exc)
        raise


def _import_app_formal_sd_first():
    sd_exc = None
    try:
        return _import_sd_first()
    except Exception as exc:
        sd_exc = exc

    try:
        app = _import_root_first()
        _print_trace("TEST_ENTRY_SD_IMPORT_FAIL", sd_exc)
        return app
    except Exception as root_exc:
        _print_trace("TEST_ENTRY_SD_IMPORT_FAIL", sd_exc)
        _print_trace("TEST_ENTRY_ROOT_IMPORT_FAIL", root_exc)
        raise


def _run_test_mode():
    print("TEST_ENTRY_MODE=TEST")
    _print_sd_mount_marker()

    try:
        app = _import_app()
        source = _detect_app_source(app)
        print("TEST_ENTRY_APP_SOURCE=%s" % source)
        try:
            app._boot_source_tag = "SD" if source == "sd" else "ROOT"
        except Exception:
            pass
        try:
            stage = str(getattr(app.config, "PHASE_ACCEPTANCE_STAGE", "")).upper()
        except Exception:
            stage = ""
        if stage == "PHASE8":
            print("PHASE8_SD_BOOT_OK")
        if getattr(app, "_lgfx", None) is None:
            print("TEST_ENTRY_FAIL_NO_LGFX")
            return False
        app.run(max_frames=TEST_MAX_FRAMES)
        print("PHASE3_RUN_OK")
        print("TEST_ENTRY_PASS")
        return True
    except Exception as exc:
        try:
            import sys

            print("TEST_ENTRY_FAIL")
            sys.print_exception(exc)
        except Exception:
            print("TEST_ENTRY_FAIL: %r" % (exc,))
        return False


def _run_formal_mode():
    print("TEST_ENTRY_MODE=FORMAL")
    _print_sd_mount_marker()
    app = _import_app_formal_sd_first()
    source = _detect_app_source(app)
    print("TEST_ENTRY_APP_SOURCE=%s" % source)
    try:
        app._boot_source_tag = "SD" if source == "sd" else "ROOT"
    except Exception:
        pass
    app.run()


def run():
    mode = (MODE or "").upper()

    if mode == "FORMAL":
        _run_formal_mode()
        return True

    if mode != "TEST":
        print("TEST_ENTRY_UNKNOWN_MODE=%s" % MODE)
        print("TEST_ENTRY_MODE_FALLBACK=TEST")

    return _run_test_mode()
