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


def _load_sd_app():
    import os
    import sys

    os.stat(GAME_PATH + "/app.py")
    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)
    sys.path.insert(0, GAME_PATH)
    _reset_game_imports()
    import app
    return app


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
