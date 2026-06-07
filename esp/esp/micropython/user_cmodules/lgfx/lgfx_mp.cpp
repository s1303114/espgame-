#include <stdint.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
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
extern "C" mp_obj_t lgfx_band_pipeline_tail_wait(void);

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
static MP_DEFINE_CONST_FUN_OBJ_0(lgfx_band_pipeline_tail_wait_obj, lgfx_band_pipeline_tail_wait);


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



static inline int16_t lgfx_rd_i16(const uint8_t *p) {
    return (int16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static inline void lgfx_wr_i16(uint8_t *p, int32_t v) {
    if (v < -32768) v = -32768;
    if (v > 32767) v = 32767;
    uint16_t uv = (uint16_t)((int16_t)v);
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
}

static inline int32_t lgfx_clamp_i32(int32_t v, int32_t lo, int32_t hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static inline uint16_t lgfx_rd_u16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static inline void lgfx_wr_u16(uint8_t *p, uint32_t v) {
    uint16_t uv = (uint16_t)(v & 0xFFFFu);
    p[0] = (uint8_t)(uv & 0xFFu);
    p[1] = (uint8_t)((uv >> 8) & 0xFFu);
}

static inline int32_t lgfx_move_toward_i32(int32_t curr_v, int32_t target_v, int32_t speed_px) {
    int32_t step = speed_px < 1 ? 1 : speed_px;
    int32_t delta = target_v - curr_v;
    if (delta > 0) {
        curr_v += delta < step ? delta : step;
    } else if (delta < 0) {
        int32_t mag = -delta;
        curr_v -= mag < step ? mag : step;
    }
    return curr_v;
}

static const int32_t LGFX_MONK_ORB_COUNT = 5;
static const int32_t LGFX_MONK_ORB_RADIUS = 28;
static const int32_t LGFX_MONK_ORB_W = 16;
static const int32_t LGFX_MONK_ORB_H = 16;
static const int32_t LGFX_MONK_ORB_SCALE = 1024;
static const int32_t LGFX_MONK_ORB_TABLE_SIZE = 60;
static const int16_t LGFX_MONK_ORB_COS[LGFX_MONK_ORB_TABLE_SIZE] = {
    1024, 1018, 1002, 974, 935, 887, 828, 761, 685, 602,
    512, 416, 316, 213, 107, 0, -107, -213, -316, -416,
    -512, -602, -685, -761, -828, -887, -935, -974, -1002, -1018,
    -1024, -1018, -1002, -974, -935, -887, -828, -761, -685, -602,
    -512, -416, -316, -213, -107, 0, 107, 213, 316, 416,
    512, 602, 685, 761, 828, 887, 935, 974, 1002, 1018
};
static const int16_t LGFX_MONK_ORB_SIN[LGFX_MONK_ORB_TABLE_SIZE] = {
    0, 107, 213, 316, 416, 512, 602, 685, 761, 828,
    887, 935, 974, 1002, 1018, 1024, 1018, 1002, 974, 935,
    887, 828, 761, 685, 602, 512, 416, 316, 213, 107,
    0, -107, -213, -316, -416, -512, -602, -685, -761, -828,
    -887, -935, -974, -1002, -1018, -1024, -1018, -1002, -974, -935,
    -887, -828, -761, -685, -602, -512, -416, -316, -213, -107
};

static void lgfx_monk_enemy_draw_origin(
    int32_t wx,
    int32_t wy,
    int32_t ow,
    int32_t oh,
    int32_t monk_frame_w,
    int32_t monk_frame_h,
    int32_t *draw_x,
    int32_t *draw_y
) {
    int32_t dx = wx;
    int32_t dy = wy;
    if (monk_frame_w > 0 && ow != monk_frame_w) {
        dx = wx + ((ow - monk_frame_w) / 2);
    }
    if (monk_frame_h > 0 && oh != monk_frame_h) {
        dy = wy + (oh - monk_frame_h);
    }
    *draw_x = dx;
    *draw_y = dy;
}

static void lgfx_monk_orb_slot_world_pos(
    int32_t wx,
    int32_t wy,
    int32_t ow,
    int32_t oh,
    int32_t anim_counter,
    int32_t slot_i,
    int32_t monk_frame_w,
    int32_t monk_frame_h,
    int32_t *orb_x,
    int32_t *orb_y
) {
    int32_t draw_x = wx;
    int32_t draw_y = wy;
    lgfx_monk_enemy_draw_origin(wx, wy, ow, oh, monk_frame_w, monk_frame_h, &draw_x, &draw_y);
    int32_t center_x = draw_x + (monk_frame_w / 2);
    int32_t center_y = draw_y + (monk_frame_h / 2);
    int32_t angle_idx = (anim_counter + ((slot_i * LGFX_MONK_ORB_TABLE_SIZE) / LGFX_MONK_ORB_COUNT)) % LGFX_MONK_ORB_TABLE_SIZE;
    if (angle_idx < 0) {
        angle_idx += LGFX_MONK_ORB_TABLE_SIZE;
    }
    int32_t orb_cx = center_x + ((LGFX_MONK_ORB_COS[angle_idx] * LGFX_MONK_ORB_RADIUS) / LGFX_MONK_ORB_SCALE);
    int32_t orb_cy = center_y - ((LGFX_MONK_ORB_SIN[angle_idx] * LGFX_MONK_ORB_RADIUS) / LGFX_MONK_ORB_SCALE);
    *orb_x = orb_cx - (LGFX_MONK_ORB_W / 2);
    *orb_y = orb_cy - (LGFX_MONK_ORB_H / 2);
}

static int32_t lgfx_isqrt_i32(int32_t value) {
    if (value <= 0) {
        return 0;
    }
    int32_t result = 0;
    int32_t bit = 1 << 30;
    while (bit > value) {
        bit >>= 2;
    }
    while (bit != 0) {
        if (value >= result + bit) {
            value -= result + bit;
            result = (result >> 1) + bit;
        } else {
            result >>= 1;
        }
        bit >>= 2;
    }
    return result;
}

static void lgfx_monk_orb_pos_from_idx(int32_t center_x, int32_t center_y, int32_t radius_px, int32_t angle_idx, int32_t *orb_x, int32_t *orb_y) {
    int32_t idx = angle_idx % LGFX_MONK_ORB_TABLE_SIZE;
    if (idx < 0) {
        idx += LGFX_MONK_ORB_TABLE_SIZE;
    }
    int32_t orb_cx = center_x + ((LGFX_MONK_ORB_COS[idx] * radius_px) / LGFX_MONK_ORB_SCALE);
    int32_t orb_cy = center_y - ((LGFX_MONK_ORB_SIN[idx] * radius_px) / LGFX_MONK_ORB_SCALE);
    *orb_x = orb_cx - (LGFX_MONK_ORB_W / 2);
    *orb_y = orb_cy - (LGFX_MONK_ORB_H / 2);
}

static mp_obj_t lgfx_update_monk_orbs_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 10) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 10 args"));
    }

    mp_buffer_info_t orb_info;
    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t enemy_states_info;
    mp_get_buffer_raise(args[0], &orb_info, MP_BUFFER_RW);
    mp_int_t orb_stride = mp_obj_get_int(args[1]);
    mp_int_t orb_count = mp_obj_get_int(args[2]);
    mp_get_buffer_raise(args[3], &enemy_rows_info, MP_BUFFER_READ);
    mp_int_t enemy_row_stride = mp_obj_get_int(args[4]);
    mp_int_t enemy_count = mp_obj_get_int(args[5]);
    mp_get_buffer_raise(args[6], &enemy_states_info, MP_BUFFER_READ);
    mp_int_t enemy_state_stride = mp_obj_get_int(args[7]);
    mp_int_t monk_frame_w = mp_obj_get_int(args[8]);
    mp_int_t monk_frame_h = mp_obj_get_int(args[9]);

    if (orb_stride < 16 || orb_count < 0 || enemy_row_stride < 12 || enemy_state_stride < 8 || enemy_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid monk orb dims"));
    }
    if (orb_info.len < (size_t)orb_stride * (size_t)orb_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk orb buf too small"));
    }
    if (enemy_rows_info.len < (size_t)enemy_row_stride * (size_t)enemy_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy rows buf too small"));
    }
    if (enemy_states_info.len < (size_t)enemy_state_stride * (size_t)enemy_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy states buf too small"));
    }
    if (monk_frame_w < 1) {
        monk_frame_w = 32;
    }
    if (monk_frame_h < 1) {
        monk_frame_h = 48;
    }

    uint8_t *orb_buf = (uint8_t *)orb_info.buf;
    const uint8_t *enemy_rows = (const uint8_t *)enemy_rows_info.buf;
    const uint8_t *enemy_states = (const uint8_t *)enemy_states_info.buf;
    int32_t updated = 0;
    for (int32_t oi = 0; oi < orb_count; ++oi) {
        uint8_t *orb = orb_buf + ((size_t)oi * (size_t)orb_stride);
        uint8_t mode = orb[0];
        if (mode == 0xFFu || mode == 3u || mode == 4u) {
            continue;
        }
        int32_t enemy_i = oi / LGFX_MONK_ORB_COUNT;
        int32_t slot_i = (int32_t)orb[1];
        if (slot_i < 0 || slot_i >= LGFX_MONK_ORB_COUNT) {
            slot_i = oi % LGFX_MONK_ORB_COUNT;
            orb[1] = (uint8_t)slot_i;
        }
        if (enemy_i < 0 || enemy_i >= enemy_count) {
            continue;
        }
        const uint8_t *row = enemy_rows + ((size_t)enemy_i * (size_t)enemy_row_stride);
        const uint8_t *state = enemy_states + ((size_t)enemy_i * (size_t)enemy_state_stride);
        if (!row[8]) {
            continue;
        }
        int32_t wx = lgfx_rd_i16(row + 0);
        int32_t wy = lgfx_rd_i16(row + 2);
        int32_t ow = lgfx_rd_i16(row + 4);
        int32_t oh = lgfx_rd_i16(row + 6);
        int32_t anim_counter = lgfx_rd_i16(state + 2);
        int32_t draw_x = wx;
        int32_t draw_y = wy;
        lgfx_monk_enemy_draw_origin(wx, wy, ow, oh, monk_frame_w, monk_frame_h, &draw_x, &draw_y);
        int32_t center_x = draw_x + (monk_frame_w / 2);
        int32_t center_y = draw_y + (monk_frame_h / 2);
        int32_t angle_idx = (anim_counter + ((slot_i * LGFX_MONK_ORB_TABLE_SIZE) / LGFX_MONK_ORB_COUNT)) % LGFX_MONK_ORB_TABLE_SIZE;
        if (angle_idx < 0) {
            angle_idx += LGFX_MONK_ORB_TABLE_SIZE;
        }
        int32_t out_x = 0;
        int32_t out_y = 0;
        if (mode == 0u) {
            lgfx_monk_orb_pos_from_idx(center_x, center_y, LGFX_MONK_ORB_RADIUS, angle_idx, &out_x, &out_y);
            lgfx_wr_i16(orb + 8, LGFX_MONK_ORB_RADIUS);
        } else if (mode == 1u) {
            int32_t detached_x = lgfx_rd_i16(orb + 4);
            int32_t detached_y = lgfx_rd_i16(orb + 6);
            int32_t rel_x = (detached_x + (LGFX_MONK_ORB_W / 2)) - center_x;
            int32_t rel_y = center_y - (detached_y + (LGFX_MONK_ORB_H / 2));
            int32_t radius_px = lgfx_isqrt_i32((rel_x * rel_x) + (rel_y * rel_y));
            int32_t capture_eps = 6;
            if (radius_px > LGFX_MONK_ORB_RADIUS) {
                capture_eps += (radius_px - LGFX_MONK_ORB_RADIUS) / 12;
            }
            if (capture_eps > 24) {
                capture_eps = 24;
            }
            int32_t along_scaled = (rel_x * LGFX_MONK_ORB_COS[angle_idx]) + (rel_y * LGFX_MONK_ORB_SIN[angle_idx]);
            int32_t perp_scaled = (rel_x * LGFX_MONK_ORB_SIN[angle_idx]) - (rel_y * LGFX_MONK_ORB_COS[angle_idx]);
            if (perp_scaled < 0) {
                perp_scaled = -perp_scaled;
            }
            if (along_scaled > 0 && perp_scaled <= (capture_eps * LGFX_MONK_ORB_SCALE)) {
                mode = 2u;
                orb[0] = mode;
                orb[2] = 4u;
                lgfx_wr_i16(orb + 8, radius_px);
                lgfx_monk_orb_pos_from_idx(center_x, center_y, radius_px, angle_idx, &out_x, &out_y);
            } else {
                out_x = detached_x;
                out_y = detached_y;
            }
        } else if (mode == 2u) {
            uint8_t capture_lock = orb[2];
            if (capture_lock > 0) {
                orb[2] = (uint8_t)(capture_lock - 1u);
            }
            int32_t radius_px = lgfx_rd_i16(orb + 8);
            if (radius_px <= 0) {
                radius_px = LGFX_MONK_ORB_RADIUS;
            }
            if (radius_px <= (LGFX_MONK_ORB_RADIUS + 1)) {
                radius_px = LGFX_MONK_ORB_RADIUS;
                orb[0] = 0u;
            } else {
                int32_t shrink = (radius_px - LGFX_MONK_ORB_RADIUS) / 20;
                if (shrink < 1) {
                    shrink = 1;
                }
                radius_px -= shrink;
                if (radius_px <= (LGFX_MONK_ORB_RADIUS + 1)) {
                    radius_px = LGFX_MONK_ORB_RADIUS;
                    orb[0] = 0u;
                }
            }
            lgfx_wr_i16(orb + 8, radius_px);
            lgfx_monk_orb_pos_from_idx(center_x, center_y, radius_px, angle_idx, &out_x, &out_y);
        } else {
            continue;
        }
        lgfx_wr_i16(orb + 10, out_x);
        lgfx_wr_i16(orb + 12, out_y);
        orb[3] = 1u;
        updated += 1;
    }
    return mp_obj_new_int(updated);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_monk_orbs_native_obj, 10, 10, lgfx_update_monk_orbs_native);

