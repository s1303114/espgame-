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

static inline bool tile_id_is_opaque(uint8_t tid) {
    switch (tid) {
        case 2:
        case 10:
        case 24:
        case 26:
        case 28:
        case 29:
        case 30:
        case 31:
        case 36:
        case 41:
        case 42:
        case 43:
        case 44:
        case 45:
        case 46:
        case 49:
        case 50:
        case 51:
        case 52:
        case 53:
        case 57:
        case 58:
        case 59:
        case 60:
        case 61:
        case 63:
            return true;
        default:
            return false;
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
            bool opaque_tile = tile_id_is_opaque(tid);
            for (int32_t y = 0; y < vis_h; ++y) {
                const uint8_t *src_row = tileset + src_row_base + ((size_t)y * src_stride);
                uint8_t *dst_row = dst + ((((size_t)(dy + y) * (size_t)dst_w) + (size_t)dx) * 2u);
                if (transparent_key < 0 || opaque_tile) {
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

static void compose_atlas_region_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    int16_t wx,
    int16_t wy,
    const uint8_t *atlas,
    int32_t atlas_w,
    int32_t atlas_h,
    int32_t src_x,
    int32_t src_y,
    int32_t src_w,
    int32_t src_h,
    int32_t transparent_key
) {
    if (!atlas || atlas_w <= 0 || atlas_h <= 0 || src_w <= 0 || src_h <= 0) {
        return;
    }
    if (src_x < 0 || src_y < 0 || src_x + src_w > atlas_w || src_y + src_h > atlas_h) {
        return;
    }

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
    if (vis_w <= 0 || vis_h <= 0) {
        return;
    }

    size_t atlas_row_bytes = (size_t)atlas_w * 2u;
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

static constexpr int32_t kMonkOrbSrcX = 96;
static constexpr int32_t kMonkOrbSrcY = 16;
static constexpr int32_t kMonkOrbW = 16;
static constexpr int32_t kMonkOrbH = 16;

static void compose_monk_orb_sprite_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    int32_t wx,
    int32_t wy,
    const uint8_t *orb_atlas,
    int32_t orb_atlas_w,
    int32_t orb_atlas_h,
    int32_t transparent_key
) {
    if (!orb_atlas || orb_atlas_w <= 0 || orb_atlas_h <= 0) {
        return;
    }
    compose_atlas_region_band(
        dst,
        dst_w,
        dst_h,
        camera_x,
        band_top,
        (int16_t)wx,
        (int16_t)wy,
        orb_atlas,
        orb_atlas_w,
        orb_atlas_h,
        kMonkOrbSrcX,
        kMonkOrbSrcY,
        kMonkOrbW,
        kMonkOrbH,
        transparent_key
    );
}

static void compose_enemy_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *enemy_desc,
    int32_t enemy_stride,
    int32_t enemy_count,
    const uint8_t *enemy_sheet,
    int32_t enemy_sheet_w,
    int32_t enemy_sheet_h,
    const uint8_t *enemy_monk_sheet,
    int32_t enemy_monk_frame_w,
    int32_t enemy_monk_frame_h,
    int32_t enemy_monk_frame_count,
    int32_t enemy_monk_frame_hold,
    const uint8_t *enemy_monk_orb_atlas,
    int32_t enemy_monk_orb_atlas_w,
    int32_t enemy_monk_orb_atlas_h,
    int32_t enemy_key,
    int32_t enemy_frame_hold
) {
    if (!enemy_desc || enemy_count <= 0 || enemy_stride < 10) {
        return;
    }
    (void)enemy_monk_orb_atlas;
    (void)enemy_monk_orb_atlas_w;
    (void)enemy_monk_orb_atlas_h;
    const int32_t bow_frame_w = 32;
    const int32_t bow_frame_h = 32;
    bool bow_ready = enemy_sheet && enemy_sheet_w >= (10 * bow_frame_w) && enemy_sheet_h >= (3 * bow_frame_h);
    bool monk_ready = enemy_monk_sheet && enemy_monk_frame_w > 0 && enemy_monk_frame_h > 0 && enemy_monk_frame_count > 0;
    if (!bow_ready && !monk_ready) {
        return;
    }
    if (enemy_frame_hold < 1) {
        enemy_frame_hold = 1;
    }
    if (enemy_monk_frame_hold < 1) {
        enemy_monk_frame_hold = 1;
    }

    for (int32_t i = 0; i < enemy_count; ++i) {
        const uint8_t *eb = enemy_desc + ((size_t)i * (size_t)enemy_stride);
        int16_t wx = (int16_t)((uint16_t)eb[0] | ((uint16_t)eb[1] << 8));
        int16_t wy = (int16_t)((uint16_t)eb[2] | ((uint16_t)eb[3] << 8));
        int32_t anim_counter = (uint16_t)eb[4] | ((uint16_t)eb[5] << 8);
        int32_t enemy_state = (int32_t)eb[6];
        bool face_right = eb[7] != 0;
        int32_t enemy_type = (int32_t)eb[8];

        if (enemy_type == 1) {
            if (!monk_ready) {
                continue;
            }
            int32_t dx = (int32_t)wx - camera_x;
            int32_t dy = (int32_t)wy - band_top;
            if (dx >= dst_w || (dx + enemy_monk_frame_w) <= 0 || dy >= dst_h || (dy + enemy_monk_frame_h) <= 0) {
                continue;
            }
            int32_t monk_frame_idx = (anim_counter / enemy_monk_frame_hold) % enemy_monk_frame_count;
            int32_t src_x = monk_frame_idx * enemy_monk_frame_w;
            compose_atlas_region_band(
                dst,
                dst_w,
                dst_h,
                camera_x,
                band_top,
                wx,
                wy,
                enemy_monk_sheet,
                enemy_monk_frame_w * enemy_monk_frame_count,
                enemy_monk_frame_h,
                src_x,
                0,
                enemy_monk_frame_w,
                enemy_monk_frame_h,
                enemy_key
            );
            continue;
        }

        if (!bow_ready) {
            continue;
        }
        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        if (dx >= dst_w || (dx + bow_frame_w) <= 0 || dy >= dst_h || (dy + bow_frame_h) <= 0) {
            continue;
        }

        int32_t frame_idx = anim_counter / enemy_frame_hold;
        int32_t src_x = 0;
        int32_t src_y = bow_frame_h * 2;
        if (enemy_state == 2) {
            if (frame_idx > 9) {
                frame_idx = 9;
            }
            src_x = frame_idx * bow_frame_w;
            src_y = face_right ? 0 : bow_frame_h;
        } else {
            frame_idx %= 5;
            src_x = (face_right ? frame_idx : (5 + frame_idx)) * bow_frame_w;
        }

        compose_atlas_region_band(
            dst,
            dst_w,
            dst_h,
            camera_x,
            band_top,
            wx,
            wy,
            enemy_sheet,
            enemy_sheet_w,
            enemy_sheet_h,
            src_x,
            src_y,
            bow_frame_w,
            bow_frame_h,
            enemy_key
        );
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

static void compose_special_objects_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *special_desc,
    int32_t special_stride,
    int32_t special_count,
    const uint8_t *respawn_sheet,
    int32_t respawn_frame_w,
    int32_t respawn_frame_h,
    int32_t respawn_frame_count,
    const uint8_t *anchor_sheet,
    int32_t anchor_frame_w,
    int32_t anchor_frame_h,
    int32_t anchor_frame_count,
    const uint8_t *orb_atlas,
    int32_t orb_atlas_w,
    int32_t orb_atlas_h,
    int32_t special_key
) {
    if (!special_desc || special_count <= 0 || special_stride < 8) {
        return;
    }
    for (int32_t i = 0; i < special_count; ++i) {
        const uint8_t *sb = special_desc + ((size_t)i * (size_t)special_stride);
        int16_t wx = (int16_t)((uint16_t)sb[0] | ((uint16_t)sb[1] << 8));
        int16_t wy = (int16_t)((uint16_t)sb[2] | ((uint16_t)sb[3] << 8));
        int32_t kind = (int32_t)sb[4];
        int32_t frame_index = (int32_t)sb[5];
        const uint8_t *sheet = nullptr;
        int32_t frame_w = 0;
        int32_t frame_h = 0;
        int32_t frame_count = 0;
        if (kind == 0) {
            sheet = respawn_sheet;
            frame_w = respawn_frame_w;
            frame_h = respawn_frame_h;
            frame_count = respawn_frame_count;
        } else if (kind == 1) {
            sheet = anchor_sheet;
            frame_w = anchor_frame_w;
            frame_h = anchor_frame_h;
            frame_count = anchor_frame_count;
        } else if (kind == 2) {
            frame_w = kMonkOrbW;
            frame_h = kMonkOrbH;
            if (!orb_atlas || orb_atlas_w <= 0 || orb_atlas_h <= 0) {
                continue;
            }
            int32_t dx = (int32_t)wx - camera_x;
            int32_t dy = (int32_t)wy - band_top;
            if (dx >= dst_w || (dx + frame_w) <= 0 || dy >= dst_h || (dy + frame_h) <= 0) {
                continue;
            }
            compose_monk_orb_sprite_band(
                dst,
                dst_w,
                dst_h,
                camera_x,
                band_top,
                wx,
                wy,
                orb_atlas,
                orb_atlas_w,
                orb_atlas_h,
                special_key
            );
            continue;
        } else {
            continue;
        }
        if (!sheet || frame_w <= 0 || frame_h <= 0 || frame_count <= 0) {
            continue;
        }
        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        if (dx >= dst_w || (dx + frame_w) <= 0 || dy >= dst_h || (dy + frame_h) <= 0) {
            continue;
        }
        int32_t src_frame = frame_index;
        if (src_frame < 0) {
            src_frame = 0;
        }
        if (src_frame >= frame_count) {
            src_frame = frame_count - 1;
        }
        compose_atlas_region_band(
            dst,
            dst_w,
            dst_h,
            camera_x,
            band_top,
            wx,
            wy,
            sheet,
            frame_w * frame_count,
            frame_h,
            src_frame * frame_w,
            0,
            frame_w,
            frame_h,
            special_key
        );
    }
}

static void compose_overlay_band(
    uint8_t *dst,
    int32_t dst_w,
    int32_t dst_h,
    int32_t camera_x,
    int32_t band_top,
    const uint8_t *overlay_desc,
    int32_t overlay_stride,
    int32_t overlay_count,
    mp_obj_t overlay_frames_obj,
    int32_t overlay_key
) {
    if (!overlay_desc || overlay_count <= 0 || overlay_stride < 10) {
        return;
    }

    size_t frame_obj_count = 0;
    mp_obj_t *frame_objs = nullptr;
    mp_obj_get_array(overlay_frames_obj, &frame_obj_count, &frame_objs);
    if (frame_obj_count == 0 || frame_objs == nullptr) {
        return;
    }

    for (int32_t i = 0; i < overlay_count; ++i) {
        const uint8_t *ob = overlay_desc + ((size_t)i * (size_t)overlay_stride);
        int16_t wx = (int16_t)((uint16_t)ob[0] | ((uint16_t)ob[1] << 8));
        int16_t wy = (int16_t)((uint16_t)ob[2] | ((uint16_t)ob[3] << 8));
        int32_t frame_w = (uint16_t)ob[4] | ((uint16_t)ob[5] << 8);
        int32_t frame_h = (uint16_t)ob[6] | ((uint16_t)ob[7] << 8);
        int32_t frame_idx = (uint16_t)ob[8] | ((uint16_t)ob[9] << 8);
        if (frame_w <= 0 || frame_h <= 0 || frame_idx < 0 || (size_t)frame_idx >= frame_obj_count) {
            continue;
        }
        int32_t dx = (int32_t)wx - camera_x;
        int32_t dy = (int32_t)wy - band_top;
        if (dx >= dst_w || (dx + frame_w) <= 0 || dy >= dst_h || (dy + frame_h) <= 0) {
            continue;
        }

        mp_buffer_info_t frame_info;
        mp_get_buffer_raise(frame_objs[frame_idx], &frame_info, MP_BUFFER_READ);
        size_t expected_len = (size_t)frame_w * (size_t)frame_h * 2u;
        if (frame_info.len < expected_len) {
            continue;
        }
        compose_sprite_band(
            dst,
            dst_w,
            dst_h,
            (int32_t)wx - camera_x,
            (int32_t)wy - band_top,
            (const uint8_t *)frame_info.buf,
            frame_w,
            frame_h,
            overlay_key
        );
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
    int32_t sprite_key,
    const uint8_t *overlay_desc,
    int32_t overlay_stride,
    int32_t overlay_count,
    mp_obj_t overlay_frames_obj,
    const uint8_t *special_desc,
    int32_t special_stride,
    int32_t special_count,
    const uint8_t *respawn_sheet,
    int32_t respawn_frame_w,
    int32_t respawn_frame_h,
    int32_t respawn_frame_count,
    const uint8_t *anchor_sheet,
    int32_t anchor_frame_w,
    int32_t anchor_frame_h,
    int32_t anchor_frame_count,
    int32_t overlay_key,
    const uint8_t *enemy_desc,
    int32_t enemy_stride,
    int32_t enemy_count,
    const uint8_t *enemy_sheet,
    int32_t enemy_sheet_w,
    int32_t enemy_sheet_h,
    const uint8_t *enemy_monk_sheet,
    int32_t enemy_monk_frame_w,
    int32_t enemy_monk_frame_h,
    int32_t enemy_monk_frame_count,
    int32_t enemy_monk_frame_hold,
    const uint8_t *enemy_monk_orb_atlas,
    int32_t enemy_monk_orb_atlas_w,
    int32_t enemy_monk_orb_atlas_h,
    int32_t enemy_key,
    int32_t enemy_frame_hold,
    bool disable_far,
    uint32_t *band_bg_us,
    uint32_t *band_tilemap_us,
    uint32_t *band_object_us,
    uint32_t *band_special_us,
    uint32_t *band_enemy_us,
    uint32_t *band_player_us
) {
    int64_t t0 = esp_timer_get_time();
    if (disable_far) {
        memset(dst, 0, (size_t)screen_w * (size_t)band_h * 2u);
    } else {
        copy_far_band(dst, screen_w, band_y, band_h, far);
    }
    int64_t t1 = esp_timer_get_time();
    compose_tilemap_band(dst, screen_w, band_h, camera_x, band_y, tilemap, map_w, map_h, tileset, tileset_len, tile_size, tileset_w, tile_key);
    int64_t t2 = esp_timer_get_time();
    compose_objects_band(dst, screen_w, band_h, camera_x, band_y, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key);
    int64_t t3 = esp_timer_get_time();
    compose_enemy_band(dst, screen_w, band_h, camera_x, band_y, enemy_desc, enemy_stride, enemy_count, enemy_sheet, enemy_sheet_w, enemy_sheet_h, enemy_monk_sheet, enemy_monk_frame_w, enemy_monk_frame_h, enemy_monk_frame_count, enemy_monk_frame_hold, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, enemy_key, enemy_frame_hold);
    int64_t t4 = esp_timer_get_time();
    compose_special_objects_band(dst, screen_w, band_h, camera_x, band_y, special_desc, special_stride, special_count, respawn_sheet, respawn_frame_w, respawn_frame_h, respawn_frame_count, anchor_sheet, anchor_frame_w, anchor_frame_h, anchor_frame_count, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, overlay_key);
    int64_t t5 = esp_timer_get_time();
    compose_overlay_band(dst, screen_w, band_h, camera_x, band_y, overlay_desc, overlay_stride, overlay_count, overlay_frames_obj, overlay_key);
    int64_t t6 = esp_timer_get_time();
    compose_sprite_band(dst, screen_w, band_h, sprite_x, sprite_y - band_y, sprite, sprite_w, sprite_h, sprite_key);
    int64_t t7 = esp_timer_get_time();
    *band_bg_us += (uint32_t)(t1 - t0);
    *band_tilemap_us += (uint32_t)(t2 - t1);
    *band_object_us += (uint32_t)(t3 - t2);
    *band_enemy_us += (uint32_t)(t4 - t3);
    *band_special_us += (uint32_t)((t5 - t4) + (t6 - t5));
    *band_player_us += (uint32_t)(t7 - t6);
}

static void submit_band_start(
    uint8_t *buf,
    int32_t screen_w,
    int32_t band_y,
    int32_t band_h,
    bool *prev_swap,
    uint32_t *kick_us,
    uint32_t *sync_us,
    uint32_t *start_us,
    uint32_t *push_us
) {
    size_t len = (size_t)screen_w * (size_t)band_h * 2u;
    int64_t t0 = esp_timer_get_time();
    esp_err_t sync_ret = esp_cache_msync((void *)buf, len, ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_UNALIGNED);
    int64_t t1 = esp_timer_get_time();
    if (sync_ret != ESP_OK) {
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("cache msync failed: %d"), (int)sync_ret);
    }
    *prev_swap = lcd.getSwapBytes();
    lcd.startWrite();
    lcd.setSwapBytes(false);
    int64_t t2 = esp_timer_get_time();
    lcd.pushImageDMA(0, band_y, screen_w, band_h, (const uint16_t *)buf);
    int64_t t3 = esp_timer_get_time();
    *sync_us += (uint32_t)(t1 - t0);
    *start_us += (uint32_t)(t2 - t1);
    *push_us += (uint32_t)(t3 - t2);
    *kick_us += (uint32_t)(t3 - t0);
}

static void submit_band_wait(bool prev_swap, uint32_t *wait_us, uint32_t *wait_dma_us, uint32_t *end_us) {
    int64_t t0 = esp_timer_get_time();
    lcd.waitDMA();
    int64_t t1 = esp_timer_get_time();
    lcd.setSwapBytes(prev_swap);
    lcd.endWrite();
    int64_t t2 = esp_timer_get_time();
    *wait_dma_us += (uint32_t)(t1 - t0);
    *end_us += (uint32_t)(t2 - t1);
    *wait_us += (uint32_t)(t2 - t0);
}

typedef struct {
    bool active;
    bool prev_swap;
    int64_t wait_t0;
} lgfx_tail_wait_state_t;

static lgfx_tail_wait_state_t g_tail_wait_state = {false, false, 0};

extern "C" {

mp_obj_t lgfx_band_pipeline_tail_wait(void) {
    if (!g_tail_wait_state.active) {
        mp_obj_t out[4] = {
            mp_obj_new_int(0),
            mp_obj_new_int(0),
            mp_obj_new_int(0),
            mp_obj_new_int(0),
        };
        return mp_obj_new_tuple(4, out);
    }
    int64_t t_enter = esp_timer_get_time();
    lcd.waitDMA();
    int64_t t_dma = esp_timer_get_time();
    lcd.setSwapBytes(g_tail_wait_state.prev_swap);
    lcd.endWrite();
    int64_t t_done = esp_timer_get_time();
    uint32_t total_wait_us = (uint32_t)(t_done - g_tail_wait_state.wait_t0);
    uint32_t residual_wait_us = (uint32_t)(t_done - t_enter);
    uint32_t residual_dma_wait_us = (uint32_t)(t_dma - t_enter);
    uint32_t end_us = (uint32_t)(t_done - t_dma);
    g_tail_wait_state.active = false;
    mp_obj_t out[4] = {
        mp_obj_new_int_from_uint(total_wait_us),
        mp_obj_new_int_from_uint(residual_wait_us),
        mp_obj_new_int_from_uint(residual_dma_wait_us),
        mp_obj_new_int_from_uint(end_us),
    };
    return mp_obj_new_tuple(4, out);
}

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
    if (n_args != 28 && n_args != 33 && n_args != 34 && n_args != 41 && n_args != 42 && n_args != 45 && n_args != 47 && n_args != 50 && n_args != 58 && n_args != 61 && n_args != 62) {
        mp_raise_ValueError(MP_ERROR_TEXT("need 28, 33, 34, 41, 42, 45, 47, 50, 58, 61 or 62 args"));
    }
    if (g_tail_wait_state.active) {
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("tail wait pending"));
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
    mp_buffer_info_t overlay_info;
    overlay_info.buf = nullptr;
    overlay_info.len = 0;
    int32_t overlay_stride = 0;
    int32_t overlay_count = 0;
    mp_obj_t overlay_frames_obj = mp_const_empty_tuple;
    mp_buffer_info_t special_desc_info;
    special_desc_info.buf = nullptr;
    special_desc_info.len = 0;
    int32_t special_stride = 0;
    int32_t special_count = 0;
    mp_buffer_info_t respawn_sheet_info;
    respawn_sheet_info.buf = nullptr;
    respawn_sheet_info.len = 0;
    int32_t respawn_frame_w = 0;
    int32_t respawn_frame_h = 0;
    int32_t respawn_frame_count = 0;
    mp_buffer_info_t anchor_sheet_info;
    anchor_sheet_info.buf = nullptr;
    anchor_sheet_info.len = 0;
    int32_t anchor_frame_w = 0;
    int32_t anchor_frame_h = 0;
    int32_t anchor_frame_count = 0;
    int32_t overlay_key = -1;
    mp_buffer_info_t enemy_desc_info;
    enemy_desc_info.buf = nullptr;
    enemy_desc_info.len = 0;
    int32_t enemy_stride = 0;
    int32_t enemy_count = 0;
    mp_buffer_info_t enemy_sheet_info;
    enemy_sheet_info.buf = nullptr;
    enemy_sheet_info.len = 0;
    int32_t enemy_sheet_w = 0;
    int32_t enemy_sheet_h = 0;
    int32_t enemy_key = -1;
    int32_t enemy_frame_hold = 4;
    mp_buffer_info_t enemy_monk_sheet_info;
    enemy_monk_sheet_info.buf = nullptr;
    enemy_monk_sheet_info.len = 0;
    int32_t enemy_monk_frame_w = 0;
    int32_t enemy_monk_frame_h = 0;
    int32_t enemy_monk_frame_count = 0;
    int32_t enemy_monk_frame_hold = 1;
    mp_buffer_info_t enemy_monk_orb_atlas_info;
    enemy_monk_orb_atlas_info.buf = nullptr;
    enemy_monk_orb_atlas_info.len = 0;
    int32_t enemy_monk_orb_atlas_w = 0;
    int32_t enemy_monk_orb_atlas_h = 0;
    int32_t probe_flags = 0;
    bool verbose = false;
    if (n_args == 61 || n_args == 62) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        mp_get_buffer_raise(args[31], &special_desc_info, MP_BUFFER_READ);
        special_stride = (int32_t)mp_obj_get_int(args[32]);
        special_count = (int32_t)mp_obj_get_int(args[33]);
        mp_get_buffer_raise(args[34], &respawn_sheet_info, MP_BUFFER_READ);
        respawn_frame_w = (int32_t)mp_obj_get_int(args[35]);
        respawn_frame_h = (int32_t)mp_obj_get_int(args[36]);
        respawn_frame_count = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &anchor_sheet_info, MP_BUFFER_READ);
        anchor_frame_w = (int32_t)mp_obj_get_int(args[39]);
        anchor_frame_h = (int32_t)mp_obj_get_int(args[40]);
        anchor_frame_count = (int32_t)mp_obj_get_int(args[41]);
        overlay_key = (int32_t)mp_obj_get_int(args[42]);
        mp_get_buffer_raise(args[43], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[44]);
        enemy_count = (int32_t)mp_obj_get_int(args[45]);
        mp_get_buffer_raise(args[46], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[47]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[48]);
        mp_get_buffer_raise(args[49], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[50]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[51]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[52]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[53]);
        mp_get_buffer_raise(args[54], &enemy_monk_orb_atlas_info, MP_BUFFER_READ);
        enemy_monk_orb_atlas_w = (int32_t)mp_obj_get_int(args[55]);
        enemy_monk_orb_atlas_h = (int32_t)mp_obj_get_int(args[56]);
        enemy_key = (int32_t)mp_obj_get_int(args[57]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[58]);
        probe_flags = (int32_t)mp_obj_get_int(args[59]);
        verbose = mp_obj_is_true(args[60]);
    } else if (n_args == 58) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        mp_get_buffer_raise(args[31], &special_desc_info, MP_BUFFER_READ);
        special_stride = (int32_t)mp_obj_get_int(args[32]);
        special_count = (int32_t)mp_obj_get_int(args[33]);
        mp_get_buffer_raise(args[34], &respawn_sheet_info, MP_BUFFER_READ);
        respawn_frame_w = (int32_t)mp_obj_get_int(args[35]);
        respawn_frame_h = (int32_t)mp_obj_get_int(args[36]);
        respawn_frame_count = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &anchor_sheet_info, MP_BUFFER_READ);
        anchor_frame_w = (int32_t)mp_obj_get_int(args[39]);
        anchor_frame_h = (int32_t)mp_obj_get_int(args[40]);
        anchor_frame_count = (int32_t)mp_obj_get_int(args[41]);
        overlay_key = (int32_t)mp_obj_get_int(args[42]);
        mp_get_buffer_raise(args[43], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[44]);
        enemy_count = (int32_t)mp_obj_get_int(args[45]);
        mp_get_buffer_raise(args[46], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[47]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[48]);
        mp_get_buffer_raise(args[49], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[50]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[51]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[52]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[53]);
        enemy_key = (int32_t)mp_obj_get_int(args[54]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[55]);
        probe_flags = (int32_t)mp_obj_get_int(args[56]);
        verbose = mp_obj_is_true(args[57]);
    } else if (n_args == 50) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[39]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[40]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[41]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[42]);
        mp_get_buffer_raise(args[43], &enemy_monk_orb_atlas_info, MP_BUFFER_READ);
        enemy_monk_orb_atlas_w = (int32_t)mp_obj_get_int(args[44]);
        enemy_monk_orb_atlas_h = (int32_t)mp_obj_get_int(args[45]);
        enemy_key = (int32_t)mp_obj_get_int(args[46]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[47]);
        probe_flags = (int32_t)mp_obj_get_int(args[48]);
        verbose = mp_obj_is_true(args[49]);
    } else if (n_args == 47) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &enemy_monk_sheet_info, MP_BUFFER_READ);
        enemy_monk_frame_w = (int32_t)mp_obj_get_int(args[39]);
        enemy_monk_frame_h = (int32_t)mp_obj_get_int(args[40]);
        enemy_monk_frame_count = (int32_t)mp_obj_get_int(args[41]);
        enemy_monk_frame_hold = (int32_t)mp_obj_get_int(args[42]);
        enemy_key = (int32_t)mp_obj_get_int(args[43]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[44]);
        probe_flags = (int32_t)mp_obj_get_int(args[45]);
        verbose = mp_obj_is_true(args[46]);
    } else if (n_args == 42) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        enemy_key = (int32_t)mp_obj_get_int(args[38]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[39]);
        probe_flags = (int32_t)mp_obj_get_int(args[40]);
        verbose = mp_obj_is_true(args[41]);
    } else if (n_args == 41) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        mp_get_buffer_raise(args[32], &enemy_desc_info, MP_BUFFER_READ);
        enemy_stride = (int32_t)mp_obj_get_int(args[33]);
        enemy_count = (int32_t)mp_obj_get_int(args[34]);
        mp_get_buffer_raise(args[35], &enemy_sheet_info, MP_BUFFER_READ);
        enemy_sheet_w = (int32_t)mp_obj_get_int(args[36]);
        enemy_sheet_h = (int32_t)mp_obj_get_int(args[37]);
        enemy_key = (int32_t)mp_obj_get_int(args[38]);
        enemy_frame_hold = (int32_t)mp_obj_get_int(args[39]);
        verbose = mp_obj_is_true(args[40]);
    } else if (n_args == 45) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        mp_get_buffer_raise(args[31], &special_desc_info, MP_BUFFER_READ);
        special_stride = (int32_t)mp_obj_get_int(args[32]);
        special_count = (int32_t)mp_obj_get_int(args[33]);
        mp_get_buffer_raise(args[34], &respawn_sheet_info, MP_BUFFER_READ);
        respawn_frame_w = (int32_t)mp_obj_get_int(args[35]);
        respawn_frame_h = (int32_t)mp_obj_get_int(args[36]);
        respawn_frame_count = (int32_t)mp_obj_get_int(args[37]);
        mp_get_buffer_raise(args[38], &anchor_sheet_info, MP_BUFFER_READ);
        anchor_frame_w = (int32_t)mp_obj_get_int(args[39]);
        anchor_frame_h = (int32_t)mp_obj_get_int(args[40]);
        anchor_frame_count = (int32_t)mp_obj_get_int(args[41]);
        overlay_key = (int32_t)mp_obj_get_int(args[42]);
        probe_flags = (int32_t)mp_obj_get_int(args[43]);
        verbose = mp_obj_is_true(args[44]);
    } else if (n_args == 34) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        probe_flags = (int32_t)mp_obj_get_int(args[32]);
        verbose = mp_obj_is_true(args[33]);
    } else if (n_args == 33) {
        mp_get_buffer_raise(args[27], &overlay_info, MP_BUFFER_READ);
        overlay_stride = (int32_t)mp_obj_get_int(args[28]);
        overlay_count = (int32_t)mp_obj_get_int(args[29]);
        overlay_frames_obj = args[30];
        overlay_key = (int32_t)mp_obj_get_int(args[31]);
        verbose = mp_obj_is_true(args[32]);
    } else {
        verbose = mp_obj_is_true(args[27]);
    }
    bool disable_far = (probe_flags & 0x1) != 0;
    bool defer_final_wait = false;
    if (n_args == 62) {
        defer_final_wait = mp_obj_is_true(args[61]);
    }

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
    if (overlay_count > 0) {
        if (overlay_stride < 10 || overlay_info.len < (size_t)overlay_count * (size_t)overlay_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("overlay buf too small"));
        }
    }
    if (special_count > 0) {
        if (special_stride < 8 || special_desc_info.len < (size_t)special_count * (size_t)special_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("special buf too small"));
        }
    }
    if (respawn_sheet_info.buf != nullptr && respawn_frame_w > 0 && respawn_frame_h > 0 && respawn_frame_count > 0) {
        if (respawn_sheet_info.len < (size_t)respawn_frame_w * (size_t)respawn_frame_h * (size_t)respawn_frame_count * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("respawn sheet too small"));
        }
    }
    if (anchor_sheet_info.buf != nullptr && anchor_frame_w > 0 && anchor_frame_h > 0 && anchor_frame_count > 0) {
        if (anchor_sheet_info.len < (size_t)anchor_frame_w * (size_t)anchor_frame_h * (size_t)anchor_frame_count * 2u) {
            mp_raise_ValueError(MP_ERROR_TEXT("anchor sheet too small"));
        }
    }
    if (enemy_count > 0) {
        if (enemy_stride < 10 || enemy_desc_info.len < (size_t)enemy_count * (size_t)enemy_stride) {
            mp_raise_ValueError(MP_ERROR_TEXT("enemy desc too small"));
        }
        if (enemy_sheet_info.buf != nullptr && enemy_sheet_w > 0 && enemy_sheet_h > 0) {
            if (enemy_sheet_info.len < (size_t)enemy_sheet_w * (size_t)enemy_sheet_h * 2u) {
                mp_raise_ValueError(MP_ERROR_TEXT("enemy sheet too small"));
            }
        }
        if (enemy_monk_sheet_info.buf != nullptr && enemy_monk_frame_w > 0 && enemy_monk_frame_h > 0 && enemy_monk_frame_count > 0) {
            if (enemy_monk_sheet_info.len < (size_t)enemy_monk_frame_w * (size_t)enemy_monk_frame_h * (size_t)enemy_monk_frame_count * 2u) {
                mp_raise_ValueError(MP_ERROR_TEXT("enemy monk sheet too small"));
            }
        }
        if (enemy_monk_orb_atlas_info.buf != nullptr && enemy_monk_orb_atlas_w > 0 && enemy_monk_orb_atlas_h > 0) {
            if (enemy_monk_orb_atlas_info.len < (size_t)enemy_monk_orb_atlas_w * (size_t)enemy_monk_orb_atlas_h * 2u) {
                mp_raise_ValueError(MP_ERROR_TEXT("enemy monk orb atlas too small"));
            }
        }
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
    const uint8_t *overlay_desc = (const uint8_t *)overlay_info.buf;
    const uint8_t *special_desc = (const uint8_t *)special_desc_info.buf;
    const uint8_t *respawn_sheet = (const uint8_t *)respawn_sheet_info.buf;
    const uint8_t *anchor_sheet = (const uint8_t *)anchor_sheet_info.buf;
    const uint8_t *enemy_desc = (const uint8_t *)enemy_desc_info.buf;
    const uint8_t *enemy_sheet = (const uint8_t *)enemy_sheet_info.buf;
    const uint8_t *enemy_monk_sheet = (const uint8_t *)enemy_monk_sheet_info.buf;
    const uint8_t *enemy_monk_orb_atlas = (const uint8_t *)enemy_monk_orb_atlas_info.buf;

    static const uint32_t kProfileBands = 6;
    uint32_t compose_us = 0;
    uint32_t band_bg_us = 0;
    uint32_t band_tilemap_us = 0;
    uint32_t band_object_us = 0;
    uint32_t band_special_us = 0;
    uint32_t band_enemy_us = 0;
    uint32_t band_player_us = 0;
    uint32_t band_compose_each[kProfileBands] = {0};
    uint32_t band_wait_each[kProfileBands] = {0};
    uint32_t kick_us = 0;
    uint32_t wait_us = 0;
    uint32_t sync_us = 0;
    uint32_t start_us = 0;
    uint32_t push_us = 0;
    uint32_t wait_dma_us = 0;
    uint32_t end_us = 0;
    uint32_t bands = 0;
    int64_t all_t0 = esp_timer_get_time();

    int32_t y = 0;
    int32_t bh = band_h_cfg;
    if (y + bh > screen_h) bh = screen_h - y;
    int64_t ct0 = esp_timer_get_time();
    compose_scene_band(band_a, screen_w, y, bh, far, camera_x, tilemap, map_w, map_h, tileset, tileset_info.len, tile_size, tileset_w, tile_key, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key, overlay_desc, overlay_stride, overlay_count, overlay_frames_obj, special_desc, special_stride, special_count, respawn_sheet, respawn_frame_w, respawn_frame_h, respawn_frame_count, anchor_sheet, anchor_frame_w, anchor_frame_h, anchor_frame_count, overlay_key, enemy_desc, enemy_stride, enemy_count, enemy_sheet, enemy_sheet_w, enemy_sheet_h, enemy_monk_sheet, enemy_monk_frame_w, enemy_monk_frame_h, enemy_monk_frame_count, enemy_monk_frame_hold, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, enemy_key, enemy_frame_hold, disable_far, &band_bg_us, &band_tilemap_us, &band_object_us, &band_special_us, &band_enemy_us, &band_player_us);
    uint32_t compose_delta = (uint32_t)(esp_timer_get_time() - ct0);
    compose_us += compose_delta;
    band_compose_each[0] = compose_delta;

    bool prev_swap = false;
    submit_band_start(band_a, screen_w, y, bh, &prev_swap, &kick_us, &sync_us, &start_us, &push_us);
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
        compose_scene_band(next_buf, screen_w, y, bh, far, camera_x, tilemap, map_w, map_h, tileset, tileset_info.len, tile_size, tileset_w, tile_key, objbuf, obj_stride, object_count, obj_atlas, obj_atlas_w, obj_atlas_h, object_key, sprite, sprite_w, sprite_h, sprite_x, sprite_y, sprite_key, overlay_desc, overlay_stride, overlay_count, overlay_frames_obj, special_desc, special_stride, special_count, respawn_sheet, respawn_frame_w, respawn_frame_h, respawn_frame_count, anchor_sheet, anchor_frame_w, anchor_frame_h, anchor_frame_count, overlay_key, enemy_desc, enemy_stride, enemy_count, enemy_sheet, enemy_sheet_w, enemy_sheet_h, enemy_monk_sheet, enemy_monk_frame_w, enemy_monk_frame_h, enemy_monk_frame_count, enemy_monk_frame_hold, enemy_monk_orb_atlas, enemy_monk_orb_atlas_w, enemy_monk_orb_atlas_h, enemy_key, enemy_frame_hold, disable_far, &band_bg_us, &band_tilemap_us, &band_object_us, &band_special_us, &band_enemy_us, &band_player_us);
        compose_delta = (uint32_t)(esp_timer_get_time() - ct0);
        compose_us += compose_delta;
        if (bands < kProfileBands) {
            band_compose_each[bands] = compose_delta;
        }
        int64_t wt0 = esp_timer_get_time();
        submit_band_wait(prev_swap, &wait_us, &wait_dma_us, &end_us);
        uint32_t wait_delta = (uint32_t)(esp_timer_get_time() - wt0);
        if ((bands - 1) < kProfileBands) {
            band_wait_each[bands - 1] = wait_delta;
        }
        submit_band_start(next_buf, screen_w, y, bh, &prev_swap, &kick_us, &sync_us, &start_us, &push_us);
        if (verbose) {
            mp_printf(&mp_plat_print, "BAND_PIPE band=%u y=%d h=%d\n", (unsigned)bands, (int)y, (int)bh);
        }
        ++bands;
        y += bh;
        next_buf = (next_buf == band_a) ? band_b : band_a;
    }
    if (defer_final_wait) {
        g_tail_wait_state.active = true;
        g_tail_wait_state.prev_swap = prev_swap;
        g_tail_wait_state.wait_t0 = esp_timer_get_time();
    } else {
        int64_t wt0 = esp_timer_get_time();
        submit_band_wait(prev_swap, &wait_us, &wait_dma_us, &end_us);
        uint32_t wait_delta = (uint32_t)(esp_timer_get_time() - wt0);
        if ((bands - 1) < kProfileBands) {
            band_wait_each[bands - 1] = wait_delta;
        }
    }

    uint32_t total_us = (uint32_t)(esp_timer_get_time() - all_t0);
    mp_obj_t out[28] = {
        mp_obj_new_int_from_uint(bands),
        mp_obj_new_int_from_uint(compose_us),
        mp_obj_new_int_from_uint(kick_us),
        mp_obj_new_int_from_uint(wait_us),
        mp_obj_new_int_from_uint(sync_us),
        mp_obj_new_int_from_uint(start_us),
        mp_obj_new_int_from_uint(push_us),
        mp_obj_new_int_from_uint(wait_dma_us),
        mp_obj_new_int_from_uint(end_us),
        mp_obj_new_int_from_uint(total_us),
        mp_obj_new_int_from_uint(band_bg_us),
        mp_obj_new_int_from_uint(band_tilemap_us),
        mp_obj_new_int_from_uint(band_object_us),
        mp_obj_new_int_from_uint(band_special_us),
        mp_obj_new_int_from_uint(band_enemy_us),
        mp_obj_new_int_from_uint(band_player_us),
        mp_obj_new_int_from_uint(band_compose_each[0]),
        mp_obj_new_int_from_uint(band_compose_each[1]),
        mp_obj_new_int_from_uint(band_compose_each[2]),
        mp_obj_new_int_from_uint(band_compose_each[3]),
        mp_obj_new_int_from_uint(band_compose_each[4]),
        mp_obj_new_int_from_uint(band_compose_each[5]),
        mp_obj_new_int_from_uint(band_wait_each[0]),
        mp_obj_new_int_from_uint(band_wait_each[1]),
        mp_obj_new_int_from_uint(band_wait_each[2]),
        mp_obj_new_int_from_uint(band_wait_each[3]),
        mp_obj_new_int_from_uint(band_wait_each[4]),
        mp_obj_new_int_from_uint(band_wait_each[5]),
    };
    return mp_obj_new_tuple(28, out);
}
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(lgfx_render_scene_bands_rgb565_obj, 28, 62, lgfx_render_scene_bands_rgb565);

} // extern "C"

#endif // !defined(NO_QSTR)
