# SD-only launcher for internal flash.
# Keep game code and assets on /sd/game; internal flash only boots the SD app.

GAME_PATH = "/sd/game"
STAGE_REQUEST_PATH = GAME_PATH + "/save/next_stage.txt"
BOOT_STAGE_PATH = GAME_PATH + "/save/boot_stage.txt"

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


def _trace(msg):
    pass


def _mount_sd():
    try:
        import machine
        import os
    except Exception as exc:
        return False, "machine/os unavailable: %r" % (exc,)

    # Single supported SD path for the current board wiring.
    try:
        os.mkdir("/sd")
    except Exception:
        pass
    try:
        os.umount("/sd")
    except Exception:
        pass
    try:
        sd = machine.SDCard(
            slot=2,
            width=1,
            sck=5,
            mosi=6,
            miso=7,
            cs=4,
            freq=1000000,
        )
        os.mount(sd, "/sd")
        return True, "mounted with slot=2 width=1 sck=5 mosi=6 miso=7 cs=4"
    except Exception as exc_slot2:
        return False, "slot2=%r" % (exc_slot2,)


def _reset_game_imports():
    import sys

    purge = []
    for name in sys.modules:
        if name in ("app", "app_camera_test", "map2_app", "map2_elevator", "config", "assets", "state"):
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


def _read_stage_request():
    try:
        with open(STAGE_REQUEST_PATH, "r") as handle:
            stage = handle.read().strip()
    except Exception:
        stage = ""
    if stage:
        try:
            import os
            os.remove(STAGE_REQUEST_PATH)
        except Exception:
            pass
        if stage == "stage02":
            return stage
    try:
        with open(BOOT_STAGE_PATH, "r") as handle:
            stage = handle.read().strip()
    except Exception:
        return "map1"
    if stage == "stage02":
        return stage
    return "map1"


def _load_sd_app():
    import os
    import sys

    os.stat(GAME_PATH + "/app.py")
    os.stat(GAME_PATH + "/config.py")
    stage = _read_stage_request()
    app_name = "map2_app" if stage == "stage02" else "app_camera_test"
    app_path = GAME_PATH + "/" + app_name + ".py"
    os.stat(app_path)
    os.chdir(GAME_PATH)
    while GAME_PATH in sys.path:
        sys.path.remove(GAME_PATH)
    while ".frozen" in sys.path:
        sys.path.remove(".frozen")
    sys.path.insert(0, GAME_PATH)
    _reset_game_imports()
    config = _exec_module_from_path("config", GAME_PATH + "/config.py")
    if stage == "map1":
        try:
            import asset_cache
            asset_cache.preload_map2(config, int(config.SCREEN_W), int(config.SCREEN_H))
        except Exception as exc:
            print("MAP2_PRELOAD_EXCEPTION %r" % (exc,))
    print("LAUNCHER_STAGE=%s" % stage)
    return _exec_module_from_path(app_name, app_path)


def main():
    _trace("MAIN_ENTER")
    ok, detail = _mount_sd()
    if ok:
        _trace("MOUNT_OK:%s" % detail)
        print("SD mount: %s" % detail)
    else:
        _trace("MOUNT_FAIL:%s" % detail)
        print("SD mount failed: %s" % detail)
        _safe_mode("sd mount failed")
        return

    while True:
        try:
            _trace("LOAD_SD_APP_BEGIN")
            app = _load_sd_app()
            _trace("LOAD_SD_APP_OK")
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
            _trace("APP_RUN_BEGIN")
            app.run()
            _trace("APP_RUN_RETURN")
            break
        except Exception as exc:
            if str(exc) == "STAGE_SWITCH":
                try:
                    import lgfx
                    if hasattr(lgfx, "band_pipeline_tail_wait"):
                        lgfx.band_pipeline_tail_wait()
                except Exception:
                    pass
                print("LAUNCHER_STAGE_SWITCH")
                continue
            _trace("APP_RUN_EXCEPTION:%r" % (exc,))
            try:
                import sys
                print("Launcher run crashed")
                sys.print_exception(exc)
            except Exception:
                print("Launcher run crashed: %r" % (exc,))
            _safe_mode("sd app run failed")


if __name__ == "__main__":
    main()