static bool lgfx_aabb_near_view_early(
    int32_t wx,
    int32_t wy,
    int32_t w,
    int32_t h,
    int32_t camera_x,
    int32_t view_w,
    int32_t view_h,
    int32_t margin_x,
    int32_t margin_y
) {
    if (w <= 0 || h <= 0 || view_w <= 0 || view_h <= 0) {
        return false;
    }
    int32_t left = wx;
    int32_t top = wy;
    int32_t right = left + w;
    int32_t bottom = top + h;
    int32_t view_left = camera_x - margin_x;
    int32_t view_top = -margin_y;
    int32_t view_right = camera_x + view_w + margin_x;
    int32_t view_bottom = view_h + margin_y;
    return left < view_right && right > view_left && top < view_bottom && bottom > view_top;
}

static mp_obj_t lgfx_pack_monk_orb_descriptors_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 14) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 14 args"));
    }

    mp_buffer_info_t out_info;
    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t monk_orbs_info;
    mp_get_buffer_raise(args[0], &out_info, MP_BUFFER_RW);
    mp_int_t out_stride = mp_obj_get_int(args[1]);
    mp_get_buffer_raise(args[2], &enemy_rows_info, MP_BUFFER_READ);
    mp_int_t enemy_row_stride = mp_obj_get_int(args[3]);
    mp_int_t enemy_count = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &monk_orbs_info, MP_BUFFER_READ);
    mp_int_t orb_stride = mp_obj_get_int(args[6]);
    mp_int_t orb_count = mp_obj_get_int(args[7]);
    mp_int_t camera_x = mp_obj_get_int(args[8]);
    mp_int_t view_w = mp_obj_get_int(args[9]);
    mp_int_t view_h = mp_obj_get_int(args[10]);
    mp_int_t monk_frame_w = mp_obj_get_int(args[11]);
    mp_int_t monk_frame_h = mp_obj_get_int(args[12]);
    mp_int_t max_out_count = mp_obj_get_int(args[13]);

    if (out_stride < 8 || enemy_row_stride < 12 || orb_stride < 16 || enemy_count < 0 || orb_count < 0 || max_out_count < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid monk orb desc dims"));
    }
    if (enemy_rows_info.len < (size_t)enemy_count * (size_t)enemy_row_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy rows buf too small"));
    }
    if (monk_orbs_info.len < (size_t)orb_count * (size_t)orb_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk orb buf too small"));
    }
    if (out_info.len < (size_t)max_out_count * (size_t)out_stride) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk orb desc out too small"));
    }
    if (view_w <= 0 || view_h <= 0) {
        return MP_OBJ_NEW_SMALL_INT(0);
    }
    if (monk_frame_w < 1) {
        monk_frame_w = 32;
    }
    if (monk_frame_h < 1) {
        monk_frame_h = 48;
    }

    uint8_t *out = (uint8_t *)out_info.buf;
    const uint8_t *enemy_rows = (const uint8_t *)enemy_rows_info.buf;
    const uint8_t *orbs = (const uint8_t *)monk_orbs_info.buf;
    int32_t count = 0;
    int32_t per_enemy_orbs = LGFX_MONK_ORB_COUNT;
    int32_t enemy_limit = enemy_count;
    int32_t orb_enemy_limit = orb_count / per_enemy_orbs;
    if (enemy_limit > orb_enemy_limit) {
        enemy_limit = orb_enemy_limit;
    }

    for (int32_t ei = 0; ei < enemy_limit && count < max_out_count; ++ei) {
        const uint8_t *row = enemy_rows + ((size_t)ei * (size_t)enemy_row_stride);
        if (!row[8]) {
            continue;
        }
        int32_t wx = lgfx_rd_i16(row + 0);
        int32_t wy = lgfx_rd_i16(row + 2);
        int32_t ow = lgfx_rd_i16(row + 4);
        int32_t oh = lgfx_rd_i16(row + 6);
        int32_t draw_x = wx;
        int32_t draw_y = wy;
        lgfx_monk_enemy_draw_origin(wx, wy, ow, oh, monk_frame_w, monk_frame_h, &draw_x, &draw_y);
        int32_t orb_extent = LGFX_MONK_ORB_RADIUS + (LGFX_MONK_ORB_W / 2);
        if (!lgfx_aabb_near_view_early(draw_x - orb_extent, draw_y - orb_extent, monk_frame_w + (orb_extent * 2), monk_frame_h + (orb_extent * 2), camera_x, view_w, view_h, 48, 32)) {
            continue;
        }
        for (int32_t si = 0; si < per_enemy_orbs && count < max_out_count; ++si) {
            int32_t oi = (ei * per_enemy_orbs) + si;
            if (oi < 0 || oi >= orb_count) {
                continue;
            }
            const uint8_t *orb = orbs + ((size_t)oi * (size_t)orb_stride);
            uint8_t mode = orb[0];
            if (mode == 0xFFu || mode == 3u || mode == 4u) {
                continue;
            }
            int32_t orb_x = lgfx_rd_i16(orb + 10);
            int32_t orb_y = lgfx_rd_i16(orb + 12);
            if (!lgfx_aabb_near_view_early(orb_x, orb_y, LGFX_MONK_ORB_W, LGFX_MONK_ORB_H, camera_x, view_w, view_h, 48, 32)) {
                continue;
            }
            uint8_t *dst = out + ((size_t)count * (size_t)out_stride);
            lgfx_wr_i16(dst + 0, orb_x);
            lgfx_wr_i16(dst + 2, orb_y);
            dst[4] = 2u;
            dst[5] = (uint8_t)(si & 0xFF);
            dst[6] = 0u;
            dst[7] = 0u;
            count += 1;
        }
    }
    return mp_obj_new_int(count);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_pack_monk_orb_descriptors_native_obj, 14, 14, lgfx_pack_monk_orb_descriptors_native);

