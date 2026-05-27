#include <stdint.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_cache.h"

// Keep qstr extraction lightweight: when NO_QSTR is set, avoid preprocessing
// the heavy LovyanGFX-backed implementation body.
#if !defined(NO_QSTR)
extern "C" {
#include "py/obj.h"
#include "py/objmodule.h"
#include "py/runtime.h"
#include "py/stream.h"
#include "extmod/vfs.h"
}

#if !defined(NO_QSTR)
#include "lgfx_config.hpp"
#include "lgfx_shared.hpp"
LGFX lcd;

static uint8_t *read_file_bytes(const char *path, size_t *out_len) {
    mp_obj_t args[2] = {
        mp_obj_new_str(path, strlen(path)),
        MP_OBJ_NEW_QSTR(MP_QSTR_rb),
    };
    mp_obj_t file = mp_vfs_open(MP_ARRAY_SIZE(args), &args[0], (mp_map_t *)&mp_const_empty_map);

    size_t cap = 4096;
    size_t len = 0;
    uint8_t *buf = (uint8_t *)malloc(cap);
    if (buf == nullptr) {
        mp_stream_close(file);
        errno = ENOMEM;
        return nullptr;
    }

    int errcode = 0;
    uint8_t tmp[512];
    while (true) {
        mp_uint_t n = mp_stream_rw(file, tmp, sizeof(tmp), &errcode, MP_STREAM_RW_READ | MP_STREAM_RW_ONCE);
        if (errcode != 0) {
            free(buf);
            mp_stream_close(file);
            errno = errcode;
            return nullptr;
        }
        if (n == 0) {
            break;
        }

        if (len + (size_t)n > cap) {
            size_t new_cap = cap;
            while (new_cap < len + (size_t)n) {
                if (new_cap > (SIZE_MAX / 2)) {
                    free(buf);
                    mp_stream_close(file);
                    errno = EFBIG;
                    return nullptr;
                }
                new_cap *= 2;
            }
            uint8_t *new_buf = (uint8_t *)realloc(buf, new_cap);
            if (new_buf == nullptr) {
                free(buf);
                mp_stream_close(file);
                errno = ENOMEM;
                return nullptr;
            }
            buf = new_buf;
            cap = new_cap;
        }

        memcpy(buf + len, tmp, (size_t)n);
        len += (size_t)n;
    }

    mp_stream_close(file);
    *out_len = len;
    return buf;
}

static bool draw_png_from_path(
    lgfx::v1::LGFX_Sprite *sprite,
    const char *path,
    int32_t sx,
    int32_t sy,
    int32_t w,
    int32_t h
) {
    size_t png_len = 0;
    uint8_t *png_data = read_file_bytes(path, &png_len);
    if (png_data == nullptr && png_len == 0) {
        return false;
    }

    bool ok = sprite->drawPng(
        png_data,
        (uint32_t)png_len,
        0,
        0,
        w,
        h,
        sx,
        sy,
        1.0f,
        1.0f,
        (lgfx::v1::datum_t)0
    );

    free(png_data);
    return ok;
}

static bool decode_png_rect_to_rgb565_row_major(
    const char *path,
    int32_t sx,
    int32_t sy,
    int32_t w,
    int32_t h,
    uint16_t *out_pixels,
    uint16_t preset_color,
    uint32_t *preset_after_count
) {
    if (w <= 0 || h <= 0 || out_pixels == nullptr) {
        errno = EINVAL;
        return false;
    }

    size_t pix_count = (size_t)w * (size_t)h;
    for (size_t i = 0; i < pix_count; ++i) {
        out_pixels[i] = preset_color;
    }

    lgfx::v1::LGFX_Sprite sprite(&lcd);
    sprite.setColorDepth(16);
    if (!sprite.createSprite(w, h)) {
        errno = ENOMEM;
        return false;
    }
    sprite.fillScreen(preset_color);

    bool ok = draw_png_from_path(&sprite, path, sx, sy, w, h);
    if (!ok) {
        if (errno == 0) {
            errno = EIO;
        }
        sprite.deleteSprite();
        return false;
    }

    const uint8_t *src = (const uint8_t *)sprite.getBuffer();
    size_t buf_len = sprite.bufferLength();
    size_t row_bytes = (size_t)w * 2u;
    size_t min_len = (size_t)h * row_bytes;
    if (src == nullptr || buf_len < min_len) {
        errno = EIO;
        sprite.deleteSprite();
        return false;
    }
    size_t stride_bytes = buf_len / (size_t)h;
    if (stride_bytes < row_bytes) {
        errno = EIO;
        sprite.deleteSprite();
        return false;
    }

    uint8_t *dst = (uint8_t *)out_pixels;
    for (int32_t y = 0; y < h; ++y) {
        memcpy(dst + ((size_t)y * row_bytes), src + ((size_t)y * stride_bytes), row_bytes);
    }

    if (preset_after_count != nullptr) {
        uint32_t count = 0;
        for (size_t i = 0; i < pix_count; ++i) {
            if (out_pixels[i] == preset_color) {
                ++count;
            }
        }
        *preset_after_count = count;
    }

    sprite.deleteSprite();
    return true;
}
#endif

extern "C" {

static mp_obj_t lgfx_init(void) {
    lcd.init();
    lcd.setRotation(1);
    lcd.setBrightness(255);
    lcd.fillScreen(0x0000);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(lgfx_init_obj, lgfx_init);

static mp_obj_t lgfx_fill(mp_obj_t color_in) {
    mp_int_t color = mp_obj_get_int(color_in);
    lcd.fillScreen((uint16_t)color);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(lgfx_fill_obj, lgfx_fill);

static mp_obj_t lgfx_rotation(mp_obj_t rot_in) {
    mp_int_t rot = mp_obj_get_int(rot_in);
    lcd.setRotation((uint_fast8_t)rot);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(lgfx_rotation_obj, lgfx_rotation);

static mp_obj_t lgfx_fill_rect(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);
    mp_int_t color = mp_obj_get_int(args[4]);
    lcd.fillRect((int32_t)x, (int32_t)y, (int32_t)w, (int32_t)h, (uint16_t)color);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_fill_rect_obj, 5, 5, lgfx_fill_rect);

static mp_obj_t lgfx_blit_rect565(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[4], &bufinfo, MP_BUFFER_READ);

    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    // API contract: Python buffer is little-endian RGB565 byte layout.
    // For this panel path, pushImage must run with swapBytes=true to send proper byte order.
    bool prev_swap = lcd.getSwapBytes();
    lcd.setSwapBytes(true);

    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;
    lcd.pushImage((int32_t)x, (int32_t)y, (int32_t)w, (int32_t)h, pixels);

    lcd.setSwapBytes(prev_swap);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_obj, 5, 5, lgfx_blit_rect565);

static mp_obj_t lgfx_blit_rect565_rows(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[4], &bufinfo, MP_BUFFER_READ);

    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    // Display transfer safety policy (current known-good baseline):
    // - Large-frame path must use row-compatible transfer only.
    // - pushImage(..., h=1) per row + waitDMA() per row is stable.
    // - Do not replace this with h>1 bulk for mainline rendering.
    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;
    bool prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(true);
    for (mp_int_t row = 0; row < h; ++row) {
        const uint16_t *row_ptr = pixels + ((size_t)row * (size_t)w);
        lcd.pushImage((int32_t)x, (int32_t)(y + row), (int32_t)w, 1, row_ptr);
        lcd.waitDMA();
    }
    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_rows_obj, 5, 5, lgfx_blit_rect565_rows);

static mp_obj_t lgfx_blit_rect565_wait(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[4], &bufinfo, MP_BUFFER_READ);

    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    // Experimental path:
    // - Uses pushImage(..., h>1) in one shot.
    // - Kept for diagnostics/experiments only, not for mainline large-frame rendering.
    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;
    bool prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(true);
    lcd.pushImage((int32_t)x, (int32_t)y, (int32_t)w, (int32_t)h, pixels);
    // Safety contract: return only after transfer is complete,
    // so caller can safely reuse the same source buffer.
    lcd.waitDMA();
    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_wait_obj, 5, 5, lgfx_blit_rect565_wait);


