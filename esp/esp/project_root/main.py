# SD-only launcher for internal flash.
# Keep game code and assets on /sd/game; internal flash only boots the SD app.

GAME_PATH = "/sd/game"
STAGE_REQUEST_PATH = GAME_PATH + "/save/next_stage.txt"
BOOT_STAGE_PATH = GAME_PATH + "/save/boot_stage.txt"
_preloaded_modules = {}

try:
    from time import sleep_ms
except Exception:
    from time import sleep as _sleep

    def sleep_ms(ms):
        _sleep(ms / 1000)


def _safe_mode(reason):
    _show_boot_screen(0xF800)
    print("SAFE MODE")
    print(reason)
    while True:
        sleep_ms(1000)


def _trace(msg):
    pass


def _show_boot_screen(color=0x001F):
    try:
        import lgfx
        lgfx.init()
        try:
            lgfx.rotation(1)
        except Exception:
            pass
        lgfx.fill(int(color))
    except Exception:
        pass


def _verbose(config=None):
    try:
        return bool(getattr(config, "LAUNCHER_VERBOSE", False))
    except Exception:
        return False


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
        os.stat(GAME_PATH)
        return True, "already mounted"
    except Exception:
        pass
    last_exc = None
    attempt = 0
    while attempt < 5:
        attempt += 1
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
            return True, "mounted with slot=2 width=1 sck=5 mosi=6 miso=7 cs=4 attempt=%d" % attempt
        except Exception as exc_slot2:
            last_exc = exc_slot2
            try:
                os.stat(GAME_PATH)
                return True, "already mounted after slot2=%r" % (exc_slot2,)
            except Exception:
                pass
            sleep_ms(200)
    return False, "slot2=%r" % (last_exc,)


def _reset_game_imports(preserve_map2=False):
    import sys

    purge = []
    for name in sys.modules:
        if preserve_map2 and name in ("map2_app", "map2_elevator"):
            continue
        if name in ("app", "app_camera_test", "map2_app", "map2_elevator", "config", "assets", "state", "stall_trace", "native_submit_glue"):
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

    mpy_path = path[:-3] + ".mpy" if path.endswith(".py") else path + ".mpy"
    try:
        import os
        os.stat(mpy_path)
        if name in sys.modules:
            del sys.modules[name]
        return __import__(name)
    except Exception:
        pass

    ns = {
        "__name__": name,
        "__file__": path,
    }
    with open(path, "r") as handle:
        source = handle.read()
    if name == "app_camera_test" and _verbose(sys.modules.get("config")):
        print("LOADER_SRC_PATH=%s" % path)
        print("LOADER_SRC_HAS_V2_START=%d" % (1 if ("APP_RUN_START_PHASE_CAMERA_TEST_V2" in source) else 0))
        print("LOADER_SRC_HAS_V2_FAR=%d" % (1 if ("SWAP_FAR_OK_V2" in source) else 0))
    exec(source, ns)
    module = _ModuleProxy(ns)
    sys.modules[name] = module
    return module


def _preload_map2_modules(config):
    import sys

    if "map2_app" in _preloaded_modules:
        return _preloaded_modules["map2_app"]
    old_config = sys.modules.get("config")
    sys.modules["config"] = config
    try:
        elevator = _exec_module_from_path("map2_elevator", GAME_PATH + "/map2_elevator.py")
        app = _exec_module_from_path("map2_app", GAME_PATH + "/map2_app.py")
        _preloaded_modules["map2_elevator"] = elevator
        _preloaded_modules["map2_app"] = app
        return app
    except Exception:
        if old_config is not None:
            sys.modules["config"] = old_config
        raise


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


def _load_sd_app(skip_preload=False):
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
    if stage == "stage02" and "map2_app" in _preloaded_modules:
        return _preloaded_modules["map2_app"]
    _reset_game_imports(stage == "stage02" and "map2_app" in _preloaded_modules)
    config = _exec_module_from_path("config", GAME_PATH + "/config.py")
    if not skip_preload:
        try:
            import asset_cache
            asset_cache.preload_map1(config, int(config.SCREEN_W), int(config.SCREEN_H))
            asset_cache.preload_map2(config, int(config.SCREEN_W), int(config.SCREEN_H))
            _preload_map2_modules(config)
        except Exception as exc:
            print("ASSET_PRELOAD_EXCEPTION %r" % (exc,))
    if _verbose(config):
        print("LAUNCHER_STAGE=%s" % stage)
    return _exec_module_from_path(app_name, app_path)


def main():
    import sys

    _trace("MAIN_ENTER")
    _show_boot_screen(0x001F)
    ok, detail = _mount_sd()
    if ok:
        _trace("MOUNT_OK:%s" % detail)
        _show_boot_screen(0x07E0)
    else:
        _trace("MOUNT_FAIL:%s" % detail)
        print("SD mount failed: %s" % detail)
        _safe_mode("sd mount failed")
        return

    stage_switch_pending = False
    joy_centers = None
    while True:
        try:
            _trace("LOAD_SD_APP_BEGIN")
            app = _load_sd_app(stage_switch_pending)
            _trace("LOAD_SD_APP_OK")
            if _verbose(sys.modules.get("config")):
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
            try:
                app._stage_switch_from_previous = stage_switch_pending
            except Exception:
                pass
            try:
                if joy_centers is not None:
                    app._joy_centers_from_previous = joy_centers
            except Exception:
                pass
            stage_switch_pending = False
            _trace("APP_RUN_BEGIN")
            app.run()
            _trace("APP_RUN_RETURN")
            break
        except Exception as exc:
            if str(exc) == "STAGE_SWITCH":
                try:
                    joy_centers = app.get_joy_centers()
                except Exception:
                    joy_centers = None
                try:
                    import lgfx
                    if hasattr(lgfx, "band_pipeline_tail_wait"):
                        lgfx.band_pipeline_tail_wait()
                except Exception:
                    pass
                if _verbose(sys.modules.get("config")):
                    print("LAUNCHER_STAGE_SWITCH")
                stage_switch_pending = True
                continue
            _trace("APP_RUN_EXCEPTION:%r" % (exc,))
            try:
                print("Launcher run crashed")
                sys.print_exception(exc)
            except Exception:
                print("Launcher run crashed: %r" % (exc,))
            _safe_mode("sd app run failed")


if __name__ == "__main__":
    main()
