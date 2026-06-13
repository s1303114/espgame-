import config


def _buf_set_u16_le(buf, off, value):
    uv = int(value) & 0xFFFF
    buf[off] = uv & 0xFF
    buf[off + 1] = (uv >> 8) & 0xFF


def _swap16(v):
    return ((v & 0xFF) << 8) | ((v >> 8) & 0xFF)


def _is_special_render_object(meta):
    return bool(meta and meta.get("special_render"))


def _special_kind_from_anim_id(anim_id):
    aid = str(anim_id or "")
    if aid == "respawn_stone":
        return 0
    if aid == "resurrection_anchor":
        return 1
    return -1


def _new_special_object_specs(objects_meta, object_animations):
    if not objects_meta:
        return bytearray()
    out = bytearray(len(objects_meta) * 6)
    i = 0
    while i < len(objects_meta):
        meta = objects_meta[i]
        kind = -1
        frame_count = 0
        frame_hold = 4
        loop_flag = 1
        if _is_special_render_object(meta) and object_animations:
            anim_id = meta.get("anim_id", "") if meta else ""
            kind = _special_kind_from_anim_id(anim_id)
            anim_spec = object_animations.get(anim_id)
            if anim_spec:
                frame_count = int(anim_spec.get("frame_count", len(anim_spec.get("frames") or [])) or 0)
                frame_hold = int(anim_spec.get("frame_hold", 4) or 4)
                if frame_hold < 1:
                    frame_hold = 1
                loop_flag = 1 if bool(anim_spec.get("loop", True)) else 0
        base = i * 6
        out[base] = kind & 0xFF
        out[base + 1] = frame_count & 0xFF
        _buf_set_u16_le(out, base + 2, frame_hold)
        out[base + 4] = loop_flag & 0xFF
        out[base + 5] = 0
        i += 1
    return out


def _new_native_submit_scratch(objects_c_count, enemy_rows_c_count, monk_orb_c_count, enemy_max_bullets):
    object_count = int(objects_c_count)
    enemy_count = int(enemy_rows_c_count)
    orb_count = int(monk_orb_c_count)
    bullet_count = int(enemy_max_bullets)
    if object_count < 1:
        object_count = 1
    if enemy_count < 1:
        enemy_count = 1
    if orb_count < 1:
        orb_count = 1
    if bullet_count < 1:
        bullet_count = 1
    special_cap = object_count + orb_count + 2
    enemy_cap = enemy_count + 2
    return (
        bytearray(special_cap * 8),
        special_cap,
        bytearray(enemy_cap * 10),
        enemy_cap,
        bytearray(bullet_count * 10),
        bullet_count,
    )


def extend_ctx(ctx, objects_ctx, enemy_rt):
    native_scratch = _new_native_submit_scratch(
        objects_ctx[5],
        enemy_rt["enemy_rows_c_count"],
        enemy_rt["monk_orb_c_count"],
        enemy_rt["enemy_max_bullets"],
    )
    ctx.extend((
        objects_ctx[9],
        objects_ctx[10],
        objects_ctx[11],
        _new_special_object_specs(objects_ctx[1], objects_ctx[2]),
        native_scratch[0],
        native_scratch[1],
        native_scratch[2],
        native_scratch[3],
        native_scratch[4],
        native_scratch[5],
        _swap16(int(getattr(config, "CAMERA_PLAYER_COLORKEY_RGB565", 0xF81F)) & 0xFFFF),
        _swap16(0xF81F),
        _swap16(int(getattr(config, "CAMERA_OBJECT_COLORKEY_RGB565", 0xF81F)) & 0xFFFF) if bool(getattr(config, "CAMERA_OBJECT_COLORKEY_ENABLE", True)) else -1,
        enemy_rt["enemy_states"]._buf,
        enemy_rt["enemy_bullets"]._buf,
    ))
    return ctx