static mp_obj_t lgfx_blit_rect565_wire_wait(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[4], &bufinfo, MP_BUFFER_READ);

    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;
    bool prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(false);
    lcd.pushImage((int32_t)x, (int32_t)y, (int32_t)w, (int32_t)h, pixels);
    lcd.waitDMA();
    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_wire_wait_obj, 5, 5, lgfx_blit_rect565_wire_wait);

static bool lgfx_async_inflight = false;
static bool lgfx_async_prev_swap = false;

static mp_obj_t lgfx_blit_rect565_async(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }
    if (lgfx_async_inflight) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("async busy"));
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[4], &bufinfo, MP_BUFFER_READ);
    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;
    lgfx_async_prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(true);
    lcd.pushImageDMA((int32_t)x, (int32_t)y, (int32_t)w, (int32_t)h, pixels);
    lgfx_async_inflight = true;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_async_obj, 5, 5, lgfx_blit_rect565_async);


static mp_obj_t lgfx_blit_rect565_wire_async(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }
    if (lgfx_async_inflight) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("async busy"));
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[4], &bufinfo, MP_BUFFER_READ);
    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;
    esp_err_t sync_ret = esp_cache_msync(
        (void *)pixels,
        expected_len,
        ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED
    );
    if (sync_ret != ESP_OK) {
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("cache msync failed: %d"), (int)sync_ret);
    }
    lgfx_async_prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(false);
    lcd.pushImageDMA((int32_t)x, (int32_t)y, (int32_t)w, (int32_t)h, pixels);
    lgfx_async_inflight = true;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_wire_async_obj, 5, 5, lgfx_blit_rect565_wire_async);

static mp_obj_t lgfx_blit_wait_done(void) {
    if (!lgfx_async_inflight) {
        return mp_const_none;
    }
    lcd.waitDMA();
    lcd.setSwapBytes(lgfx_async_prev_swap);
    lcd.endWrite();
    lgfx_async_inflight = false;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(lgfx_blit_wait_done_obj, lgfx_blit_wait_done);


static mp_obj_t lgfx_async_probe_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 4) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 4 args"));
    }
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[0], &bufinfo, MP_BUFFER_READ);
    mp_int_t w = mp_obj_get_int(args[1]);
    mp_int_t h = mp_obj_get_int(args[2]);
    mp_int_t small_h = mp_obj_get_int(args[3]);

    if (w <= 0 || h <= 0 || small_h <= 0 || small_h > h) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }

    size_t full_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf too small"));
    }

    const uint16_t *full_pixels = (const uint16_t *)bufinfo.buf;
    const uint16_t *small_pixels = (const uint16_t *)bufinfo.buf;

    // Ensure clean async state.
    if (lgfx_async_inflight) {
        lcd.waitDMA();
        lcd.setSwapBytes(lgfx_async_prev_swap);
        lcd.endWrite();
        lgfx_async_inflight = false;
    }

    uint32_t t_full_kick = 0, t_full_wait = 0;
    uint32_t t_small_kick = 0, t_small_wait = 0;
    uint32_t t_full_1 = 0, t_full_2 = 0;
    uint32_t t_small_1 = 0, t_small_2 = 0;

    // Case 1: first full-screen async call (kick + wait split)
    {
        int64_t t0 = esp_timer_get_time();
        lgfx_async_prev_swap = lcd.getSwapBytes();
        lcd.startWrite();
        lcd.setSwapBytes(true);
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)h, full_pixels);
        lgfx_async_inflight = true;
        int64_t t1 = esp_timer_get_time();

        lcd.waitDMA();
        lcd.setSwapBytes(lgfx_async_prev_swap);
        lcd.endWrite();
        lgfx_async_inflight = false;
        int64_t t2 = esp_timer_get_time();

        t_full_kick = (uint32_t)(t1 - t0);
        t_full_wait = (uint32_t)(t2 - t1);
    }

    // Case 2: full-screen back-to-back calls in one write session.
    {
        bool prev_swap = lcd.getSwapBytes();
        lcd.startWrite();
        lcd.setSwapBytes(true);

        int64_t t0 = esp_timer_get_time();
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)h, full_pixels);
        int64_t t1 = esp_timer_get_time();
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)h, full_pixels);
        int64_t t2 = esp_timer_get_time();

        lcd.waitDMA();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();

        t_full_1 = (uint32_t)(t1 - t0);
        t_full_2 = (uint32_t)(t2 - t1);
    }

    // Case 3: small-rect async call (kick + wait split)
    {
        int64_t t0 = esp_timer_get_time();
        lgfx_async_prev_swap = lcd.getSwapBytes();
        lcd.startWrite();
        lcd.setSwapBytes(true);
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)small_h, small_pixels);
        lgfx_async_inflight = true;
        int64_t t1 = esp_timer_get_time();

        lcd.waitDMA();
        lcd.setSwapBytes(lgfx_async_prev_swap);
        lcd.endWrite();
        lgfx_async_inflight = false;
        int64_t t2 = esp_timer_get_time();

        t_small_kick = (uint32_t)(t1 - t0);
        t_small_wait = (uint32_t)(t2 - t1);
    }

    // Case 4: small-rect back-to-back calls in one write session.
    {
        bool prev_swap = lcd.getSwapBytes();
        lcd.startWrite();
        lcd.setSwapBytes(true);

        int64_t t0 = esp_timer_get_time();
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)small_h, small_pixels);
        int64_t t1 = esp_timer_get_time();
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)small_h, small_pixels);
        int64_t t2 = esp_timer_get_time();

        lcd.waitDMA();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();

        t_small_1 = (uint32_t)(t1 - t0);
        t_small_2 = (uint32_t)(t2 - t1);
    }

    mp_printf(&mp_plat_print, "ASYNC_PROBE full_kick_us=%u full_wait_us=%u\n", t_full_kick, t_full_wait);
    mp_printf(&mp_plat_print, "ASYNC_PROBE full_b2b_us first=%u second=%u\n", t_full_1, t_full_2);
    mp_printf(&mp_plat_print, "ASYNC_PROBE small_h=%d small_kick_us=%u small_wait_us=%u\n", (int)small_h, t_small_kick, t_small_wait);
    mp_printf(&mp_plat_print, "ASYNC_PROBE small_b2b_us first=%u second=%u\n", t_small_1, t_small_2);

    mp_obj_t out[8] = {
        mp_obj_new_int_from_uint(t_full_kick),
        mp_obj_new_int_from_uint(t_full_wait),
        mp_obj_new_int_from_uint(t_full_1),
        mp_obj_new_int_from_uint(t_full_2),
        mp_obj_new_int_from_uint(t_small_kick),
        mp_obj_new_int_from_uint(t_small_wait),
        mp_obj_new_int_from_uint(t_small_1),
        mp_obj_new_int_from_uint(t_small_2),
    };
    return mp_obj_new_tuple(8, out);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_async_probe_rgb565_obj, 4, 4, lgfx_async_probe_rgb565);

