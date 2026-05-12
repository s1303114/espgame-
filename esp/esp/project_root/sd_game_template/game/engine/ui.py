import config


SAVE_STATUS_NEUTRAL = "neutral"
SAVE_STATUS_OK = "ok"
SAVE_STATUS_FAIL = "fail"


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _hud_rect():
    h = int(getattr(config, "PHASE8_HUD_HEIGHT", 16))
    if h < 16:
        h = 16
    if h > 20:
        h = 20
    return 0, 0, int(config.SCREEN_W), h


def get_hud_rect():
    return _hud_rect()


def build_snapshot(hp, max_hp, debug_enabled, save_status):
    hp_v = int(hp)
    hp_max = int(max_hp)
    if hp_max < 1:
        hp_max = 1
    if hp_v < 0:
        hp_v = 0
    if hp_v > hp_max:
        hp_v = hp_max

    if save_status not in (SAVE_STATUS_NEUTRAL, SAVE_STATUS_OK, SAVE_STATUS_FAIL):
        save_status = SAVE_STATUS_NEUTRAL

    return {
        "hp": hp_v,
        "max_hp": hp_max,
        "debug_enabled": bool(debug_enabled),
        "save_status": save_status,
    }


def compose_hud(snapshot, out_drawables, out_rects):
    # Reuse caller-provided containers to avoid per-frame allocations.
    del out_drawables[:]
    out_rects.clear()

    hud_x, hud_y, hud_w, hud_h = _hud_rect()

    # Full HUD baseline background.
    out_drawables.append((hud_x, hud_y, hud_w, hud_h, int(config.COLOR_UI_BG)))
    out_rects["hud_bg"] = (hud_x, hud_y, hud_w, hud_h)

    # HP bar (left)
    hp_box_x = hud_x + 4
    hp_box_y = hud_y + 3
    hp_box_w = 72
    hp_box_h = hud_h - 6
    if hp_box_h < 8:
        hp_box_h = 8
    out_drawables.append((hp_box_x, hp_box_y, hp_box_w, hp_box_h, 0x4208))
    out_rects["hp_box"] = (hp_box_x, hp_box_y, hp_box_w, hp_box_h)

    inner_pad = 2
    hp_fill_x = hp_box_x + inner_pad
    hp_fill_y = hp_box_y + inner_pad
    hp_fill_h = hp_box_h - (inner_pad * 2)
    hp_fill_w_max = hp_box_w - (inner_pad * 2)
    if hp_fill_h < 2:
        hp_fill_h = 2
    if hp_fill_w_max < 2:
        hp_fill_w_max = 2
    hp_ratio_w = (hp_fill_w_max * int(snapshot["hp"])) // int(snapshot["max_hp"])
    hp_ratio_w = _clamp(hp_ratio_w, 0, hp_fill_w_max)
    if hp_ratio_w > 0:
        out_drawables.append((hp_fill_x, hp_fill_y, hp_ratio_w, hp_fill_h, 0x07E0))
    out_rects["hp_fill"] = (hp_fill_x, hp_fill_y, hp_ratio_w, hp_fill_h)

    # X/B skill hint blocks (center)
    hint_w = 14
    hint_h = hp_box_h
    x_hint_x = 92
    b_hint_x = x_hint_x + hint_w + 6
    hint_y = hp_box_y
    out_drawables.append((x_hint_x, hint_y, hint_w, hint_h, 0x061F))
    out_drawables.append((b_hint_x, hint_y, hint_w, hint_h, 0xFD20))
    out_rects["hint_x"] = (x_hint_x, hint_y, hint_w, hint_h)
    out_rects["hint_b"] = (b_hint_x, hint_y, hint_w, hint_h)

    # Save status block
    save_x = 126
    save_y = hp_box_y
    save_w = 22
    save_h = hp_box_h
    save_status = snapshot["save_status"]
    if save_status == SAVE_STATUS_OK:
        save_color = 0x07E0
    elif save_status == SAVE_STATUS_FAIL:
        save_color = 0xF800
    else:
        save_color = 0x39E7
    out_drawables.append((save_x, save_y, save_w, save_h, save_color))
    out_rects["save_status"] = (save_x, save_y, save_w, save_h)

    # Debug ON/OFF block
    dbg_x = 152
    dbg_y = hp_box_y
    dbg_w = 22
    dbg_h = hp_box_h
    dbg_color = 0x07E0 if snapshot["debug_enabled"] else 0x7BEF
    out_drawables.append((dbg_x, dbg_y, dbg_w, dbg_h, dbg_color))
    out_rects["debug_status"] = (dbg_x, dbg_y, dbg_w, dbg_h)

    # Keep right side masked so stale pixels are never visible.
    mask_x = 178
    mask_w = hud_w - mask_x
    if mask_w > 0:
        out_drawables.append((mask_x, hud_y, mask_w, hud_h, int(config.COLOR_UI_BG)))
        out_rects["hud_mask"] = (mask_x, hud_y, mask_w, hud_h)
