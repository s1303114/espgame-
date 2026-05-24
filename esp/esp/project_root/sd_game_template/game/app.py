import config

_boot_source_tag = "UNKNOWN"


def run(max_frames=None):
    import app_camera_test as impl

    try:
        impl._boot_source_tag = _boot_source_tag
    except Exception:
        pass
    return impl.run(max_frames)