static mp_obj_t lgfx_submit_probe_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 3) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 3 args"));
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[0], &bufinfo, MP_BUFFER_READ);
    mp_int_t w = mp_obj_get_int(args[1]);
    mp_int_t h = mp_obj_get_int(args[2]);
    if (w <= 0 || h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }

    size_t full_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf too small"));
    }

    const uint16_t *pixels = (const uint16_t *)bufinfo.buf;

    if (lgfx_async_inflight) {
        lcd.waitDMA();
        lcd.setSwapBytes(lgfx_async_prev_swap);
        lcd.endWrite();
        lgfx_async_inflight = false;
    }

    uint32_t t_swap_sync = 0;
    uint32_t t_swap_dma_kick = 0;
    uint32_t t_swap_dma_wait = 0;
    uint32_t t_noswap_sync = 0;
    uint32_t t_noswap_dma_kick = 0;
    uint32_t t_noswap_dma_wait = 0;

    {
        bool prev_swap = lcd.getSwapBytes();
        int64_t t0 = esp_timer_get_time();
        lcd.startWrite();
        lcd.setSwapBytes(true);
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)h, pixels);
        lcd.waitDMA();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();
        int64_t t1 = esp_timer_get_time();
        t_swap_sync = (uint32_t)(t1 - t0);
    }

    {
        bool prev_swap = lcd.getSwapBytes();
        lcd.startWrite();
        lcd.setSwapBytes(true);
        int64_t t0 = esp_timer_get_time();
        lcd.pushImageDMA(0, 0, (int32_t)w, (int32_t)h, pixels);
        int64_t t1 = esp_timer_get_time();
        lcd.waitDMA();
        int64_t t2 = esp_timer_get_time();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();
        t_swap_dma_kick = (uint32_t)(t1 - t0);
        t_swap_dma_wait = (uint32_t)(t2 - t1);
    }

    {
        bool prev_swap = lcd.getSwapBytes();
        int64_t t0 = esp_timer_get_time();
        lcd.startWrite();
        lcd.setSwapBytes(false);
        lcd.pushImage(0, 0, (int32_t)w, (int32_t)h, pixels);
        lcd.waitDMA();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();
        int64_t t1 = esp_timer_get_time();
        t_noswap_sync = (uint32_t)(t1 - t0);
    }

    {
        bool prev_swap = lcd.getSwapBytes();
        lcd.startWrite();
        lcd.setSwapBytes(false);
        int64_t t0 = esp_timer_get_time();
        lcd.pushImageDMA(0, 0, (int32_t)w, (int32_t)h, pixels);
        int64_t t1 = esp_timer_get_time();
        lcd.waitDMA();
        int64_t t2 = esp_timer_get_time();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();
        t_noswap_dma_kick = (uint32_t)(t1 - t0);
        t_noswap_dma_wait = (uint32_t)(t2 - t1);
    }

    mp_printf(&mp_plat_print, "SUBMIT_PROBE_SWAP_SYNC_US=%u\n", t_swap_sync);
    mp_printf(&mp_plat_print, "SUBMIT_PROBE_SWAP_DMA_KICK_US=%u\n", t_swap_dma_kick);
    mp_printf(&mp_plat_print, "SUBMIT_PROBE_SWAP_DMA_WAIT_US=%u\n", t_swap_dma_wait);
    mp_printf(&mp_plat_print, "SUBMIT_PROBE_NOSWAP_SYNC_US=%u\n", t_noswap_sync);
    mp_printf(&mp_plat_print, "SUBMIT_PROBE_NOSWAP_DMA_KICK_US=%u\n", t_noswap_dma_kick);
    mp_printf(&mp_plat_print, "SUBMIT_PROBE_NOSWAP_DMA_WAIT_US=%u\n", t_noswap_dma_wait);

    mp_obj_t out[6] = {
        mp_obj_new_int_from_uint(t_swap_sync),
        mp_obj_new_int_from_uint(t_swap_dma_kick),
        mp_obj_new_int_from_uint(t_swap_dma_wait),
        mp_obj_new_int_from_uint(t_noswap_sync),
        mp_obj_new_int_from_uint(t_noswap_dma_kick),
        mp_obj_new_int_from_uint(t_noswap_dma_wait),
    };
    return mp_obj_new_tuple(6, out);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_submit_probe_rgb565_obj, 3, 3, lgfx_submit_probe_rgb565);


