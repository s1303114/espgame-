# Main entry for internal flash.
# Fixed launcher: always run test_entry.run() after reset.

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


def _is_missing_module(exc, module_name):
    msg = str(exc).lower()
    return ("no module named" in msg) and (module_name.lower() in msg)


def _load_test_entry():
    import sys

    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)
    if "test_entry" in sys.modules:
        del sys.modules["test_entry"]
    import test_entry
    return test_entry, "root"


def _load_test_entry_from_sd():
    import sys

    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)
    sys.path.insert(0, GAME_PATH)
    if "test_entry" in sys.modules:
        del sys.modules["test_entry"]
    import test_entry
    return test_entry, "sd"


def main():
    root_exc = None
    try:
        test_entry, source = _load_test_entry()
    except Exception as exc:
        root_exc = exc

        ok, detail = _mount_sd()
        if ok:
            print("SD mount: %s" % detail)
        else:
            print("SD mount skipped: %s" % detail)

        try:
            test_entry, source = _load_test_entry_from_sd()
        except Exception as sd_exc:
            try:
                import sys

                print("Launcher import crashed (root)")
                sys.print_exception(root_exc)
                print("Launcher import crashed (sd)")
                sys.print_exception(sd_exc)
            except Exception:
                print("Launcher import crashed root=%r sd=%r" % (root_exc, sd_exc))
            _safe_mode("test_entry load failed")
            return

    try:
        print("Launcher source: %s" % source)
        test_entry.run()
    except Exception as exc:
        try:
            import sys
            print("Launcher run crashed")
            sys.print_exception(exc)
        except Exception:
            print("Launcher run crashed: %r" % (exc,))
        _safe_mode("test_entry run failed")


if __name__ == "__main__":
    main()
