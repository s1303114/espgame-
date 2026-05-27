#if !defined(NO_QSTR)

#include <stdint.h>
#include "esp_cache.h"
#include "esp_timer.h"

extern "C" {
#include "py/obj.h"
#include "py/runtime.h"
}

#include "lgfx_shared.hpp"


static void copy_far_band(uint8_t *dst, int32_t dst_w, int32_t band_y, int32_t band_h, const uint8_t *far) {
    size_t row_bytes = (size_t)dst_w * 2u;
    for (int32_t y = 0; y < band_h; ++y) {
        memcpy(dst + ((size_t)y * row_bytes), far + (((size_t)(band_y + y) * (size_t)dst_w) * 2u), row_bytes);
    }
}

static void compose_tilemap_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    const uint8_t *tileset,
    size_t tileset_len,
    int32_t tile_size,
    int32_t tileset_w,
    int32_t transparent_key
) {
    if (!tilemap || !tileset || dst_w <= 0 || dst_h <= 0 || map_w <= 0 || map_h <= 0 || tile_size <= 0 || tileset_w <= 0) {
        return;
    }
    size_t tile_bytes = (size_t)tile_size * (size_t)tile_size * 2u;
    size_t tile_count = tile_bytes ? (tileset_len / tile_bytes) : 0u;
    size_t tileset_cols = (size_t)tileset_w / (size_t)tile_size;
    if (tile_count == 0 || tileset_cols == 0) {
        return;
    }

    int32_t start_col = camera_x / tile_size;
    int32_t end_col = (camera_x + dst_w - 1) / tile_size;
    int32_t start_row = band_top / tile_size;
    int32_t end_row = (band_top + dst_h - 1) / tile_size;
    if (start_col < 0) start_col = 0;
    if (start_row < 0) start_row = 0;
    if (end_col >= map_w) end_col = map_w - 1;
    if (end_row >= map_h) end_row = map_h - 1;
    if (end_col < start_col || end_row < start_row) return;

    for (int32_t r = start_row; r <= end_row; ++r) {
        const uint8_t *map_row = tilemap + ((size_t)r * (size_t)map_w);
        for (int32_t c = start_col; c <= end_col; ++c) {
            uint8_t tid = map_row[c];
            if (tid == 0u) continue;
            size_t tile_idx = (size_t)tid - 1u;
            if (tile_idx >= tile_count) continue;

            int32_t dx = (c * tile_size) - camera_x;
            int32_t dy = (r * tile_size) - band_top;
            int32_t src_x0 = 0;
            int32_t src_y0 = 0;
            int32_t vis_w = tile_size;
            int32_t vis_h = tile_size;
            if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
            if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
            if (dx + vis_w > dst_w) vis_w = dst_w - dx;
            if (dy + vis_h > dst_h) vis_h = dst_h - dy;
            if (vis_w <= 0 || vis_h <= 0) continue;

            size_t atlas_col = tile_idx % tileset_cols;
            size_t atlas_row = tile_idx / tileset_cols;
            size_t tile_px_x = atlas_col * (size_t)tile_size;
            size_t tile_px_y = atlas_row * (size_t)tile_size;
            size_t src_row_base = ((tile_px_y + (size_t)src_y0) * (size_t)tileset_w + tile_px_x + (size_t)src_x0) * 2u;
            size_t src_stride = (size_t)tileset_w * 2u;
            size_t copy_bytes = (size_t)vis_w * 2u;
            for (int32_t y = 0; y < vis_h; ++y) {
                const uint8_t *src_row = tileset + src_row_base + ((size_t)y * src_stride);
                uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
                if (transparent_key < 0) {
                    memcpy(dst_row, src_row, copy_bytes);
                } else {
                    for (int32_t x = 0; x < vis_w; ++x) {
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
}

static void compose_objects_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *objbuf,
    int32_t obj_stride,
    int32_t object_count,
    const uint8_t *atlas,
    int32_t atlas_w,
    int32_t atlas_h,
    int32_t transparent_key
) {
    if (!objbuf || !atlas || object_count <= 0 || obj_stride < 12 || atlas_w <= 0 || atlas_h <= 0) return;
    size_t atlas_row_bytes = (size_t)atlas_w * 2u;
    for (int32_t i = 0; i < object_count; ++i) {
        const uint8_t *ob = objbuf + ((size_t)i * (size_t)obj_stride);
        int16_t wx = (int16_t)((uint16_t)ob[0] | ((uint16_t)ob[1] << 8));
        int16_t wy = (int16_t)((uint16_t)ob[2] | ((uint16_t)ob[3] << 8));
        int32_t src_x = (uint16_t)ob[4] | ((uint16_t)ob[5] << 8);
        int32_t src_y = (uint16_t)ob[6] | ((uint16_t)ob[7] << 8);
        int32_t src_w = (uint16_t)ob[8] | ((uint16_t)ob[9] << 8);
        int32_t src_h = (uint16_t)ob[10] | ((uint16_t)ob[11] << 8);
        if (src_w <= 0 || src_h <= 0) continue;
        if (src_x < 0 || src_y < 0 || src_x + src_w > atlas_w || src_y + src_h > atlas_h) continue;

        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        int32_t src_x0 = 0;
        int32_t src_y0 = 0;
        int32_t vis_w = src_w;
        int32_t vis_h = src_h;
        if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
        if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
        if (dx + vis_w > dst_w) vis_w = dst_w - dx;
        if (dy + vis_h > dst_h) vis_h = dst_h - dy;
        if (vis_w <= 0 || vis_h <= 0) continue;

        size_t src_row_base = ((size_t)(src_y + src_y0) * (size_t)atlas_w + (size_t)(src_x + src_x0)) * 2u;
        size_t copy_bytes = (size_t)vis_w * 2u;
        for (int32_t y = 0; y < vis_h; ++y) {
            const uint8_t *src_row = atlas + src_row_base + ((size_t)y * atlas_row_bytes);
            uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
            if (transparent_key < 0) {
                memcpy(dst_row, src_row, copy_bytes);
            } else {
                for (int32_t x = 0; x < vis_w; ++x) {
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

static void compose_sprite_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t dst_x,
    int32_t dst_y,
    const uint8_t *src,
    int32_t src_w,
    int32_t src_h,
    int32_t transparent_key
) {
    if (!src || dst_w <= 0 || dst_h <= 0 || src_w <= 0 || src_h <= 0) return;
    if (dst_x >= dst_w || dst_y >= dst_h || (dst_x + src_w) <= 0 || (dst_y + src_h) <= 0) return;
    int32_t src_x0 = 0;
    int32_t src_y0 = 0;
    int32_t dx = dst_x;
    int32_t dy = dst_y;
    int32_t vis_w = src_w;
    int32_t vis_h = src_h;
    if (dx < 0) { src_x0 = -dx; vis_w -= src_x0; dx = 0; }
    if (dy < 0) { src_y0 = -dy; vis_h -= src_y0; dy = 0; }
    if (dx + vis_w > dst_w) vis_w = dst_w - dx;
    if (dy + vis_h > dst_h) vis_h = dst_h - dy;
    if (vis_w <= 0 || vis_h <= 0) return;

    size_t copy_bytes = (size_t)vis_w * 2u;
    for (int32_t y = 0; y < vis_h; ++y) {
        const uint8_t *src_row = src + ((((size_t)(src_y0 + y) * (size_t)src_w) + (size_t)src_x0) * 2u);
        uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
        if (transparent_key < 0) {
            memcpy(dst_row, src_row, copy_bytes);
        } else {
            for (int32_t x = 0; x < vis_w; ++x) {
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

static void compose_scene_band(
    uint8_t *dst,
    int32_t screen_w,
    int32_t band_y,
    int32_t band_h,
    const uint8_t *far,
    int32_t camera_x,
    const uint8_t *tilemap,
    int32_t map_w,
    int32_t map_h,
    const uint8_t *tileset,
    size_t tileset_len,
    int32_t tile_size,
    int32_t tileset_w,
    int32_t tile_key,
    const uint8_t *objbuf,
    int32_t obj_stride,
    int32_t object_count,
    const uint8_t *obj_atlas,
    int32_t obj_atlas_w,
    int32_t obj_atlas_h,
    int32_t object_key,
    const uint8_t *sprite,
    int32_t sprite_w,
    int32_t sprite_h,
    int32_t sprite_x,
    int32_t sprite_y,
    int32_t sprite_key
) {
    copy_far_band(dst, screen_w, band_y, band_h, far);
    compose_tilemap_band(dst, screen_w, band_h, camera_x, band_y, tilemap, map_w, map_h, tileset, tileset_len, tile_size, tileset_w, tile_key);
    compose_objects_band(dst, screen_w, band_h, camera_x, band_y, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key);
    compose_sprite_band(dst, screen_w, band_h, sprite_x, sprite_y - band_y, sprite, sprite_w, sprite_h, sprite_key);
}

static void submit_band_start(uint8_t *buf, int32_t screen_w, int32_t band_y, int32_t band_h, bool *prev_swap, uint32_t *kick_us) {
    size_t len = (size_t)screen_w * (size_t)band_h * 2u;
    int64_t t0 = esp_timer_get_time();
    esp_err_t sync_ret = esp_cache_msync((void *)buf, len, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
    if (sync_ret != ESP_OK) {
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("cache msync failed: %d"), (int)sync_ret);
    }
    *prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(false);
    lcd.pushImageDMA(0, band_y, screen_w, band_h, (const uint16_t *)buf);
    *kick_us += (uint32_t)(esp_timer_get_time() - t0);
}

static void submit_band_wait(bool prev_swap, uint32_t *wait_us) {
    int64_t t0 = esp_timer_get_time();
    lcd.waitDMA();
    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();
    *wait_us += (uint32_t)(esp_timer_get_time() - t0);
}

extern "C" {

static mp_obj_t lgfx_band_submit_probe_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 4) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 4 args"));
    }

    mp_buffer_info_t bufinfo;
    mp_get_buffer_raise(args[0], &bufinfo, MP_BUFFER_READ);
    mp_int_t w = mp_obj_get_int(args[1]);
    mp_int_t h = mp_obj_get_int(args[2]);
    mp_int_t band_h = mp_obj_get_int(args[3]);
    if (w <= 0 || h <= 0 || band_h <= 0 || band_h > h) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }

    size_t full_len = (size_t)w * (size_t)h * 2u;
    if (bufinfo.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("buf too small"));
    }

    const uint8_t *base = (const uint8_t *)bufinfo.buf;
    uint32_t total_kick_us = 0;
    uint32_t total_wait_us = 0;
    uint32_t band_count = 0;
    int64_t all_t0 = esp_timer_get_time();

    mp_printf(&mp_plat_print, "BAND_SUBMIT_PROBE_START w=%d h=%d band_h=%d\n", (int)w, (int)h, (int)band_h);

    int32_t y = 0;
    while (y < h) {
        int32_t bh = (int32_t)band_h;
        if (y + bh > h) {
            bh = h - y;
        }
        size_t band_len = (size_t)w * (size_t)bh * 2u;
        const uint16_t *pixels = (const uint16_t *)(base + ((size_t)y * (size_t)w * 2u));

        bool prev_swap = lcd.getSwapBytes();
        int64_t t0 = esp_timer_get_time();
        esp_err_t sync_ret = esp_cache_msync(
            (void *)pixels,
            band_len,
            ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED
        );
        if (sync_ret != ESP_OK) {
            mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("cache msync failed: %d"), (int)sync_ret);
        }
        lcd.startWrite();
        lcd.setSwapBytes(false);
        lcd.pushImageDMA(0, y, (int32_t)w, bh, pixels);
        int64_t t1 = esp_timer_get_time();
        lcd.waitDMA();
        int64_t t2 = esp_timer_get_time();
        lcd.setSwapBytes(prev_swap);
        lcd.endWrite();

        uint32_t kick_us = (uint32_t)(t1 - t0);
        uint32_t wait_us = (uint32_t)(t2 - t1);
        total_kick_us += kick_us;
        total_wait_us += wait_us;
        mp_printf(
            &mp_plat_print,
            "BAND_SUBMIT_PROBE band=%u y=%d h=%d kick_us=%u wait_us=%u total_us=%u\n",
            (unsigned)band_count,
            (int)y,
            (int)bh,
            (unsigned)kick_us,
            (unsigned)wait_us,
            (unsigned)(kick_us + wait_us)
        );

        ++band_count;
        y += bh;
    }

    uint32_t total_us = (uint32_t)(esp_timer_get_time() - all_t0);
    mp_printf(
        &mp_plat_print,
        "BAND_SUBMIT_PROBE_TOTAL bands=%u kick_us=%u wait_us=%u total_us=%u\n",
        (unsigned)band_count,
        (unsigned)total_kick_us,
        (unsigned)total_wait_us,
        (unsigned)total_us
    );

    mp_obj_t out[4] = {
        mp_obj_new_int_from_uint(band_count),
        mp_obj_new_int_from_uint(total_kick_us),
        mp_obj_new_int_from_uint(total_wait_us),
        mp_obj_new_int_from_uint(total_us),
    };
    return mp_obj_new_tuple(4, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_band_submit_probe_rgb565_obj, 4, 4, lgfx_band_submit_probe_rgb565);


static mp_obj_t lgfx_render_scene_bands_rgb565(size_t n_args, const mp_obj_t *args) {
    if (n_args != 28) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 28 args"));
    }

    mp_buffer_info_t band_a_info, band_b_info, far_info, tilemap_info, tileset_info, obj_info, obj_atlas_info, sprite_info;
    mp_get_buffer_raise(args[0], &band_a_info, MP_BUFFER_RW);
    mp_get_buffer_raise(args[1], &band_b_info, MP_BUFFER_RW);
    int32_t screen_w = (int32_t)mp_obj_get_int(args[2]);
    int32_t screen_h = (int32_t)mp_obj_get_int(args[3]);
    int32_t band_h_cfg = (int32_t)mp_obj_get_int(args[4]);
    mp_get_buffer_raise(args[5], &far_info, MP_BUFFER_READ);
    int32_t camera_x = (int32_t)mp_obj_get_int(args[6]);
    mp_get_buffer_raise(args[7], &tilemap_info, MP_BUFFER_READ);
    int32_t map_w = (int32_t)mp_obj_get_int(args[8]);
    int32_t map_h = (int32_t)mp_obj_get_int(args[9]);
    mp_get_buffer_raise(args[10], &tileset_info, MP_BUFFER_READ);
    int32_t tile_size = (int32_t)mp_obj_get_int(args[11]);
    int32_t tileset_w = (int32_t)mp_obj_get_int(args[12]);
    int32_t tile_key = (int32_t)mp_obj_get_int(args[13]);
    mp_get_buffer_raise(args[14], &obj_info, MP_BUFFER_READ);
    int32_t obj_stride = (int32_t)mp_obj_get_int(args[15]);
    mp_get_buffer_raise(args[16], &obj_atlas_info, MP_BUFFER_READ);
    int32_t obj_atlas_w = (int32_t)mp_obj_get_int(args[17]);
    int32_t obj_atlas_h = (int32_t)mp_obj_get_int(args[18]);
    int32_t object_key = (int32_t)mp_obj_get_int(args[19]);
    int32_t object_count = (int32_t)mp_obj_get_int(args[20]);
    mp_get_buffer_raise(args[21], &sprite_info, MP_BUFFER_READ);
    int32_t sprite_w = (int32_t)mp_obj_get_int(args[22]);
    int32_t sprite_h = (int32_t)mp_obj_get_int(args[23]);
    int32_t sprite_x = (int32_t)mp_obj_get_int(args[24]);
    int32_t sprite_y = (int32_t)mp_obj_get_int(args[25]);
    int32_t sprite_key = (int32_t)mp_obj_get_int(args[26]);
    bool verbose = mp_obj_is_true(args[27]);

    if (screen_w <= 0 || screen_h <= 0 || band_h_cfg <= 0 || band_h_cfg > screen_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid dims"));
    }
    size_t max_band_len = (size_t)screen_w * (size_t)band_h_cfg * 2u;
    size_t full_len = (size_t)screen_w * (size_t)screen_h * 2u;
    if (band_a_info.len < max_band_len || band_b_info.len < max_band_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("band buf too small"));
    }
    if (far_info.len < full_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("far buf too small"));
    }
    if (tilemap_info.len < (size_t)map_w * (size_t)map_h) {
        mp_raise_ValueError(MP_ERROR_TEXT("tilemap buf too small"));
    }
    if (sprite_info.len < (size_t)sprite_w * (size_t)sprite_h * 2u) {
        mp_raise_ValueError(MP_ERROR_TEXT("sprite buf too small"));
    }
    if (object_count > 0) {
        if (obj_stride < 12 || obj_info.len < (size_t)object_count * (size_t)obj_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("object buf too small"));
        }
        if (obj_atlas_info.len < (size_t)obj_atlas_w * (size_t)obj_atlas_h * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("object atlas too small"));
        }
    }

    uint8_t *band_a = (uint8_t *)band_a_info.buf;
    uint8_t *band_b = (uint8_t *)band_b_info.buf;
    const uint8_t *far = (const uint8_t *)far_info.buf;
    const uint8_t *tilemap = (const uint8_t *)tilemap_info.buf;
    const uint8_t *tileset = (const uint8_t *)tileset_info.buf;
    const uint8_t *objbuf = (const uint8_t *)obj_info.buf;
    const uint8_t *obj_atlas = (const uint8_t *)obj_atlas_info.buf;
    const uint8_t *sprite = (const uint8_t *)sprite_info.buf;

    uint32_t compose_us = 0;
    uint32_t kick_us = 0;
    uint32_t wait_us = 0;
    uint32_t bands = 0;
    int64_t all_t0 = esp_timer_get_time();

    int32_t y = 0;
    int32_t bh = band_h_cfg;
    if (y + bh > screen_h) bh = screen_h - y;
    int64_t ct0 = esp_timer_get_time();
    compose_scene_band(band_a, screen_w, y, bh, far, camera_x, tilemap, map_w, map_h, tileset, tileset_info.len, tile_size, tileset_w, tile_key, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key);
    compose_us += (uint32_t)(esp_timer_get_time() - ct0);

    bool prev_swap = false;
    submit_band_start(band_a, screen_w, y, bh, &prev_swap, &kick_us);
    if (verbose) {
        mp_printf(&mp_plat_print, "BAND_PIPE band=0 y=%d h=%d\n", (int)y, (int)bh);
    }
    bands = 1;
    y += bh;

    uint8_t *next_buf = band_b;
    while (y < screen_h) {
        bh = band_h_cfg;
        if (y + bh > screen_h) bh = screen_h - y;
        ct0 = esp_timer_get_time();
        compose_scene_band(next_buf, screen_w, y, bh, far, camera_x, tilemap, map_w, map_h, tileset, tileset_info.len, tile_size, tileset_w, tile_key, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key);
        compose_us += (uint32_t)(esp_timer_get_time() - ct0);
        submit_band_wait(prev_swap, &wait_us);
        submit_band_start(next_buf, screen_w, y, bh, &prev_swap, &kick_us);
        if (verbose) {
            mp_printf(&mp_plat_print, "BAND_PIPE band=%u y=%d h=%d\n", (unsigned)bands, (int)y, (int)bh);
        }
        ++bands;
        y += bh;
        next_buf = (next_buf == band_a) ? band_b : band_a;
    }
    submit_band_wait(prev_swap, &wait_us);

    uint32_t total_us = (uint32_t)(esp_timer_get_time() - all_t0);
    mp_obj_t out[5] = {
        mp_obj_new_int_from_uint(bands),
        mp_obj_new_int_from_uint(compose_us),
        mp_obj_new_int_from_uint(kick_us),
        mp_obj_new_int_from_uint(wait_us),
        mp_obj_new_int_from_uint(total_us),
    };
    return mp_obj_new_tuple(5, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_render_scene_bands_rgb565_obj, 28, 28, lgfx_render_scene_bands_rgb565);

} // extern "C"

#endif // !defined(NO_QSTR)
