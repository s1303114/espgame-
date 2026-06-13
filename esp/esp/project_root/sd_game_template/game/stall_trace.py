try:
    from time import ticks_diff
except Exception:
    def ticks_diff(a, b):
        return a - b

_ENABLED = False
_SIZE = 0
_SLOTS = None
_POS = 0
_CUR = -1
_LEN = 76


def configure(enabled, size=32):
    global _ENABLED, _SIZE, _SLOTS, _POS, _CUR
    if not enabled:
        _ENABLED = False
        return 0
    try:
        size = int(size)
    except Exception:
        size = 32
    if size < 8:
        size = 8
    if size > 64:
        size = 64
    if _SLOTS is None or _SIZE != size:
        _SLOTS = []
        i = 0
        while i < size:
            row = [0] * _LEN
            row[0] = -1
            _SLOTS.append(row)
            i += 1
        _SIZE = size
    else:
        i = 0
        while i < _SIZE:
            _SLOTS[i][0] = -1
            i += 1
    _POS = 0
    _CUR = -1
    _ENABLED = True
    return size


def enabled():
    return _ENABLED


def start(frame, t0):
    global _POS, _CUR
    if not _ENABLED:
        return
    row = _SLOTS[_POS]
    i = 0
    while i < _LEN:
        row[i] = 0
        i += 1
    row[0] = int(frame)
    row[1] = t0
    _CUR = _POS
    _POS += 1
    if _POS >= _SIZE:
        _POS = 0


def _row():
    if (not _ENABLED) or _CUR < 0:
        return None
    return _SLOTS[_CUR]


def mark_update(t, update_us):
    row = _row()
    if row is None:
        return
    row[2] = ticks_diff(t, row[1])
    row[10] = int(update_us)


def mark_update_part(idx, t, part_us):
    row = _row()
    if row is None:
        return
    try:
        idx = int(idx)
    except Exception:
        return
    if idx < 0 or idx >= 8:
        return
    row[34 + idx] = int(part_us)
    row[42 + idx] = ticks_diff(t, row[1])


def mark_desc_part(idx, t, part_us):
    row = _row()
    if row is None:
        return
    try:
        idx = int(idx)
    except Exception:
        return
    if idx < 0 or idx >= 9:
        return
    row[50 + idx] = int(part_us)
    row[59 + idx] = ticks_diff(t, row[1])


def mark_desc_call_start(idx, t):
    row = _row()
    if row is None:
        return
    try:
        idx = int(idx)
    except Exception:
        return
    if idx == 0:
        row[70] = ticks_diff(t, row[1])
    elif idx == 4:
        row[72] = ticks_diff(t, row[1])
    elif idx == 6:
        row[74] = ticks_diff(t, row[1])


def mark_desc_helper_enter(idx, t):
    row = _row()
    if row is None:
        return
    try:
        idx = int(idx)
    except Exception:
        return
    if idx == 0:
        row[71] = ticks_diff(t, row[1])
    elif idx == 4:
        row[73] = ticks_diff(t, row[1])
    elif idx == 6:
        row[75] = ticks_diff(t, row[1])


def mark_tail(t, tail_total_us, tail_res_us, tail_dma_us):
    row = _row()
    if row is None:
        return
    row[3] = ticks_diff(t, row[1])
    row[11] = int(tail_total_us)
    row[12] = int(tail_res_us)
    row[13] = int(tail_dma_us)


def mark_submit_start(t):
    row = _row()
    if row is None:
        return
    row[4] = ticks_diff(t, row[1])


def mark_submit_call_start(t):
    row = _row()
    if row is None:
        return
    row[68] = ticks_diff(t, row[1])


def mark_submit_helper_enter(t):
    row = _row()
    if row is None:
        return
    row[69] = ticks_diff(t, row[1])


def mark_submit_end(t, submit_us, desc_us, compose_us, wait_dma_us, dma_us):
    row = _row()
    if row is None:
        return
    row[5] = ticks_diff(t, row[1])
    row[14] = int(submit_us)
    row[15] = row[5] - row[4]
    row[16] = row[15] - row[14]
    row[17] = int(desc_us)
    row[18] = int(compose_us)
    row[19] = int(wait_dma_us)
    row[20] = int(dma_us)


def mark_submit_native_done(t):
    row = _row()
    if row is None:
        return
    row[26] = ticks_diff(t, row[1])


def mark_submit_unpacked(t):
    row = _row()
    if row is None:
        return
    row[27] = ticks_diff(t, row[1])


def mark_submit_log_before(t):
    row = _row()
    if row is None:
        return
    row[28] = ticks_diff(t, row[1])