static mp_obj_t lgfx_update_monk_intro_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 7) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 7 args"));
    }

    mp_buffer_info_t intro_info;
    mp_get_buffer_raise(args[0], &intro_info, MP_BUFFER_RW);
    mp_int_t stride = mp_obj_get_int(args[1]);
    mp_int_t count = mp_obj_get_int(args[2]);
    mp_int_t drop_speed = mp_obj_get_int(args[3]);
    mp_int_t monk_frame_w = mp_obj_get_int(args[4]);
    mp_int_t monk_frame_h = mp_obj_get_int(args[5]);
    mp_int_t orb_count = mp_obj_get_int(args[6]);

    if (stride < 64 || count < 0 || orb_count < 0 || orb_count > LGFX_MONK_ORB_COUNT) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid monk intro dims"));
    }
    if (intro_info.len < (size_t)stride * (size_t)count) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk intro buf too small"));
    }
    if (drop_speed < 1) {
        drop_speed = 1;
    }
    if (monk_frame_w < 1) {
        monk_frame_w = 32;
    }
    if (monk_frame_h < 1) {
        monk_frame_h = 48;
    }

    uint8_t *buf = (uint8_t *)intro_info.buf;
    int32_t changed = 0;
    for (int32_t i = 0; i < count; ++i) {
        uint8_t *row = buf + ((size_t)i * (size_t)stride);
        uint8_t state = row[0];
        if (state != 1u) {
            continue;
        }
        int32_t body_x = lgfx_rd_i16(row + 4);
        int32_t body_y = lgfx_rd_i16(row + 6);
        int32_t body_w = lgfx_rd_i16(row + 8);
        int32_t body_h = lgfx_rd_i16(row + 10);
        int32_t target_x = lgfx_rd_i16(row + 12);
        int32_t target_y = lgfx_rd_i16(row + 14);
        int32_t target_bottom_y = lgfx_rd_i16(row + 16);
        int32_t anim_counter = (int32_t)lgfx_rd_u16(row + 18);
        if (body_w <= 0) {
            body_w = 48;
        }
        if (body_h <= 0) {
            body_h = 64;
        }
        int32_t body_bottom_y = body_y + body_h;
        body_bottom_y = lgfx_move_toward_i32(body_bottom_y, target_bottom_y, drop_speed);
        body_y = body_bottom_y - body_h;
        body_x = target_x;
        anim_counter += 1;
        if (anim_counter > 30000) {
            anim_counter = 0;
        }
        lgfx_wr_i16(row + 4, body_x);
        lgfx_wr_i16(row + 6, body_y);
        lgfx_wr_u16(row + 18, (uint32_t)anim_counter);

        for (int32_t slot_i = 0; slot_i < orb_count; ++slot_i) {
            int32_t orb_x = 0;
            int32_t orb_y = 0;
            lgfx_monk_orb_slot_world_pos(body_x, body_y, body_w, body_h, anim_counter, slot_i, monk_frame_w, monk_frame_h, &orb_x, &orb_y);
            size_t orb_base = 20u + ((size_t)slot_i * 4u);
            if (orb_base + 4u <= (size_t)stride) {
                lgfx_wr_i16(row + orb_base + 0, orb_x);
                lgfx_wr_i16(row + orb_base + 2, orb_y);
            }
        }
        if (body_y == target_y) {
            row[0] = 2u;
        }
        changed += 1;
    }
    return mp_obj_new_int(changed);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_monk_intro_native_obj, 7, 7, lgfx_update_monk_intro_native);