static mp_obj_t lgfx_rgb565_swap_bytes_inplace(mp_obj_t buf_obj) {
    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(buf_obj, &bufinfo, MP_BUFFER_RW);
    if ((bufinfo.len & 1u) != 0u) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len must be even"));
    }

    uint8_t *buf = (uint8_t *)bufinfo.buf;
    for (size_t i = 0; i < bufinfo.len; i += 2u) {
        uint8_t b = buf[i];
        buf[i] = buf[i + 1u];
        buf[i + 1u] = b;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(lgfx_rgb565_swap_bytes_inplace_obj, lgfx_rgb565_swap_bytes_inplace);

static mp_obj_t lgfx_blit_rect565_wait_copy(size_t n_args, const mp_obj_t *args) {
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);
    mp_int_t src_stride = w;
    mp_int_t src_x = 0;
    mp_int_t src_y = 0;
    mp_int_t chunk_h = 0;

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    if (n_args == 6) {
        // Backward-compatible form:
        // blit_rect565_wait_copy(x, y, w, h, src_buf, chunk_h)
        chunk_h = mp_obj_get_int(args[5]);
    } else if (n_args == 9) {
        // Stride-aware form:
        // blit_rect565_wait_copy(x, y, w, h, src_buf, src_stride, src_x, src_y, chunk_h)
        src_stride = mp_obj_get_int(args[5]);
        src_x = mp_obj_get_int(args[6]);
        src_y = mp_obj_get_int(args[7]);
        chunk_h = mp_obj_get_int(args[8]);
    } else {
        mp_raise_ValueError(MP_ERROR_TEXT("need 6 or 9 args"));
    }

    if (chunk_h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("chunk_h must > 0"));
    }
    if (src_stride <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("src_stride must > 0"));
    }
    if (src_x < 0 || src_y < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("src_x/src_y must >= 0"));
    }
    if (src_x + w > src_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("src rect exceeds stride"));
    }

    mp_buffer_info_t src_bufinfo;
    mp_get_buffer_raise(args[4], &src_bufinfo, MP_BUFFER_READ);

    if ((src_bufinfo.len & 1u) != 0u) {
        mp_raise_ValueError(MP_ERROR_TEXT("src len must be rgb565"));
    }

    size_t src_stride_bytes = (size_t)src_stride * 2u;
    size_t row_bytes = (size_t)w * 2u;
    size_t src_base = ((size_t)src_y * (size_t)src_stride + (size_t)src_x) * 2u;
    size_t needed_rows = (size_t)h;
    size_t needed_bytes = 0;
    if (needed_rows > 0) {
        needed_bytes = src_base + ((needed_rows - 1u) * src_stride_bytes) + row_bytes;
    }
    if (needed_bytes > src_bufinfo.len) {
        mp_raise_ValueError(MP_ERROR_TEXT("src buf too small"));
    }

    mp_int_t lines = chunk_h;
    if (lines > h) {
        lines = h;
    }
    size_t chunk_bytes = row_bytes * (size_t)lines;

    uint8_t *dma_chunk = (uint8_t *)heap_caps_malloc(chunk_bytes, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL);
    if (dma_chunk == nullptr) {
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("no dma chunk"));
    }

    // Experimental path:
    // - Source addressing is stride-safe, but transfer still uses pushImage(..., h>1).
    // - Keep for diagnostics only; not approved as mainline large-frame path.
    const uint8_t *src = (const uint8_t *)src_bufinfo.buf;
    bool prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(true);

    mp_int_t row = 0;
    while (row < h) {
        mp_int_t draw_h = lines;
        if (row + draw_h > h) {
            draw_h = h - row;
        }
        size_t copy_bytes = row_bytes * (size_t)draw_h;
        if (copy_bytes > chunk_bytes) {
            heap_caps_free(dma_chunk);
            lcd.setSwapBytes(prev_swap);
            lcd.endWrite();
            mp_raise_ValueError(MP_ERROR_TEXT("chunk bytes mismatch"));
        }

        // Copy row-by-row from source stride to contiguous DMA chunk.
        mp_int_t r = 0;
        while (r < draw_h) {
            size_t src_index = ((size_t)(src_y + row + r) * (size_t)src_stride + (size_t)src_x) * 2u;
            if (src_index + row_bytes > src_bufinfo.len) {
                heap_caps_free(dma_chunk);
                lcd.setSwapBytes(prev_swap);
                lcd.endWrite();
                mp_raise_ValueError(MP_ERROR_TEXT("src oob"));
            }
            memcpy(dma_chunk + ((size_t)r * row_bytes), src + src_index, row_bytes);
            ++r;
        }
        lcd.pushImage((int32_t)x, (int32_t)(y + row), (int32_t)w, (int32_t)draw_h, (const uint16_t *)dma_chunk);
        lcd.waitDMA();
        row += draw_h;
    }

    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();
    heap_caps_free(dma_chunk);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_blit_rect565_wait_copy_obj, 6, 9, lgfx_blit_rect565_wait_copy);

static mp_obj_t lgfx_blit_rect565_wait_copy_compat(size_t n_args, const mp_obj_t *args) {
    if (n_args != 9) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 9 args"));
    }
    mp_int_t x = mp_obj_get_int(args[0]);
    mp_int_t y = mp_obj_get_int(args[1]);
    mp_int_t w = mp_obj_get_int(args[2]);
    mp_int_t h = mp_obj_get_int(args[3]);
    mp_int_t src_stride = mp_obj_get_int(args[5]);
    mp_int_t src_x = mp_obj_get_int(args[6]);
    mp_int_t src_y = mp_obj_get_int(args[7]);
    mp_int_t chunk_h = mp_obj_get_int(args[8]);

    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }
    if (chunk_h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("chunk_h must > 0"));
    }
    if (src_stride <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("src_stride must > 0"));
    }
    if (src_x < 0 || src_y < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("src_x/src_y must >= 0"));
    }
    if (src_x + w > src_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("src rect exceeds stride"));
    }

    mp_buffer_info_t src_bufinfo;
    mp_get_buffer_raise(args[4], &src_bufinfo, MP_BUFFER_READ);
    if ((src_bufinfo.len & 1u) != 0u) {
        mp_raise_ValueError(MP_ERROR_TEXT("src len must be rgb565"));
    }

    size_t src_stride_bytes = (size_t)src_stride * 2u;
    size_t row_bytes = (size_t)w * 2u;
    size_t src_base = ((size_t)src_y * (size_t)src_stride + (size_t)src_x) * 2u;
    size_t needed_rows = (size_t)h;
    size_t needed_bytes = 0;
    if (needed_rows > 0) {
        needed_bytes = src_base + ((needed_rows - 1u) * src_stride_bytes) + row_bytes;
    }
    if (needed_bytes > src_bufinfo.len) {
        mp_raise_ValueError(MP_ERROR_TEXT("src buf too small"));
    }

    // Mainline-safe large-frame model:
    // - Stride-aware source selection.
    // - Row-compatible transfer only: pushImage(..., h=1) + waitDMA() per row.
    const uint8_t *src = (const uint8_t *)src_bufinfo.buf;
    bool prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(true);

    mp_int_t row = 0;
    while (row < h) {
        mp_int_t draw_h = chunk_h;
        if (row + draw_h > h) {
            draw_h = h - row;
        }
        mp_int_t r = 0;
        while (r < draw_h) {
            size_t src_index = ((size_t)(src_y + row + r) * (size_t)src_stride + (size_t)src_x) * 2u;
            if (src_index + row_bytes > src_bufinfo.len) {
                lcd.setSwapBytes(prev_swap);
                lcd.endWrite();
                mp_raise_ValueError(MP_ERROR_TEXT("src oob"));
            }
            const uint16_t *row_ptr = (const uint16_t *)(src + src_index);
            lcd.pushImage((int32_t)x, (int32_t)(y + row + r), (int32_t)w, 1, row_ptr);
            lcd.waitDMA();
            ++r;
        }
        row += draw_h;
    }

    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(
    lgfx_blit_rect565_wait_copy_compat_obj,
    9,
    9,
    lgfx_blit_rect565_wait_copy_compat
);

