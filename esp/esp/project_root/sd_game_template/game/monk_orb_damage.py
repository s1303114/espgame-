_prev_buf = None
_skip_once = False


def ignore_next():
    global _skip_once
    _skip_once = True


def _read_i16(buf, off):
    val = buf[off] | (buf[off + 1] << 8)
    if val & 0x8000:
        val -= 0x10000
    return val


def _aabb_hits_player(ox, oy, player_x, player_y, player_w, player_h):
    return player_x < (ox + 16) and (player_x + player_w) > ox and player_y < (oy + 16) and (player_y + player_h) > oy


def _swept_aabb_hits_player(prev_x, prev_y, ox, oy, player_x, player_y, player_w, player_h):
    left = prev_x if prev_x < ox else ox
    top = prev_y if prev_y < oy else oy
    right = (prev_x + 16) if prev_x > ox else (ox + 16)
    bottom = (prev_y + 16) if prev_y > oy else (oy + 16)
    return player_x < right and (player_x + player_w) > left and player_y < bottom and (player_y + player_h) > top


def action_hit_player(buf, stride, count, player_x, player_y, player_w, player_h):
    global _prev_buf, _skip_once
    if _skip_once:
        kill = None
        _skip_once = False
    else:
        kill = action_hit_player_swept(buf, stride, count, player_x, player_y, player_w, player_h, _prev_buf)
    if buf is not None and int(stride) >= 16:
        if _prev_buf is None or len(_prev_buf) != len(buf):
            _prev_buf = bytearray(buf)
        else:
            _prev_buf[:] = buf
    return kill


def action_hit_player_swept(buf, stride, count, player_x, player_y, player_w, player_h, prev_buf=None):
    if buf is None or int(stride) < 16:
        return None
    stride = int(stride)
    count = int(count)
    limit = len(buf) // stride if stride > 0 else 0
    if count > limit:
        count = limit
    px = int(player_x)
    py = int(player_y)
    pw = int(player_w)
    ph = int(player_h)
    i = 0
    while i < count:
        base = i * stride
        if (base + 16) <= len(buf):
            mode = int(buf[base])
            if mode == 2 or mode == 4 or mode == 5:
                ox = _read_i16(buf, base + 10)
                oy = _read_i16(buf, base + 12)
                if _aabb_hits_player(ox, oy, px, py, pw, ph):
                    return i, mode, ox, oy
                if prev_buf is not None and (base + 16) <= len(prev_buf) and int(prev_buf[base]) == mode:
                    prev_x = _read_i16(prev_buf, base + 10)
                    prev_y = _read_i16(prev_buf, base + 12)
                    if _swept_aabb_hits_player(prev_x, prev_y, ox, oy, px, py, pw, ph):
                        return i, mode, ox, oy
        i += 1
    return None


def check_and_store(buf, stride, count, player_x, player_y, player_w, player_h, prev_buf=None):
    kill = action_hit_player_swept(buf, stride, count, player_x, player_y, player_w, player_h, prev_buf)
    if buf is None or int(stride) < 16:
        return kill, prev_buf
    if prev_buf is None or len(prev_buf) != len(buf):
        prev_buf = bytearray(buf)
    else:
        prev_buf[:] = buf
    return kill, prev_buf
