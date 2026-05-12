try:
    import ujson as json
except Exception:
    import json

try:
    import os
except Exception:
    os = None

try:
    import config
except Exception:
    config = None


_ALLOWED_REASONS = ("manual", "deterministic", "stage_change")
_active_path = None
_volatile_save = None


def _clone_default():
    return {
        "highest_stage": "stage01",
        "current_stage": "stage01",
        "player": {"hp": 5, "x": 32, "y": 208},
        "settings": {"debug": False, "audio": True},
    }


def get_default_save():
    return _clone_default()


def _candidate_paths(path=None):
    paths = []
    if path:
        paths.append(path)
    else:
        save_path = None
        if config is not None:
            save_path = getattr(config, "SAVE_PATH", None)
        if save_path:
            paths.append(save_path)

    for p in ("/save/save0.json", "save/save0.json"):
        if p not in paths:
            paths.append(p)
    return paths


def _merge_with_default(raw):
    base = _clone_default()
    if not isinstance(raw, dict):
        return base

    if isinstance(raw.get("highest_stage"), str):
        base["highest_stage"] = raw["highest_stage"]
    if isinstance(raw.get("current_stage"), str):
        base["current_stage"] = raw["current_stage"]

    player = raw.get("player")
    if isinstance(player, dict):
        if "hp" in player:
            base["player"]["hp"] = int(player["hp"])
        if "x" in player:
            base["player"]["x"] = int(player["x"])
        if "y" in player:
            base["player"]["y"] = int(player["y"])

    settings = raw.get("settings")
    if isinstance(settings, dict):
        if "debug" in settings:
            base["settings"]["debug"] = bool(settings["debug"])
        if "audio" in settings:
            base["settings"]["audio"] = bool(settings["audio"])

    return base


def _ensure_parent_dir(path):
    if os is None:
        return False
    if not path:
        return False

    slash = path.rfind("/")
    if slash <= 0:
        return True
    parent = path[:slash]
    if not parent:
        return True

    parts = parent.split("/")
    cur = ""
    i = 0
    while i < len(parts):
        seg = parts[i]
        i += 1
        if seg == "":
            continue
        if cur == "":
            cur = "/" + seg
        else:
            cur = cur + "/" + seg
        try:
            os.mkdir(cur)
        except Exception:
            pass
    return True


def _read_json(path):
    with open(path, "r") as fp:
        return json.load(fp)


def _write_json(path, data):
    _ensure_parent_dir(path)
    with open(path, "w") as fp:
        json.dump(data, fp)


def _normalize_payload(payload):
    if isinstance(payload, dict):
        if "player" in payload and "settings" in payload:
            return _merge_with_default(payload)
    return _merge_with_default(None)


def _extract_payload(state_or_runtime):
    if isinstance(state_or_runtime, dict):
        return _merge_with_default(state_or_runtime)

    if hasattr(state_or_runtime, "to_save_dict"):
        try:
            return _merge_with_default(state_or_runtime.to_save_dict())
        except Exception:
            return _clone_default()

    out = _clone_default()
    if hasattr(state_or_runtime, "highest_stage"):
        out["highest_stage"] = str(getattr(state_or_runtime, "highest_stage"))
    if hasattr(state_or_runtime, "current_stage"):
        out["current_stage"] = str(getattr(state_or_runtime, "current_stage"))

    player = getattr(state_or_runtime, "player", None)
    if player is not None:
        out["player"]["hp"] = int(getattr(player, "hp", out["player"]["hp"]))
        out["player"]["x"] = int(getattr(player, "x", out["player"]["x"]))
        out["player"]["y"] = int(getattr(player, "y", out["player"]["y"]))

    if hasattr(state_or_runtime, "debug_enabled"):
        out["settings"]["debug"] = bool(getattr(state_or_runtime, "debug_enabled"))

    return out


def ensure_default_save(path=None):
    global _active_path, _volatile_save

    data = load_save(path)
    if _active_path is not None:
        return data

    paths = _candidate_paths(path)
    i = 0
    while i < len(paths):
        p = paths[i]
        i += 1
        try:
            _write_json(p, data)
            _active_path = p
            _volatile_save = data
            return data
        except Exception:
            continue

    _volatile_save = data
    return data


def load_save(path=None):
    global _active_path, _volatile_save

    paths = _candidate_paths(path)
    i = 0
    while i < len(paths):
        p = paths[i]
        i += 1
        try:
            raw = _read_json(p)
            data = _merge_with_default(raw)
            _active_path = p
            _volatile_save = data
            return data
        except Exception:
            continue

    data = _clone_default()
    _volatile_save = data
    return data


def save_game(state_or_runtime, reason, path=None):
    global _active_path, _volatile_save

    if reason not in _ALLOWED_REASONS:
        print("PHASE8_SAVE_REASON_INVALID")
        return False

    payload = _extract_payload(state_or_runtime)

    paths = []
    if path is not None:
        paths = [path]
    else:
        if _active_path is not None:
            paths.append(_active_path)
        base = _candidate_paths(None)
        i = 0
        while i < len(base):
            p = base[i]
            if p not in paths:
                paths.append(p)
            i += 1

    i = 0
    while i < len(paths):
        p = paths[i]
        i += 1
        try:
            _write_json(p, payload)
            _active_path = p
            _volatile_save = payload
            return True
        except Exception:
            continue

    _volatile_save = payload
    return False


def save(path, data):
    payload = _normalize_payload(data)
    return save_game(payload, "manual", path=path)
