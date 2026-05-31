# SD-only launcher for internal flash.
# Keep game code and assets on /sd/game; internal flash only boots the SD app.

GAME_PATH = "/sd/game"

try:
    from time import sleep_ms
except Exception:
    from time import sleep as _sleep

    def sleep_ms(ms):
        _sleep(ms / 1000)


def _safe_mode(reason):
    print("SAFE MODE")
    print(reason)
    while True:
        sleep_ms(1000)


def _mount_sd():
    try:
        import machine
        import os
    except Exception as exc:
        return False, "machine/os unavailable: %r" % (exc,)

    # Try slot 2 first (common SPI SD mode), then slot 3 fallback.
    try:
        sd = machine.SDCard(slot=2, sck=5, mosi=6, miso=7, cs=4)
        os.mount(sd, "/sd")
        return True, "mounted with slot=2"
    except Exception as exc_slot2:
        try:
            sd = machine.SDCard(slot=3, sck=5, mosi=6, miso=7, cs=4)
            os.mount(sd, "/sd")
            return True, "mounted with slot=3"
        except Exception as exc_slot3:
            msg = "slot2=%r; slot3=%r" % (exc_slot2, exc_slot3)
            return False, msg


def _reset_game_imports():
    import sys

    purge = []
    for name in sys.modules:
        if name in ("app", "app_camera_test", "config", "assets", "state"):
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


class _ModuleProxy:
    def __init__(self, ns):
        self._ns = ns

    def __getattr__(self, name):
        try:
            return self._ns[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == "_ns":
            object.__setattr__(self, name, value)
        else:
            self._ns[name] = value


def _exec_module_from_path(name, path):
    import sys

    ns = {
        "__name__": name,
        "__file__": path,
    }
    with open(path, "r") as handle:
        source = handle.read()
    if name == "app_camera_test":
        print("LOADER_SRC_PATH=%s" % path)
        print("LOADER_SRC_HAS_V2_START=%d" % (1 if ("APP_RUN_START_PHASE_CAMERA_TEST_V2" in source) else 0))
        print("LOADER_SRC_HAS_V2_FAR=%d" % (1 if ("SWAP_FAR_OK_V2" in source) else 0))
    exec(source, ns)
    module = _ModuleProxy(ns)
    sys.modules[name] = module
    return module


def _load_sd_app():
    import os
    import sys

    os.stat(GAME_PATH + "/app.py")
    os.stat(GAME_PATH + "/config.py")
    os.stat(GAME_PATH + "/app_camera_test.py")
    os.chdir(GAME_PATH)
    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)
    while ".frozen" in sys.path:
        sys.path.remove(".frozen")
    sys.path.insert(0, GAME_PATH)
    _reset_game_imports()
    _exec_module_from_path("config", GAME_PATH + "/config.py")
    return _exec_module_from_path("app_camera_test", GAME_PATH + "/app_camera_test.py")


def main():
    ok, detail = _mount_sd()
    if ok:
        print("SD mount: %s" % detail)
    else:
        print("SD mount failed: %s" % detail)
        _safe_mode("sd mount failed")
        return

    try:
        app = _load_sd_app()
        try:
            print("LAUNCHER_APP_TYPE=%s" % type(app).__name__)
        except Exception:
            print("LAUNCHER_APP_TYPE=?")
        try:
            print("LAUNCHER_APP_FILE=%s" % app.__file__)
        except Exception:
            print("LAUNCHER_APP_FILE=?")
        try:
            print("LAUNCHER_APP_RUN=%r" % (app.run,))
        except Exception:
            print("LAUNCHER_APP_RUN=?")
        print("Launcher source: sd")
        try:
            app._boot_source_tag = "SD"
        except Exception:
            pass
        app.run()
    except Exception as exc:
        try:
            import sys
            print("Launcher run crashed")
            sys.print_exception(exc)
        except Exception:
            print("Launcher run crashed: %r" % (exc,))
        _safe_mode("sd app run failed")


if __name__ == "__main__":
    main()