static bool lgfx_aabb_near_view(
    int32_t wx,
    int32_t wy,
    int32_t w,
    int32_t h,
    int32_t camera_x,
    int32_t view_w,
    int32_t view_h,
    int32_t margin_x,
    int32_t margin_y
) {
    if (w <= 0 || h <= 0 || view_w <= 0 || view_h <= 0) {
        return false;
    }
    int32_t left = wx;
    int32_t top = wy;
    int32_t right = left + w;
    int32_t bottom = top + h;
    int32_t view_left = camera_x - margin_x;
    int32_t view_top = -margin_y;
    int32_t view_right = camera_x + view_w + margin_x;
    int32_t view_bottom = view_h + margin_y;
    return left < view_right && right > view_left && top < view_bottom && bottom > view_top;
}

static bool lgfx_tilemap_is_solid(const uint8_t *tilemap, int32_t map_w, int32_t map_h, int32_t tx, int32_t ty) {
    if (!tilemap || tx < 0 || ty < 0 || tx >= map_w || ty >= map_h) {
        return false;
    }
    return tilemap[(size_t)ty * (size_t)map_w + (size_t)tx] != 0u;
}

static bool lgfx_aabb_collides_tilemap(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    int32_t x,
    int32_t y,
    int32_t w,
    int32_t h
) {
    if (!tilemap || map_w <= 0 || map_h <= 0 || tile_size <= 0 || w <= 0 || h <= 0) {
        return false;
    }
    int32_t left = x / tile_size;
    int32_t right = (x + w - 1) / tile_size;
    int32_t top = y / tile_size;
    int32_t bottom = (y + h - 1) / tile_size;
    if (x < 0 && (x % tile_size)) {
        left -= 1;
    }
    if (y < 0 && (y % tile_size)) {
        top -= 1;
    }
    for (int32_t ty = top; ty <= bottom; ++ty) {
        for (int32_t tx = left; tx <= right; ++tx) {
            if (lgfx_tilemap_is_solid(tilemap, map_w, map_h, tx, ty)) {
                return true;
            }
        }
    }
    return false;
}

static bool lgfx_aabb_collides_solids(
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph
) {
    if (!solids || solid_stride < 8 || solid_count <= 0 || pw <= 0 || ph <= 0) {
        return false;
    }
    int32_t p_right = px + pw;
    int32_t p_bottom = py + ph;
    for (int32_t i = 0; i < solid_count; ++i) {
        const uint8_t *sb = solids + ((size_t)i * (size_t)solid_stride);
        int32_t ox = lgfx_rd_i16(sb + 0);
        int32_t oy = lgfx_rd_i16(sb + 2);
        int32_t ow = lgfx_rd_i16(sb + 4);
        int32_t oh = lgfx_rd_i16(sb + 6);
        if (ow <= 0 || oh <= 0) {
            continue;
        }
        if (px < (ox + ow) && p_right > ox && py < (oy + oh) && p_bottom > oy) {
            return true;
        }
    }
    return false;
}

static bool lgfx_aabb_collides_world(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph
) {
    if (lgfx_aabb_collides_tilemap(tilemap, map_w, map_h, tile_size, px, py, pw, ph)) {
        return true;
    }
    if (lgfx_aabb_collides_solids(solids, solid_stride, solid_count, px, py, pw, ph)) {
        return true;
    }
    return false;
}

static void lgfx_move_axis_world(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t px,
    int32_t py,
    int32_t pw,
    int32_t ph,
    int32_t dx,
    int32_t dy,
    int32_t *out_x,
    int32_t *out_y,
    bool *hit_x,
    bool *hit_y
) {
    bool local_hit_x = false;
    bool local_hit_y = false;
    int32_t nx = px;
    int32_t ny = py;
    int32_t sx = (dx > 0) ? 1 : -1;
    int32_t sy = (dy > 0) ? 1 : -1;
    int32_t ax = (dx >= 0) ? dx : -dx;
    int32_t ay = (dy >= 0) ? dy : -dy;

    while (ax > 0) {
        int32_t tx = nx + sx;
        if (lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, tx, ny, pw, ph)) {
            local_hit_x = true;
            break;
        }
        nx = tx;
        ax -= 1;
    }
    while (ay > 0) {
        int32_t ty = ny + sy;
        if (lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, nx, ty, pw, ph)) {
            local_hit_y = true;
            break;
        }
        ny = ty;
        ay -= 1;
    }

    *out_x = nx;
    *out_y = ny;
    *hit_x = local_hit_x;
    *hit_y = local_hit_y;
}

static bool lgfx_enemy_has_support_ahead(
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count,
    int32_t wx,
    int32_t wy,
    int32_t ow,
    int32_t oh,
    int32_t direction,
    int32_t step_px
) {
    int32_t step = step_px < 1 ? 1 : step_px;
    int32_t probe_x = (direction >= 0) ? (wx + ow + step - 2) : (wx - step);
    int32_t probe_y = wy + oh + 1;
    return lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, probe_x, probe_y, 2, 2);
}

static void lgfx_reset_enemy_state(uint8_t *state, const uint8_t *row) {
    state[0] = (row && row[10]) ? 1u : 0u;
    state[1] = 0u;
    lgfx_wr_i16(state + 2, 0);
    lgfx_wr_i16(state + 4, 0);
    state[6] = 0u;
    state[7] = 0u;
}