static mp_obj_t lgfx_compose_masked_rgb565(size_t n_args, const mp_obj_t *args) {
    mp_buffer_info_t dst_bufinfo;
    mp_buffer_info_t sprite_bufinfo;
    mp_buffer_info_t mask_bufinfo;
    mp_get_buffer_raise(args[0], &dst_bufinfo, MP_BUFFER_RW);
    mp_int_t dst_w = mp_obj_get_int(args[1]);
    mp_int_t dst_h = mp_obj_get_int(args[2]);
    mp_int_t dst_x = mp_obj_get_int(args[3]);
    mp_int_t dst_y = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &sprite_bufinfo, MP_BUFFER_READ);
    mp_get_buffer_raise(args[6], &mask_bufinfo, MP_BUFFER_READ);
    mp_int_t sprite_w = mp_obj_get_int(args[7]);
    mp_int_t sprite_h = mp_obj_get_int(args[8]);

    if (dst_w <= 0 || dst_h <= 0 || sprite_w <= 0 || sprite_h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }

    size_t dst_expected_min = (size_t)dst_w * (size_t)dst_h * 2u;
    size_t sprite_expected_min = (size_t)sprite_w * (size_t)sprite_h * 2u;
    size_t mask_row_bytes = ((size_t)sprite_w + 7u) / 8u;
    size_t mask_expected_min = mask_row_bytes * (size_t)sprite_h;
    if (dst_bufinfo.len < dst_expected_min) {
        mp_raise_ValueError(MP_ERROR_TEXT("dst buf too small"));
    }
    if (sprite_bufinfo.len < sprite_expected_min) {
        mp_raise_ValueError(MP_ERROR_TEXT("sprite buf too small"));
    }
    if (mask_bufinfo.len < mask_expected_min) {
        mp_raise_ValueError(MP_ERROR_TEXT("mask buf too small"));
    }

    mp_int_t src_x0 = 0;
    mp_int_t src_y0 = 0;
    mp_int_t draw_x0 = dst_x;
    mp_int_t draw_y0 = dst_y;
    if (draw_x0 < 0) {
        src_x0 = -draw_x0;
        draw_x0 = 0;
    }
    if (draw_y0 < 0) {
        src_y0 = -draw_y0;
        draw_y0 = 0;
    }

    mp_int_t vis_w = sprite_w - src_x0;
    mp_int_t vis_h = sprite_h - src_y0;
    if (vis_w <= 0 || vis_h <= 0) {
        return mp_const_none;
    }
    if (draw_x0 + vis_w > dst_w) {
        vis_w = dst_w - draw_x0;
    }
    if (draw_y0 + vis_h > dst_h) {
        vis_h = dst_h - draw_y0;
    }
    if (vis_w <= 0 || vis_h <= 0) {
        return mp_const_none;
    }

    uint8_t *dst = (uint8_t *)dst_bufinfo.buf;
    const uint8_t *sprite = (const uint8_t *)sprite_bufinfo.buf;
    const uint8_t *mask = (const uint8_t *)mask_bufinfo.buf;
    for (mp_int_t y = 0; y < vis_h; ++y) {
        mp_int_t sy = src_y0 + y;
        mp_int_t dy = draw_y0 + y;
        for (mp_int_t x = 0; x < vis_w; ++x) {
            mp_int_t sx = src_x0 + x;
            mp_int_t dx = draw_x0 + x;
            size_t byte_index = (size_t)sy * mask_row_bytes + ((size_t)sx / 8u);
            int bit_index = 7 - (int)(sx % 8);
            uint8_t visible = (mask[byte_index] >> bit_index) & 0x01u;
            if (visible) {
                size_t src_index = ((size_t)sy * (size_t)sprite_w + (size_t)sx) * 2u;
                size_t dst_index = ((size_t)dy * (size_t)dst_w + (size_t)dx) * 2u;
                dst[dst_index] = sprite[src_index];
                dst[dst_index + 1] = sprite[src_index + 1];
            }
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_compose_masked_rgb565_obj, 9, 9, lgfx_compose_masked_rgb565);


static mp_obj_t lgfx_compose_tilemap_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 11 && n_args != 12) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 11 or 12 args"));
    }

    mp_buffer_info_t dst_bufinfo;
    mp_buffer_info_t tilemap_bufinfo;
    mp_buffer_info_t tileset_bufinfo;
    mp_get_buffer_raise(args[0], &dst_bufinfo, MP_BUFFER_RW);
    mp_int_t dst_w = mp_obj_get_int(args[1]);
    mp_int_t dst_h = mp_obj_get_int(args[2]);
    mp_int_t camera_x = mp_obj_get_int(args[3]);
    mp_int_t band_top = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &tilemap_bufinfo, MP_BUFFER_READ);
    mp_int_t map_w = mp_obj_get_int(args[6]);
    mp_int_t map_h = mp_obj_get_int(args[7]);
    mp_get_buffer_raise(args[8], &tileset_bufinfo, MP_BUFFER_READ);
    mp_int_t tile_size = mp_obj_get_int(args[9]);
    mp_int_t tileset_w = mp_obj_get_int(args[10]);
    mp_int_t transparent_key = -1;
    if (n_args == 12) {
        transparent_key = mp_obj_get_int(args[11]);
    }

    if (dst_w <= 0 || dst_h <= 0 || map_w <= 0 || map_h <= 0 || tile_size <= 0 || tileset_w <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }
    if ((tileset_w % tile_size) != 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("tileset_w mismatch"));
    }
    if ((tileset_bufinfo.len & 1u) != 0u) {
        mp_raise_ValueError(MP_ERROR_TEXT("tileset len must be rgb565"));
    }

    size_t dst_need = (size_t)dst_w * (size_t)dst_h * 2u;
    if (dst_bufinfo.len < dst_need) {
        mp_raise_ValueError(MP_ERROR_TEXT("dst buf too small"));
    }
    size_t map_need = (size_t)map_w * (size_t)map_h;
    if (tilemap_bufinfo.len < map_need) {
        mp_raise_ValueError(MP_ERROR_TEXT("tilemap buf too small"));
    }

    size_t tile_bytes = (size_t)tile_size * (size_t)tile_size * 2u;
    if (tile_bytes == 0 || tileset_bufinfo.len < tile_bytes) {
        mp_raise_ValueError(MP_ERROR_TEXT("tileset buf too small"));
    }
    size_t tile_count = tileset_bufinfo.len / tile_bytes;
    size_t tileset_cols = (size_t)tileset_w / (size_t)tile_size;
    if (tileset_cols == 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("tileset cols invalid"));
    }

    uint8_t *dst = (uint8_t *)dst_bufinfo.buf;
    const uint8_t *tilemap = (const uint8_t *)tilemap_bufinfo.buf;
    const uint8_t *tileset = (const uint8_t *)tileset_bufinfo.buf;

    mp_int_t start_col = camera_x / tile_size;
    mp_int_t end_col = (camera_x + dst_w - 1) / tile_size;
    mp_int_t start_row = band_top / tile_size;
    mp_int_t end_row = (band_top + dst_h - 1) / tile_size;

    if (start_col < 0) {
        start_col = 0;
    }
    if (start_row < 0) {
        start_row = 0;
    }
    if (end_col >= map_w) {
        end_col = map_w - 1;
    }
    if (end_row >= map_h) {
        end_row = map_h - 1;
    }
    if (end_col < start_col || end_row < start_row) {
        return mp_const_none;
    }

    for (mp_int_t r = start_row; r <= end_row; ++r) {
        const uint8_t *map_row = tilemap + ((size_t)r * (size_t)map_w);
        for (mp_int_t c = start_col; c <= end_col; ++c) {
            uint8_t tid = map_row[c];
            if (tid == 0u) {
                continue;
            }
            size_t tile_idx = (size_t)tid - 1u;
            if (tile_idx >= tile_count) {
                continue;
            }

            mp_int_t dx = (c * tile_size) - camera_x;
            mp_int_t dy = (r * tile_size) - band_top;
            mp_int_t src_x0 = 0;
            mp_int_t src_y0 = 0;
            mp_int_t vis_w = tile_size;
            mp_int_t vis_h = tile_size;

            if (dx < 0) {
                src_x0 = -dx;
                vis_w -= src_x0;
                dx = 0;
            }
            if (dy < 0) {
                src_y0 = -dy;
                vis_h -= src_y0;
                dy = 0;
            }
            if (dx + vis_w > dst_w) {
                vis_w = dst_w - dx;
            }
            if (dy + vis_h > dst_h) {
                vis_h = dst_h - dy;
            }
            if (vis_w <= 0 || vis_h <= 0) {
                continue;
            }

            size_t atlas_col = tile_idx % tileset_cols;
            size_t atlas_row = tile_idx / tileset_cols;
            size_t tile_px_x = atlas_col * (size_t)tile_size;
            size_t tile_px_y = atlas_row * (size_t)tile_size;
            size_t src_row_base = ((tile_px_y + (size_t)src_y0) * (size_t)tileset_w + tile_px_x + (size_t)src_x0) * 2u;
            size_t src_stride = (size_t)tileset_w * 2u;
            size_t copy_bytes = (size_t)vis_w * 2u;

            for (mp_int_t y = 0; y < vis_h; ++y) {
                size_t src_off = src_row_base + ((size_t)y * src_stride);
                size_t dst_off = (((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u;
                if (transparent_key < 0) {
                    memcpy(dst + dst_off, tileset + src_off, copy_bytes);
                } else {
                    const uint8_t *src_row = tileset + src_off;
                    uint8_t *dst_row = dst + dst_off;
                    for (mp_int_t x = 0; x < vis_w; ++x) {
                        size_t b = (size_t)x * 2u;
                        uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                        if (px != (uint16_t)transparent_key) {
                            dst_row[b] = src_row[b];
                            dst_row[b + 1] = src_row[b + 1];
                        }
                    }
                }
            }
        }
    }

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_compose_tilemap_rgb565_obj, 11, 12, lgfx_compose_tilemap_rgb565);

static mp_obj_t lgfx_compose_colorkey_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 9) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 9 args"));
    }

    mp_buffer_info_t dst_bufinfo;
    mp_buffer_info_t src_bufinfo;
    mp_get_buffer_raise(args[0], &dst_bufinfo, MP_BUFFER_RW);
    mp_int_t dst_w = mp_obj_get_int(args[1]);
    mp_int_t dst_h = mp_obj_get_int(args[2]);
    mp_int_t dst_x = mp_obj_get_int(args[3]);
    mp_int_t dst_y = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &src_bufinfo, MP_BUFFER_READ);
    mp_int_t src_w = mp_obj_get_int(args[6]);
    mp_int_t src_h = mp_obj_get_int(args[7]);
    mp_int_t transparent_key = mp_obj_get_int(args[8]);

    if (dst_w <= 0 || dst_h <= 0 || src_w <= 0 || src_h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }

    size_t dst_need = (size_t)dst_w * (size_t)dst_h * 2u;
    if (dst_bufinfo.len < dst_need) {
        mp_raise_ValueError(MP_ERROR_TEXT("dst buf too small"));
    }
    size_t src_need = (size_t)src_w * (size_t)src_h * 2u;
    if (src_bufinfo.len < src_need) {
        mp_raise_ValueError(MP_ERROR_TEXT("src buf too small"));
    }

    if (dst_x >= dst_w || dst_y >= dst_h || (dst_x + src_w) <= 0 || (dst_y + src_h) <= 0) {
        return mp_const_none;
    }

    mp_int_t src_x0 = 0;
    mp_int_t src_y0 = 0;
    mp_int_t dx = dst_x;
    mp_int_t dy = dst_y;
    mp_int_t vis_w = src_w;
    mp_int_t vis_h = src_h;

    if (dx < 0) {
        src_x0 = -dx;
        vis_w -= src_x0;
        dx = 0;
    }
    if (dy < 0) {
        src_y0 = -dy;
        vis_h -= src_y0;
        dy = 0;
    }
    if (dx + vis_w > dst_w) {
        vis_w = dst_w - dx;
    }
    if (dy + vis_h > dst_h) {
        vis_h = dst_h - dy;
    }
    if (vis_w <= 0 || vis_h <= 0) {
        return mp_const_none;
    }

    uint8_t *dst = (uint8_t *)dst_bufinfo.buf;
    const uint8_t *src = (const uint8_t *)src_bufinfo.buf;
    size_t copy_bytes = (size_t)vis_w * 2u;

    for (mp_int_t y = 0; y < vis_h; ++y) {
        size_t src_off = (((size_t)(src_y0 + y) * (size_t)src_w) + (size_t)src_x0) * 2u;
        size_t dst_off = (((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u;
        if (transparent_key < 0) {
            memcpy(dst + dst_off, src + src_off, copy_bytes);
        } else {
            const uint8_t *src_row = src + src_off;
            uint8_t *dst_row = dst + dst_off;
            for (mp_int_t x = 0; x < vis_w; ++x) {
                size_t b = (size_t)x * 2u;
                uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                if (px != (uint16_t)transparent_key) {
                    dst_row[b] = src_row[b];
                    dst_row[b + 1] = src_row[b + 1];
                }
            }
        }
    }

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_compose_colorkey_rgb565_obj, 9, 9, lgfx_compose_colorkey_rgb565);

static mp_obj_t lgfx_compose_objects_atlas_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 11 && n_args != 12) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 11 or 12 args"));
    }

    mp_buffer_info_t dst_bufinfo;
    mp_buffer_info_t obj_bufinfo;
    mp_buffer_info_t atlas_bufinfo;
    mp_get_buffer_raise(args[0], &dst_bufinfo, MP_BUFFER_RW);
    mp_int_t dst_w = mp_obj_get_int(args[1]);
    mp_int_t dst_h = mp_obj_get_int(args[2]);
    mp_int_t camera_x = mp_obj_get_int(args[3]);
    mp_int_t band_top = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &obj_bufinfo, MP_BUFFER_READ);
    mp_int_t obj_stride = mp_obj_get_int(args[6]);
    mp_get_buffer_raise(args[7], &atlas_bufinfo, MP_BUFFER_READ);
    mp_int_t atlas_w = mp_obj_get_int(args[8]);
    mp_int_t atlas_h = mp_obj_get_int(args[9]);
    mp_int_t transparent_key = mp_obj_get_int(args[10]);
    mp_int_t object_count = -1;
    if (n_args == 12) {
        object_count = mp_obj_get_int(args[11]);
    }

    if (dst_w <= 0 || dst_h <= 0 || atlas_w <= 0 || atlas_h <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }
    if ((atlas_bufinfo.len & 1u) != 0u) {
        mp_raise_ValueError(MP_ERROR_TEXT("atlas len must be rgb565"));
    }
    if (obj_stride < 12) {
        mp_raise_ValueError(MP_ERROR_TEXT("obj stride too small"));
    }

    size_t dst_need = (size_t)dst_w * (size_t)dst_h * 2u;
    if (dst_bufinfo.len < dst_need) {
        mp_raise_ValueError(MP_ERROR_TEXT("dst buf too small"));
    }
    size_t atlas_need = (size_t)atlas_w * (size_t)atlas_h * 2u;
    if (atlas_bufinfo.len < atlas_need) {
        mp_raise_ValueError(MP_ERROR_TEXT("atlas buf too small"));
    }

    size_t available_count = obj_bufinfo.len / (size_t)obj_stride;
    size_t draw_count = available_count;
    if (object_count >= 0 && (size_t)object_count < draw_count) {
        draw_count = (size_t)object_count;
    }

    uint8_t *dst = (uint8_t *)dst_bufinfo.buf;
    const uint8_t *objbuf = (const uint8_t *)obj_bufinfo.buf;
    const uint8_t *atlas = (const uint8_t *)atlas_bufinfo.buf;
    size_t atlas_row_bytes = (size_t)atlas_w * 2u;

    for (size_t i = 0; i < draw_count; ++i) {
        const uint8_t *ob = objbuf + (i * (size_t)obj_stride);
        int16_t wx = (int16_t)((uint16_t)ob[0] | ((uint16_t)ob[1] << 8));
        int16_t wy = (int16_t)((uint16_t)ob[2] | ((uint16_t)ob[3] << 8));
        uint16_t sx_u = (uint16_t)ob[4] | ((uint16_t)ob[5] << 8);
        uint16_t sy_u = (uint16_t)ob[6] | ((uint16_t)ob[7] << 8);
        uint16_t sw_u = (uint16_t)ob[8] | ((uint16_t)ob[9] << 8);
        uint16_t sh_u = (uint16_t)ob[10] | ((uint16_t)ob[11] << 8);

        mp_int_t src_x = (mp_int_t)sx_u;
        mp_int_t src_y = (mp_int_t)sy_u;
        mp_int_t src_w = (mp_int_t)sw_u;
        mp_int_t src_h = (mp_int_t)sh_u;
        if (src_w <= 0 || src_h <= 0) {
            continue;
        }
        if (src_x < 0 || src_y < 0 || src_x + src_w > atlas_w || src_y + src_h > atlas_h) {
            continue;
        }

        mp_int_t dx = (mp_int_t)wx - camera_x;
        mp_int_t dy = (mp_int_t)wy - band_top;
        mp_int_t src_x0 = 0;
        mp_int_t src_y0 = 0;
        mp_int_t vis_w = src_w;
        mp_int_t vis_h = src_h;

        if (dx < 0) {
            src_x0 = -dx;
            vis_w -= src_x0;
            dx = 0;
        }
        if (dy < 0) {
            src_y0 = -dy;
            vis_h -= src_y0;
            dy = 0;
        }
        if (dx + vis_w > dst_w) {
            vis_w = dst_w - dx;
        }
        if (dy + vis_h > dst_h) {
            vis_h = dst_h - dy;
        }
        if (vis_w <= 0 || vis_h <= 0) {
            continue;
        }

        size_t src_row_base = ((size_t)(src_y + src_y0) * (size_t)atlas_w + (size_t)(src_x + src_x0)) * 2u;
        size_t copy_bytes = (size_t)vis_w * 2u;

        for (mp_int_t y = 0; y < vis_h; ++y) {
            size_t src_off = src_row_base + ((size_t)y * atlas_row_bytes);
            size_t dst_off = (((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u;
            if (transparent_key < 0) {
                memcpy(dst + dst_off, atlas + src_off, copy_bytes);
            } else {
                const uint8_t *src_row = atlas + src_off;
                uint8_t *dst_row = dst + dst_off;
                for (mp_int_t x = 0; x < vis_w; ++x) {
                    size_t b = (size_t)x * 2u;
                    uint16_t px = (uint16_t)src_row[b] | ((uint16_t)src_row[b + 1] << 8);
                    if (px != (uint16_t)transparent_key) {
                        dst_row[b] = src_row[b];
                        dst_row[b + 1] = src_row[b + 1];
                    }
                }
            }
        }
    }

    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_compose_objects_atlas_rgb565_obj, 11, 12, lgfx_compose_objects_atlas_rgb565);

static mp_obj_t lgfx_png_rect565(size_t n_args, const mp_obj_t *args) {
    const char *path = mp_obj_str_get_str(args[0]);
    mp_int_t sx = mp_obj_get_int(args[1]);
    mp_int_t sy = mp_obj_get_int(args[2]);
    mp_int_t w = mp_obj_get_int(args[3]);
    mp_int_t h = mp_obj_get_int(args[4]);
    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[5], &bufinfo, MP_BUFFER_WRITE);
    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    uint32_t preset_after_count = 0;
    bool ok = decode_png_rect_to_rgb565_row_major(
        path,
        (int32_t)sx,
        (int32_t)sy,
        (int32_t)w,
        (int32_t)h,
        (uint16_t *)bufinfo.buf,
        0xF81F,
        &preset_after_count
    );
    if (!ok) {
        int err = errno;
        if (err == ENOMEM) {
            mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("png file alloc failed"));
        }
        if (err == 0) {
            err = EIO;
        }
        mp_raise_OSError(err);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_png_rect565_obj, 6, 6, lgfx_png_rect565);

static mp_obj_t lgfx_png_over_rect565(size_t n_args, const mp_obj_t *args) {
    const char *path = mp_obj_str_get_str(args[0]);
    mp_int_t sx = mp_obj_get_int(args[1]);
    mp_int_t sy = mp_obj_get_int(args[2]);
    mp_int_t w = mp_obj_get_int(args[3]);
    mp_int_t h = mp_obj_get_int(args[4]);
    if (w <= 0 || h <= 0) {
        return mp_const_none;
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[5], &bufinfo, MP_BUFFER_RW);
    size_t expected_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len != expected_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf len mismatch"));
    }

    lgfx::v1::LGFX_Sprite sprite(&lcd);
    sprite.setColorDepth(16);
    if (!sprite.createSprite((int32_t)w, (int32_t)h)) {
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("sprite alloc failed"));
    }

    sprite.pushImage(0, 0, (int32_t)w, (int32_t)h, (const uint16_t *)bufinfo.buf);
    bool ok = draw_png_from_path(
        &sprite,
        path,
        (int32_t)sx,
        (int32_t)sy,
        (int32_t)w,
        (int32_t)h
    );
    if (!ok) {
        int err = errno;
        sprite.deleteSprite();
        if (err == ENOMEM) {
            mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("png file alloc failed"));
        }
        if (err == 0) {
            err = EIO;
        }
        mp_raise_OSError(err);
    }
    sprite.readRect(0, 0, (int32_t)w, (int32_t)h, (uint16_t *)bufinfo.buf);
    sprite.deleteSprite();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_png_over_rect565_obj, 6, 6, lgfx_png_over_rect565);

