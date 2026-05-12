import config

try:
    import lgfx as _lgfx
except Exception:
    _lgfx = None

_boot_source_tag = "UNKNOWN"
_impl = None
_impl_stage = None


def _select_phase_stage():
    stage = str(getattr(config, "PHASE_ACCEPTANCE_STAGE", "PHASE7")).upper()
    if stage in ("PHASE8", "PHASE7", "PHASE6", "PHASE5", "RED_SCREEN_TEST", "PHASE_CAMERA_TEST"):
        return stage
    return "PHASE7"


def _load_impl_for_stage(stage):
    global _impl
    global _impl_stage

    if _impl is not None and _impl_stage == stage:
        return _impl

    if stage == "PHASE8":
        import app_phase8 as impl
    elif stage == "PHASE7":
        import app_phase7 as impl
    else:
        import app_full as impl

    _impl = impl
    _impl_stage = stage
    return impl


def run(max_frames=None):
    stage = _select_phase_stage()
    if stage == "PHASE_CAMERA_TEST":
        import app_camera_test as impl

        try:
            impl._boot_source_tag = _boot_source_tag
        except Exception:
            pass
        return impl.run(max_frames)

    if stage == "RED_SCREEN_TEST":
        if _lgfx is None:
            print("RED_SCREEN_TEST_FAIL: lgfx unavailable")
            return
        _lgfx.init()
        try:
            _lgfx.rotation(1)
        except Exception:
            pass
        if hasattr(_lgfx, "fill"):
            _lgfx.fill(0xF800)
        elif hasattr(_lgfx, "fill_rect"):
            _lgfx.fill_rect(0, 0, int(config.SCREEN_W), int(config.SCREEN_H), 0xF800)
        print("RED_SCREEN_TEST_OK")
        return

    impl = _load_impl_for_stage(stage)

    try:
        impl._boot_source_tag = _boot_source_tag
    except Exception:
        pass

    return impl.run(max_frames)