static int32_t lgfx_find_enemy_bullet_spawn_y(
    int32_t desired_y,
    int32_t fallback_y,
    int32_t bullet_x,
    int32_t bullet_w,
    int32_t bullet_h,
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    int32_t tile_size,
    const uint8_t *solids,
    int32_t solid_stride,
    int32_t solid_count
) {
    int32_t probe_y = desired_y;
    int32_t floor_y = fallback_y;
    if (probe_y < floor_y) {
        floor_y = probe_y;
    }
    while (probe_y >= floor_y) {
        if (!lgfx_aabb_collides_world(tilemap, map_w, map_h, tile_size, solids, solid_stride, solid_count, bullet_x, probe_y, bullet_w, bullet_h)) {
            return probe_y;
        }
        probe_y -= 1;
    }
    return fallback_y;
}

static bool lgfx_spawn_enemy_bullet(
    uint8_t *bullet_buf,
    int32_t bullet_stride,
    int32_t bullet_count,
    int32_t bullet_x,
    int32_t bullet_y,
    int32_t vel_x,
    int32_t vel_y,
    int32_t bullet_w,
    int32_t bullet_h,
    int32_t shooter_enemy_i
) {
    if (!bullet_buf || bullet_stride < 16 || bullet_count <= 0 || bullet_w <= 0 || bullet_h <= 0) {
        return false;
    }
    for (int32_t i = 0; i < bullet_count; ++i) {
        uint8_t *bb = bullet_buf + ((size_t)i * (size_t)bullet_stride);
        if (lgfx_rd_i16(bb + 12) == 0) {
            lgfx_wr_i16(bb + 0, bullet_x);
            lgfx_wr_i16(bb + 2, bullet_y);
            lgfx_wr_i16(bb + 4, vel_x);
            lgfx_wr_i16(bb + 6, vel_y);
            lgfx_wr_i16(bb + 8, bullet_w);
            lgfx_wr_i16(bb + 10, bullet_h);
            lgfx_wr_i16(bb + 12, 1);
            lgfx_wr_i16(bb + 14, shooter_enemy_i);
            return true;
        }
    }
    return false;
}

static int32_t lgfx_pick_enemy_hit_by_bullet(
    uint8_t *enemy_rows,
    int32_t enemy_row_stride,
    int32_t enemy_count,
    int32_t bx,
    int32_t by,
    int32_t bw,
    int32_t bh,
    int32_t ignore_enemy_i
) {
    if (!enemy_rows || enemy_row_stride < 12 || enemy_count <= 0) {
        return -1;
    }
    for (int32_t i = 0; i < enemy_count; ++i) {
        if (i == ignore_enemy_i) {
            continue;
        }
        uint8_t *row = enemy_rows + ((size_t)i * (size_t)enemy_row_stride);
        if (!row[8]) {
            continue;
        }
        int32_t ex = lgfx_rd_i16(row + 0);
        int32_t ey = lgfx_rd_i16(row + 2);
        int32_t ew = lgfx_rd_i16(row + 4);
        int32_t eh = lgfx_rd_i16(row + 6);
        if (ew <= 0 || eh <= 0) {
            continue;
        }
        if (bx < (ex + ew) && (bx + bw) > ex && by < (ey + eh) && (by + bh) > ey) {
            return i;
        }
    }
    return -1;
}