static mp_obj_t lgfx_png_rect_raw_test(size_t n_args, const mp_obj_t *args) {
    const char *path = mp_obj_str_get_str(args[0]);
    mp_int_t sx = mp_obj_get_int(args[1]);
    mp_int_t sy = mp_obj_get_int(args[2]);
    mp_int_t w = mp_obj_get_int(args[3]);
    mp_int_t h = mp_obj_get_int(args[4]);
    mp_int_t dx = mp_obj_get_int(args[5]);
    mp_int_t dy = mp_obj_get_int(args[6]);
    if (w <= 0 || h <= 0) {
        return MP_OBJ_NEW_SMALL_INT(0);
    }

    size_t pix_count = (size_t)w * (size_t)h;
    size_t bytes_len = pix_count * 2u;
    uint16_t *tmp = (uint16_t *)malloc(bytes_len);
    if (tmp == nullptr) {
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("raw test alloc failed"));
    }

    uint32_t preset_after = 0;
    bool ok = decode_png_rect_to_rgb565_row_major(
        path,
        (int32_t)sx,
        (int32_t)sy,
        (int32_t)w,
        (int32_t)h,
        tmp,
        0xF81F,
        &preset_after
    );
    if (!ok) {
        int err = errno;
        free(tmp);
        if (err == ENOMEM) {
            mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("raw test decode alloc failed"));
        }
        if (err == 0) {
            err = EIO;
        }
        mp_raise_OSError(err);
    }

    bool prev_swap = lcd.getSwapBytes();
    lcd.setSwapBytes(true);
    lcd.pushImage((int32_t)dx, (int32_t)dy, (int32_t)w, (int32_t)h, tmp);
    lcd.setSwapBytes(prev_swap);

    free(tmp);
    return MP_OBJ_NEW_SMALL_INT((mp_int_t)preset_after);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_png_rect_raw_test_obj, 7, 7, lgfx_png_rect_raw_test);

