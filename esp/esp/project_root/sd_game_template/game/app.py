_boot_source_tag = "UNKNOWN"


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
    exec(source, ns)
    module = _ModuleProxy(ns)
    sys.modules[name] = module
    return module


def run(max_frames=None):
    import sys

    try:
        print("APP_WRAPPER_FILE=%s" % __file__)
    except Exception:
        print("APP_WRAPPER_FILE=?")

    while ".frozen" in sys.path:
        sys.path.remove(".frozen")
    _exec_module_from_path("config", "/sd/game/config.py")
    impl = _exec_module_from_path("app_camera_test", "/sd/game/app_camera_test.py")
    try:
        print("APP_IMPL_FILE=%s" % impl.__file__)
    except Exception:
        print("APP_IMPL_FILE=?")

    try:
        impl._boot_source_tag = _boot_source_tag
    except Exception:
        pass
    return impl.run(max_frames)