static mp_obj_t lgfx_update_enemies_native(size_t n_args, const mp_obj_t *args) {
    if (n_args != 44) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 44 args"));
    }

    mp_buffer_info_t enemy_rows_info;
    mp_buffer_info_t enemy_states_info;
    mp_buffer_info_t monk_hover_info;
    mp_buffer_info_t bullet_info;
    mp_buffer_info_t tilemap_info;
    mp_buffer_info_t solids_info;
    mp_get_buffer_raise(args[0], &enemy_rows_info, MP_BUFFER_RW);
    mp_int_t enemy_row_stride = mp_obj_get_int(args[1]);
    mp_get_buffer_raise(args[2], &enemy_states_info, MP_BUFFER_RW);
    mp_int_t enemy_state_stride = mp_obj_get_int(args[3]);
    mp_int_t enemy_count = mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &monk_hover_info, MP_BUFFER_RW);
    mp_int_t monk_hover_stride = mp_obj_get_int(args[6]);
    mp_int_t monk_hover_count = mp_obj_get_int(args[7]);
    mp_get_buffer_raise(args[8], &bullet_info, MP_BUFFER_RW);
    mp_int_t bullet_stride = mp_obj_get_int(args[9]);
    mp_int_t bullet_count = mp_obj_get_int(args[10]);
    mp_int_t player_x = mp_obj_get_int(args[11]);
    mp_int_t player_y = mp_obj_get_int(args[12]);
    mp_int_t player_w = mp_obj_get_int(args[13]);
    mp_int_t player_h = mp_obj_get_int(args[14]);
    mp_int_t vel_y = mp_obj_get_int(args[15]);
    mp_get_buffer_raise(args[16], &tilemap_info, MP_BUFFER_READ);
    mp_int_t tilemap_w = mp_obj_get_int(args[17]);
    mp_int_t tilemap_h = mp_obj_get_int(args[18]);
    mp_int_t tile_size = mp_obj_get_int(args[19]);
    mp_get_buffer_raise(args[20], &solids_info, MP_BUFFER_READ);
    mp_int_t solid_stride = mp_obj_get_int(args[21]);
    mp_int_t solid_count = mp_obj_get_int(args[22]);
    mp_int_t death_margin = mp_obj_get_int(args[23]);
    mp_int_t enemy_detect_x = mp_obj_get_int(args[24]);
    mp_int_t enemy_flee_x = mp_obj_get_int(args[25]);
    mp_int_t enemy_detect_y = mp_obj_get_int(args[26]);
    mp_int_t enemy_move_speed = mp_obj_get_int(args[27]);
    mp_int_t enemy_gravity_step = mp_obj_get_int(args[28]);
    mp_int_t enemy_frame_hold = mp_obj_get_int(args[29]);
    mp_int_t enemy_shoot_fire_frame = mp_obj_get_int(args[30]);
    mp_int_t enemy_bullet_speed = mp_obj_get_int(args[31]);
    mp_int_t enemy_bullet_w = mp_obj_get_int(args[32]);
    mp_int_t enemy_bullet_h = mp_obj_get_int(args[33]);
    mp_int_t enemy_shoot_interval = mp_obj_get_int(args[34]);
    mp_int_t fall_speed_max = mp_obj_get_int(args[35]);
    mp_int_t map_w_px = mp_obj_get_int(args[36]);
    mp_int_t map_h_px = mp_obj_get_int(args[37]);
    mp_int_t camera_x = mp_obj_get_int(args[38]);
    mp_int_t screen_w = mp_obj_get_int(args[39]);
    mp_int_t screen_h = mp_obj_get_int(args[40]);
    mp_int_t enemy_update_margin_x = mp_obj_get_int(args[41]);
    mp_int_t enemy_update_margin_y = mp_obj_get_int(args[42]);
    mp_int_t enemy_bullet_cull_margin = mp_obj_get_int(args[43]);

    if (enemy_row_stride < 12 || enemy_state_stride < 8 || monk_hover_stride < 11 || bullet_stride < 16) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid stride"));
    }
    if (enemy_count < 0 || bullet_count < 0 || tilemap_w <= 0 || tilemap_h <= 0 || tile_size <= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }
    if (enemy_rows_info.len < (size_t)enemy_row_stride * (size_t)enemy_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy rows buf too small"));
    }
    if (enemy_states_info.len < (size_t)enemy_state_stride * (size_t)enemy_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy states buf too small"));
    }
    if (monk_hover_info.len < (size_t)monk_hover_stride * (size_t)monk_hover_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("monk hover buf too small"));
    }
    if (bullet_info.len < (size_t)bullet_stride * (size_t)bullet_count) {
        mp_raise_ValueError(MP_ERROR_TEXT("enemy bullets buf too small"));
    }
    if (tilemap_info.len < (size_t)tilemap_w * (size_t)tilemap_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("tilemap buf too small"));
    }
    if (solid_count > 0 && (solid_stride < 8 || solids_info.len < (size_t)solid_stride * (size_t)solid_count)) {
        mp_raise_ValueError(MP_ERROR_TEXT("solid buf too small"));
    }

    uint8_t *enemy_rows = (uint8_t *)enemy_rows_info.buf;
    uint8_t *enemy_states = (uint8_t *)enemy_states_info.buf;
    uint8_t *monk_hover = (uint8_t *)monk_hover_info.buf;
    uint8_t *bullet_buf = (uint8_t *)bullet_info.buf;
    const uint8_t *tilemap = (const uint8_t *)tilemap_info.buf;
    const uint8_t *solids = (const uint8_t *)solids_info.buf;

    int32_t player_center_x = player_x + (player_w / 2);
    int32_t player_center_y = player_y + (player_h / 2);
    int32_t shoot_anim_total = 10 * enemy_frame_hold;
    int32_t shoot_fire_tick = enemy_shoot_fire_frame * enemy_frame_hold;
    static const int32_t monk_hover_min_x = 1616;
    static const int32_t monk_hover_max_x = 1887;
    static const int32_t monk_hover_min_y = 32;
    static const int32_t monk_hover_max_y = 111;
    static const int32_t monk_hover_target_eps = 12;
    static const int32_t monk_hover_reached_eps = 1;
    static const int32_t monk_hover_phase_step = 2;
    static const int32_t monk_hover_retarget_frames = 30;
    static const int32_t monk_hover_wave_amp_x = 3;
    static const int32_t monk_hover_wave_amp_y = 2;
    static const uint8_t monk_hover_state_moving = 0xFF;
    if (shoot_fire_tick < 1) {
        shoot_fire_tick = enemy_frame_hold < 1 ? 1 : enemy_frame_hold;
    }

    for (int32_t ei = 0; ei < enemy_count; ++ei) {
        uint8_t *row = enemy_rows + ((size_t)ei * (size_t)enemy_row_stride);
        uint8_t *state = enemy_states + ((size_t)ei * (size_t)enemy_state_stride);
        int32_t wx = lgfx_rd_i16(row + 0);
        int32_t wy = lgfx_rd_i16(row + 2);
        int32_t ew = lgfx_rd_i16(row + 4);
        int32_t eh = lgfx_rd_i16(row + 6);
        int32_t visible = row[8] ? 1 : 0;
        if (!visible || ew <= 0 || eh <= 0) {
            continue;
        }

        int32_t state_code = state[1];
        int32_t facing_enemy = state[0] ? 1 : -1;
        int32_t vel_enemy_y = (int32_t)(int8_t)state[7];
        int32_t shoot_cooldown = lgfx_rd_i16(state + 4);
        bool static_enemy = row[11] != 0;
        int32_t enemy_center_x = wx + (ew / 2);
        int32_t enemy_center_y = wy + (eh / 2);
        int32_t dx_to_player = player_center_x - enemy_center_x;
        int32_t dy_to_player = player_center_y - enemy_center_y;
        bool near_player_x = (dx_to_player >= 0) ? (dx_to_player <= (enemy_detect_x + enemy_update_margin_x)) : ((-dx_to_player) <= (enemy_detect_x + enemy_update_margin_x));
        bool near_player_y = (dy_to_player >= 0) ? (dy_to_player <= (enemy_detect_y + enemy_update_margin_y)) : ((-dy_to_player) <= (enemy_detect_y + enemy_update_margin_y));
        if (!(lgfx_aabb_near_view(wx, wy, ew, eh, camera_x, screen_w, screen_h, enemy_update_margin_x, enemy_update_margin_y) || (near_player_x && near_player_y))) {
            continue;
        }
        if (shoot_cooldown > 0) {
            shoot_cooldown -= 1;
        }
        if (static_enemy) {
            uint8_t *hover = nullptr;
            if (ei < monk_hover_count) {
                hover = monk_hover + ((size_t)ei * (size_t)monk_hover_stride);
            }
            int32_t next_anim_counter = lgfx_rd_i16(state + 2) + 1;
            if (next_anim_counter > 30000) {
                next_anim_counter = 0;
            }
            int32_t hover_target_x = wx;
            int32_t hover_target_y = wy;
            int32_t hover_phase = 0;
            int32_t hover_retarget_cd = 0;
            int32_t hover_speed_q8 = 256;
            if (hover != nullptr) {
                hover_target_x = lgfx_rd_i16(hover + 0);
                hover_target_y = lgfx_rd_i16(hover + 2);
                hover_phase = (uint16_t)hover[6] | ((uint16_t)hover[7] << 8);
                hover_retarget_cd = hover[8];
                hover_speed_q8 = lgfx_rd_i16(hover + 9);
                if (hover_speed_q8 <= 0) {
                    hover_speed_q8 = 256;
                }
            }
            if (hover_retarget_cd != monk_hover_state_moving && hover_retarget_cd > 0) {
                hover_retarget_cd -= 1;
            }
            int32_t dx_target = hover_target_x - wx;
            int32_t dy_target = hover_target_y - wy;
            int32_t abs_dx_target = (dx_target >= 0) ? dx_target : -dx_target;
            int32_t abs_dy_target = (dy_target >= 0) ? dy_target : -dy_target;
            bool at_target = (abs_dx_target <= monk_hover_reached_eps) && (abs_dy_target <= monk_hover_reached_eps);
            if (!at_target && hover_retarget_cd != monk_hover_state_moving) {
                hover_retarget_cd = monk_hover_state_moving;
            }
            if (at_target) {
                wx = hover_target_x;
                wy = hover_target_y;
                if (hover_retarget_cd == monk_hover_state_moving) {
                    hover_retarget_cd = (uint8_t)monk_hover_retarget_frames;
                } else if (hover_retarget_cd <= 0) {
                    uint32_t seed = (uint32_t)(hover_phase + (ei * 131u) + (uint32_t)wx + 17u);
                    seed = (seed * 1103515245u) + 12345u;
                    int32_t target_min_x = monk_hover_min_x;
                    int32_t target_max_x = monk_hover_max_x - ew;
                    if (target_max_x < target_min_x) {
                        target_max_x = target_min_x;
                    }
                    int32_t span = target_max_x - target_min_x;
                    if (span < 0) {
                        span = 0;
                    }
                    hover_target_x = target_min_x + (int32_t)(seed % (uint32_t)(span + 1));
                    seed = (seed * 1103515245u) + 12345u;
                    int32_t target_min_y = monk_hover_min_y;
                    int32_t target_max_y = monk_hover_max_y;
                    if (target_max_y < target_min_y) {
                        target_max_y = target_min_y;
                    }
                    span = target_max_y - target_min_y;
                    if (span < 0) {
                        span = 0;
                    }
                    hover_target_y = target_min_y + (int32_t)(seed % (uint32_t)(span + 1));
                    hover_retarget_cd = monk_hover_state_moving;
                    dx_target = hover_target_x - wx;
                    dy_target = hover_target_y - wy;
                    at_target = false;
                }
            }
            if (!at_target && hover_retarget_cd == monk_hover_state_moving) {
                int32_t step_x = 0;
                if (dx_target != 0) {
                    step_x = (hover_speed_q8 + 128) / 256;
                    if (step_x < 1) {
                        step_x = 1;
                    }
                    if (dx_target > 0) {
                        wx += (dx_target < step_x) ? dx_target : step_x;
                        facing_enemy = 1;
                    } else {
                        int32_t mag = (-dx_target < step_x) ? -dx_target : step_x;
                        wx -= mag;
                        facing_enemy = -1;
                    }
                }
                int32_t step_y = (hover_speed_q8 + 128) / 256;
                if (step_y < 1) {
                    step_y = 1;
                }
                if (dy_target > 0) {
                    wy += (dy_target < step_y) ? dy_target : step_y;
                } else if (dy_target < 0) {
                    int32_t mag_y = (-dy_target < step_y) ? -dy_target : step_y;
                    wy -= mag_y;
                }
            }
            hover_phase = (hover_phase + monk_hover_phase_step) & 0xFFFF;
            int32_t max_enemy_x_hover = map_w_px - ew;
            if (max_enemy_x_hover < 0) {
                max_enemy_x_hover = 0;
            }
            wx = lgfx_clamp_i32(wx, 0, max_enemy_x_hover);
            wy = lgfx_clamp_i32(wy, monk_hover_min_y, monk_hover_max_y);
            if (wy < 0) {
                wy = 0;
            }
            lgfx_wr_i16(row + 0, wx);
            lgfx_wr_i16(row + 2, wy);
            if (hover != nullptr) {
                lgfx_wr_i16(hover + 0, hover_target_x);
                lgfx_wr_i16(hover + 2, hover_target_y);
                lgfx_wr_i16(hover + 4, hover_target_y);
                lgfx_wr_i16(hover + 6, hover_phase);
                hover[8] = (uint8_t)(hover_retarget_cd & 0xFF);
                lgfx_wr_i16(hover + 9, hover_speed_q8);
            }
            if (ei == 2 && (next_anim_counter % 30) == 0) {
                mp_printf(&mp_plat_print, "MONK_HOVER_DBG wx=%d wy=%d tx=%d ty=%d speed=%d cd=%d phase=%d\n",
                    (int)wx,
                    (int)wy,
                    (int)hover_target_x,
                    (int)hover_target_y,
                    (int)hover_speed_q8,
                    (int)hover_retarget_cd,
                    (int)hover_phase);
            }
            state[0] = (facing_enemy >= 0) ? 1u : 0u;
            state[1] = 0u;
            lgfx_wr_i16(state + 2, next_anim_counter);
            lgfx_wr_i16(state + 4, 0);
            state[6] = 0u;
            state[7] = 0u;
            continue;
        }

        bool detect_player = (dx_to_player >= 0) ? (dx_to_player <= enemy_detect_x) : ((-dx_to_player) <= enemy_detect_x);
        if (detect_player) {
            detect_player = (dy_to_player >= 0) ? (dy_to_player <= enemy_detect_y) : ((-dy_to_player) <= enemy_detect_y);
        }
        bool flee_player = false;
        if (detect_player) {
            flee_player = (dx_to_player >= 0) ? (dx_to_player <= enemy_flee_x) : ((-dx_to_player) <= enemy_flee_x);
        }
        int32_t aim_dir = (dx_to_player >= 0) ? 1 : -1;
        int32_t move_enemy_x = 0;
        if (state_code == 2) {
            facing_enemy = aim_dir;
        } else if (flee_player) {
            int32_t flee_dir = (dx_to_player >= 0) ? -1 : 1;
            if (lgfx_enemy_has_support_ahead(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, wx, wy, ew, eh, flee_dir, enemy_move_speed)) {
                if (state_code != 1 || ((state[0] ? 1 : -1) != flee_dir)) {
                    lgfx_wr_i16(state + 2, 0);
                }
                facing_enemy = flee_dir;
                state_code = 1;
                move_enemy_x = flee_dir * enemy_move_speed;
            } else if (shoot_cooldown <= 0) {
                if (state_code != 2 || facing_enemy != aim_dir) {
                    lgfx_wr_i16(state + 2, 0);
                    state[6] = 0u;
                }
                facing_enemy = aim_dir;
                state_code = 2;
            } else {
                facing_enemy = aim_dir;
                state_code = 0;
            }
        } else if (detect_player) {
            facing_enemy = aim_dir;
            if (shoot_cooldown <= 0) {
                if (state_code != 2) {
                    if (((state[0] ? 1 : -1)) != facing_enemy) {
                        lgfx_wr_i16(state + 2, 0);
                    }
                    state[6] = 0u;
                }
                state_code = 2;
            } else {
                if (((state[0] ? 1 : -1)) != facing_enemy) {
                    lgfx_wr_i16(state + 2, 0);
                }
                state_code = 0;
            }
        } else {
            state_code = 0;
        }

        bool grounded_enemy = lgfx_aabb_collides_world(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, wx, wy + 1, ew, eh);
        if (!grounded_enemy) {
            vel_enemy_y += enemy_gravity_step;
            if (vel_enemy_y > fall_speed_max) {
                vel_enemy_y = fall_speed_max;
            }
        } else if (vel_enemy_y > 0) {
            vel_enemy_y = 0;
        }

        bool enemy_hit_x = false;
        bool enemy_hit_y = false;
        int32_t moved_x = wx;
        int32_t moved_y = wy;
        lgfx_move_axis_world(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, wx, wy, ew, eh, move_enemy_x, vel_enemy_y, &moved_x, &moved_y, &enemy_hit_x, &enemy_hit_y);
        int32_t max_enemy_x = map_w_px - ew;
        if (max_enemy_x < 0) {
            max_enemy_x = 0;
        }
        moved_x = lgfx_clamp_i32(moved_x, 0, max_enemy_x);
        if (enemy_hit_y) {
            vel_enemy_y = 0;
        }
        if (moved_y < 0) {
            moved_y = 0;
            vel_enemy_y = 0;
        }
        if (moved_y > (map_h_px + death_margin)) {
            lgfx_wr_i16(row + 2, moved_y);
            row[8] = 0u;
            lgfx_reset_enemy_state(state, row);
        } else {
            lgfx_wr_i16(row + 0, moved_x);
            lgfx_wr_i16(row + 2, moved_y);
            state[0] = (facing_enemy >= 0) ? 1u : 0u;
            state[1] = (uint8_t)(state_code & 0xFF);
            lgfx_wr_i16(state + 4, shoot_cooldown);
            state[7] = (uint8_t)((int8_t)vel_enemy_y);
            if (state_code == 1) {
                lgfx_wr_i16(state + 2, lgfx_rd_i16(state + 2) + 1);
                state[6] = 0u;
            } else if (state_code == 2) {
                int32_t anim_counter = lgfx_rd_i16(state + 2) + 1;
                lgfx_wr_i16(state + 2, anim_counter);
                if (!state[6] && anim_counter >= shoot_fire_tick) {
                    int32_t bullet_vx = enemy_bullet_speed * facing_enemy;
                    int32_t bullet_x = moved_x + ((ew - enemy_bullet_w) / 2);
                    if (facing_enemy >= 0) {
                        bullet_x = moved_x + ew;
                    } else {
                        bullet_x = moved_x - enemy_bullet_w;
                    }
                    // Fire from the lower half of the enemy body: for a 32px enemy and
                    // 16px bullet, this anchors the bullet top at enemy_y + 16.
                    int32_t bullet_base_y = moved_y + (eh / 2);
                    int32_t bullet_y = lgfx_find_enemy_bullet_spawn_y(
                        bullet_base_y,
                        bullet_base_y,
                        bullet_x,
                        enemy_bullet_w,
                        enemy_bullet_h,
                        tilemap,
                        tilemap_w,
                        tilemap_h,
                        tile_size,
                        solids,
                        solid_stride,
                        solid_count
                    );
                    lgfx_spawn_enemy_bullet(bullet_buf, bullet_stride, bullet_count, bullet_x, bullet_y, bullet_vx, 0, enemy_bullet_w, enemy_bullet_h, ei);
                    state[6] = 1u;
                }
                if (lgfx_rd_i16(state + 2) >= shoot_anim_total) {
                    lgfx_wr_i16(state + 2, 0);
                    state[6] = 0u;
                    state[1] = 0u;
                    lgfx_wr_i16(state + 4, enemy_shoot_interval);
                }
            } else {
                lgfx_wr_i16(state + 2, 0);
                state[6] = 0u;
            }
        }
    }

    for (int32_t bi = 0; bi < bullet_count; ++bi) {
        uint8_t *bullet = bullet_buf + ((size_t)bi * (size_t)bullet_stride);
        if (lgfx_rd_i16(bullet + 12) == 0) {
            continue;
        }
        int32_t bx = lgfx_rd_i16(bullet + 0) + lgfx_rd_i16(bullet + 4);
        int32_t by = lgfx_rd_i16(bullet + 2) + lgfx_rd_i16(bullet + 6);
        int32_t bw = lgfx_rd_i16(bullet + 8);
        int32_t bh = lgfx_rd_i16(bullet + 10);
        int32_t shooter_enemy_i = lgfx_rd_i16(bullet + 14);
        bool active = true;
        if ((bx + bw) < 0 || bx > map_w_px || by > (map_h_px + death_margin)) {
            active = false;
        } else if (!lgfx_aabb_near_view(bx, by, bw, bh, camera_x, screen_w, screen_h, enemy_bullet_cull_margin, enemy_bullet_cull_margin)) {
            active = false;
        } else if (lgfx_aabb_collides_world(tilemap, tilemap_w, tilemap_h, tile_size, solids, solid_stride, solid_count, bx, by, bw, bh)) {
            active = false;
        } else {
            int32_t hit_enemy_i = lgfx_pick_enemy_hit_by_bullet(enemy_rows, enemy_row_stride, enemy_count, bx, by, bw, bh, shooter_enemy_i);
            if (hit_enemy_i >= 0) {
                active = false;
                uint8_t *enemy_row = enemy_rows + ((size_t)hit_enemy_i * (size_t)enemy_row_stride);
                uint8_t *enemy_state = enemy_states + ((size_t)hit_enemy_i * (size_t)enemy_state_stride);
                enemy_row[8] = 0u;
                lgfx_reset_enemy_state(enemy_state, enemy_row);
            }
        }
        if (active && player_x < (bx + bw) && (player_x + player_w) > bx && player_y < (by + bh) && (player_y + player_h) > by) {
            active = false;
            player_y = map_h_px + death_margin + 1;
            vel_y = 0;
        }
        if (active) {
            lgfx_wr_i16(bullet + 0, bx);
            lgfx_wr_i16(bullet + 2, by);
        } else {
            lgfx_wr_i16(bullet + 12, 0);
        }
    }

    mp_obj_t out[2] = {
        mp_obj_new_int(player_y),
        mp_obj_new_int(vel_y),
    };
    return mp_obj_new_tuple(2, out);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_update_enemies_native_obj, 44, 44, lgfx_update_enemies_native);

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
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait), MP_ROM_PTR(&lgfx_blit_rect565_wait_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_wait), MP_ROM_PTR(&lgfx_blit_rect565_wire_wait_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_async), MP_ROM_PTR(&lgfx_blit_rect565_async_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_async), MP_ROM_PTR(&lgfx_blit_rect565_wire_async_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit_wait_done), MP_ROM_PTR(&lgfx_blit_wait_done_obj) },
    { MP_ROM_QSTR(MP_QSTR_async_probe_rgb565), MP_ROM_PTR(&lgfx_async_probe_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_submit_probe_rgb565), MP_ROM_PTR(&lgfx_submit_probe_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_band_submit_probe_rgb565), MP_ROM_PTR(&lgfx_band_submit_probe_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_band_pipeline_tail_wait), MP_ROM_PTR(&lgfx_band_pipeline_tail_wait_obj) },
    { MP_ROM_QSTR(MP_QSTR_render_scene_bands_rgb565), MP_ROM_PTR(&lgfx_render_scene_bands_rgb565_obj) },
    { MP_ROM_QSTR(MP_QSTR_update_enemies_native), MP_ROM_PTR(&lgfx_update_enemies_native_obj) },
    { MP_ROM_QSTR(MP_QSTR_update_monk_intro_native), MP_ROM_PTR(&lgfx_update_monk_intro_native_obj) },
    { MP_ROM_QSTR(MP_QSTR_update_monk_orbs_native), MP_ROM_PTR(&lgfx_update_monk_orbs_native_obj) },
    { MP_ROM_QSTR(MP_QSTR_pack_monk_orb_descriptors_native), MP_ROM_PTR(&lgfx_pack_monk_orb_descriptors_native_obj) },
    { MP_ROM_QSTR(MP_QSTR_pick_swappable_monk_orb_native), MP_ROM_PTR(&lgfx_pick_swappable_monk_orb_native_obj) },
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
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wait), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_wait), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_async), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_rect565_wire_async), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_blit_wait_done), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_async_probe_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_submit_probe_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_band_submit_probe_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_band_pipeline_tail_wait), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_render_scene_bands_rgb565), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_update_enemies_native), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_update_monk_intro_native), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_update_monk_orbs_native), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_pack_monk_orb_descriptors_native), MP_ROM_INT(0) },
    { MP_ROM_QSTR(MP_QSTR_pick_swappable_monk_orb_native), MP_ROM_INT(0) },
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