static mp_obj_t lgfx_draw_png_mem(size_t n_args, const mp_obj_t *args) {
    const char *path = mp_obj_str_get_str(args[0]);
    mp_int_t x = mp_obj_get_int(args[1]);
    mp_int_t y = mp_obj_get_int(args[2]);

    size_t png_len = 0;
    uint8_t *png_data = read_file_bytes(path, &png_len);
    if (png_data == nullptr || png_len == 0) {
        int err = errno;
        if (err == 0) {
            err = EIO;
        }
        mp_raise_OSError(err);
    }

    bool ok = lcd.drawPng(
        png_data,
        (uint32_t)png_len,
        (int32_t)x,
        (int32_t)y,
        0,
        0,
        0,
        0,
        1.0f,
        1.0f,
        (lgfx::v1::datum_t)0
    );
    free(png_data);

    if (!ok) {
        mp_raise_OSError(EIO);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_draw_png_mem_obj, 3, 3, lgfx_draw_png_mem);

static const mp_rom_map_elem_t lgfx_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_lgfx) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_PTR(&lgfx_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill), MP_ROM_PTR(&lgfx_fill_obj) },
    { MP_ROM_QSTR(MP_QSTR_rotation), MP_ROM_PTR(&lgfx_rotation_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill_rect), MP_ROM_PTR(&lgfx_fill_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565), MP_ROM_PTR(&lgfx_blit_rect565_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_rows), MP_ROM_PTR(&lgfx_blit_rect565_rows_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait), MP_ROM_PTR(&lgfx_blit_rect565_wait_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_wait), MP_ROM_PTR(&lgfx_blit_rect565_wire_wait_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_async), MP_ROM_PTR(&lgfx_blit_rect565_async_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_async), MP_ROM_PTR(&lgfx_blit_rect565_wire_async_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_wait_done), MP_ROM_PTR(&lgfx_blit_wait_done_obj) },
    { MP_ROM_QSTR(MP_QSTR_async_probe_rgb565), MP_ROM_PTR(&lgfx_async_probe_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_submit_probe_rgb565), MP_ROM_PTR(&lgfx_submit_probe_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_band_submit_probe_rgb565), MP_ROM_PTR(&lgfx_band_submit_probe_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_render_scene_bands_rgb565), MP_ROM_PTR(&lgfx_render_scene_bands_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_rgb565_swap_bytes_inplace), MP_ROM_PTR(&lgfx_rgb565_swap_bytes_inplace_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait_copy), MP_ROM_PTR(&lgfx_blit_rect565_wait_copy_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait_copy_compat), MP_ROM_PTR(&lgfx_blit_rect565_wait_copy_compat_obj) },
    { MP_ROM_QSTR(MP_QSTR_compose_masked_rgb565), MP_ROM_PTR(&lgfx_compose_masked_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_compose_tilemap_rgb565), MP_ROM_PTR(&lgfx_compose_tilemap_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_compose_colorkey_rgb565), MP_ROM_PTR(&lgfx_compose_colorkey_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_compose_objects_atlas_rgb565), MP_ROM_PTR(&lgfx_compose_objects_atlas_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_png_rect565), MP_ROM_PTR(&lgfx_png_rect565_obj) },
    { MP_ROM_QSTR(MP_QSTR_png_over_rect565), MP_ROM_PTR(&lgfx_png_over_rect565_obj) },
    { MP_ROM_QSTR(MP_QSTR_png_rect_raw_test), MP_ROM_PTR(&lgfx_png_rect_raw_test_obj) },
    { MP_ROM_QSTR(MP_QSTR_draw_png_mem), MP_ROM_PTR(&lgfx_draw_png_mem_obj) },
    { MP_ROM_QSTR(MP_QSTR_TFT_BLACK), MP_ROM_INT(0x0000) },
    { MP_ROM_QSTR(MP_QSTR_TFT_WHITE), MP_ROM_INT(0xFFFF) },
    { MP_ROM_QSTR(MP_QSTR_TFT_RED), MP_ROM_INT(0xF800) },
    { MP_ROM_QSTR(MP_QSTR_TFT_GREEN), MP_ROM_INT(0x07E0) },
    { MP_ROM_QSTR(MP_QSTR_TFT_BLUE), MP_ROM_INT(0x001F) },
};
static MP_DEFINE_CONST_DICT(lgfx_module_globals, lgfx_module_globals_table);