def mark_submit_log_done(t):
    row = _row()
    if row is None:
        return
    row[29] = ticks_diff(t, row[1])


def mark_submit_pre_return(t):
    row = _row()
    if row is None:
        return
    row[30] = ticks_diff(t, row[1])


def mark_hud(t, hud_us):
    row = _row()
    if row is None:
        return
    row[6] = ticks_diff(t, row[1])
    row[21] = int(hud_us)


def mark_debug(t):
    row = _row()
    if row is None:
        return
    row[7] = ticks_diff(t, row[1])


def mark_profile(t):
    row = _row()
    if row is None:
        return
    row[8] = ticks_diff(t, row[1])


def finish(t, total_us, camera_x, player_x, enemies, orbs):
    row = _row()
    if row is None:
        return
    row[9] = int(total_us)
    row[22] = int(camera_x)
    row[23] = int(player_x)
    row[24] = int(enemies)
    row[25] = int(orbs)


def dump(frame, total_us):
    if not _ENABLED:
        return
    print("STALL_TRACE_BEGIN frame=%d total_us=%d size=%d" % (int(frame), int(total_us), int(_SIZE)))
    n = 0
    while n < _SIZE:
        idx = _POS + n
        if idx >= _SIZE:
            idx -= _SIZE
        row = _SLOTS[idx]
        if row[0] >= 0:
            print(
                "STALL_TRACE f=%d end=%d upd_end=%d tail_end=%d sub0=%d call0=%d call1=%d native_done=%d unpack_done=%d log0=%d log1=%d pre_ret=%d sub1=%d hud_end=%d dbg_end=%d prof_end=%d upd=%d tail_total=%d tail_res=%d tail_dma=%d sub_wall=%d sub_us=%d sub_extra=%d call_enter_us=%d helper_gap_us=%d post_native=%d post_unpack=%d log_us=%d return_extra=%d desc=%d comp=%d wait_dma=%d dma=%d hud=%d cam=%d px=%d enemies=%d orbs=%d up0=%d up1=%d up2=%d up3=%d up4=%d up5=%d up6=%d up7=%d up0e=%d up1e=%d up2e=%d up3e=%d up4e=%d up5e=%d up6e=%d up7e=%d d0=%d d1=%d d2=%d d3=%d d4=%d d5=%d d6=%d d7=%d d8=%d d0e=%d d1e=%d d2e=%d d3e=%d d4e=%d d5e=%d d6e=%d d7e=%d d8e=%d d0_call_enter_us=%d d0_body_us=%d d4_call_enter_us=%d d4_body_us=%d d6_call_enter_us=%d d6_body_us=%d"
                % (
                    row[0],
                    row[9],
                    row[2],
                    row[3],
                    row[4],
                    row[68],
                    row[69],
                    row[26],
                    row[27],
                    row[28],
                    row[29],
                    row[30],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[10],
                    row[11],
                    row[12],
                    row[13],
                    row[15],
                    row[14],
                    row[16],
                    row[69] - row[68] if row[69] and row[68] else 0,
                    row[26] - row[69] if row[26] and row[69] else 0,
                    row[27] - row[26] if row[27] and row[26] else 0,
                    row[30] - row[27] if row[30] and row[27] else 0,
                    row[29] - row[28] if row[29] and row[28] else 0,
                    row[5] - row[30] if row[5] and row[30] else 0,
                    row[17],
                    row[18],
                    row[19],
                    row[20],
                    row[21],
                    row[22],
                    row[23],
                    row[24],
                    row[25],
                    row[34],
                    row[35],
                    row[36],
                    row[37],
                    row[38],
                    row[39],
                    row[40],
                    row[41],
                    row[42],
                    row[43],
                    row[44],
                    row[45],
                    row[46],
                    row[47],
                    row[48],
                    row[49],
                    row[50],
                    row[51],
                    row[52],
                    row[53],
                    row[54],
                    row[55],
                    row[56],
                    row[57],
                    row[58],
                    row[59],
                    row[60],
                    row[61],
                    row[62],
                    row[63],
                    row[64],
                    row[65],
                    row[66],
                    row[67],
                    row[71] - row[70] if row[71] and row[70] else 0,
                    row[59] - row[71] if row[59] and row[71] else 0,
                    row[73] - row[72] if row[73] and row[72] else 0,
                    row[63] - row[73] if row[63] and row[73] else 0,
                    row[75] - row[74] if row[75] and row[74] else 0,
                    row[65] - row[75] if row[65] and row[75] else 0,
                )
            )
        n += 1
    print("STALL_TRACE_END")
