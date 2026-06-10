def _read_i16(buf, off):
    val = buf[off] | (buf[off + 1] << 8)
    if val & 0x8000:
        val -= 0x10000
    return val


def _append_i16(buf, value):
    iv = int(value)
    if iv < 0:
        iv += 0x10000
    buf.append(iv & 0xFF)
    buf.append((iv >> 8) & 0xFF)


def pack_descriptors(
    monk_attack_buf,
    monk_attack_stride,
    monk_attack_count,
    camera_x,
    view_w,
    view_h,
    attack_stride_min,
    orb_w,
    orb_h,
    final_phase_lock,
    special_kind_path,
    max_count,
    chunk_px,
    thickness,
    rush_steps,
):
    out = bytearray()
    stride = 8
    count = 0
    if monk_attack_buf is None or int(monk_attack_stride) < int(attack_stride_min) or int(monk_attack_count) <= 0:
        return out, stride, count
    left = int(camera_x)
    top = 0
    right = left + int(view_w) - int(orb_w)
    bottom = int(view_h) - int(orb_h)
    if right < left:
        right = left
    if bottom < top:
        bottom = top
    ei = 0
    while ei < int(monk_attack_count):
        base = ei * int(monk_attack_stride)
        if base < 0 or (base + int(attack_stride_min)) > len(monk_attack_buf):
            ei += 1
            continue
        if int(monk_attack_buf[base + 0]) != int(final_phase_lock):
            ei += 1
            continue
        x = _read_i16(monk_attack_buf, base + 4)
        y = _read_i16(monk_attack_buf, base + 6)
        vx = _read_i16(monk_attack_buf, base + 8)
        vy = _read_i16(monk_attack_buf, base + 10)
        if vx == 0 and vy == 0:
            ei += 1
            continue
        predicted_steps = 0
        while predicted_steps < int(rush_steps) and count < int(max_count):
            start_x = x
            start_y = y
            steps = 0
            while steps < (int(rush_steps) - predicted_steps):
                nx = x + vx
                ny = y + vy
                bounced = False
                if nx < left:
                    nx = left + (left - nx)
                    vx = -vx
                    bounced = True
                elif nx > right:
                    nx = right - (nx - right)
                    vx = -vx
                    bounced = True
                if ny < top:
                    ny = top + (top - ny)
                    vy = -vy
                    bounced = True
                elif ny > bottom:
                    ny = bottom - (ny - bottom)
                    vy = -vy
                    bounced = True
                x = nx
                y = ny
                steps += 1
                predicted_steps += 1
                if bounced:
                    break
            seg_dx = x - start_x
            seg_dy = y - start_y
            seg_steps = abs(seg_dx)
            if abs(seg_dy) > seg_steps:
                seg_steps = abs(seg_dy)
            if seg_steps > 0:
                drawn = 0
                chunk_start_x = start_x
                chunk_start_y = start_y
                while drawn < seg_steps and count < int(max_count):
                    next_drawn = drawn + int(chunk_px)
                    if next_drawn > seg_steps:
                        next_drawn = seg_steps
                    chunk_end_x = start_x + (seg_dx * next_drawn) // seg_steps
                    chunk_end_y = start_y + (seg_dy * next_drawn) // seg_steps
                    dx = chunk_end_x - chunk_start_x
                    dy = chunk_end_y - chunk_start_y
                    if dx < -128:
                        dx = -128
                    if dx > 127:
                        dx = 127
                    if dy < -128:
                        dy = -128
                    if dy > 127:
                        dy = 127
                    _append_i16(out, chunk_start_x)
                    _append_i16(out, chunk_start_y)
                    out.append(int(special_kind_path) & 0xFF)
                    out.append(dx & 0xFF)
                    out.append(dy & 0xFF)
                    out.append(int(thickness) & 0xFF)
                    count += 1
                    chunk_start_x = chunk_end_x
                    chunk_start_y = chunk_end_y
                    drawn = next_drawn
        ei += 1
    return out, stride, count