const mp_obj_module_t lgfx_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&lgfx_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_lgfx, lgfx_user_cmodule);

} // extern "C"
#else
extern "C" {

static const mp_rom_map_elem_t lgfx_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_lgfx) },
    { MP_ROM_QSTR(MP_QSTR_init), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_fill), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_rotation), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_fill_rect), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_rows), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_wait), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_async), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_async), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_wait_done), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_async_probe_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_submit_probe_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_band_submit_probe_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_render_scene_bands_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_rgb565_swap_bytes_inplace), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait_copy), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait_copy_compat), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_compose_masked_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_compose_tilemap_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_compose_colorkey_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_compose_objects_atlas_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_png_rect565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_png_over_rect565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_png_rect_raw_test), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_draw_png_mem), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_TFT_BLACK), MP_ROM_INT(0x0000) },
    { MP_ROM_QSTR(MP_QSTR_TFT_WHITE), MP_ROM_INT(0xFFFF) },
    { MP_ROM_QSTR(MP_QSTR_TFT_RED), MP_ROM_INT(0xF800) },
    { MP_ROM_QSTR(MP_QSTR_TFT_GREEN), MP_ROM_INT(0x07E0) },
    { MP_ROM_QSTR(MP_QSTR_TFT_BLUE), MP_ROM_INT(0x001F) },
};
static MP_DEFINE_CONST_DICT(lgfx_module_globals, lgfx_module_globals_table);

const mp_obj_module_t lgfx_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&lgfx_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_lgfx, lgfx_user_cmodule);

} // extern "C"
#endif
