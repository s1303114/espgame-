#pragma once

#include "lgfx_config.hpp"

extern LGFX lcd;

#ifdef __cplusplus
extern "C" {
#endif

extern const mp_obj_fun_builtin_var_t lgfx_band_submit_probe_rgb565_obj;
extern const mp_obj_fun_builtin_var_t lgfx_render_scene_bands_rgb565_obj;
extern const mp_obj_fun_builtin_var_t lgfx_submit_native_band_frame_obj;
extern const mp_obj_fun_builtin_fixed_t lgfx_copy_last_render_profile_obj;
extern const mp_obj_fun_builtin_var_t lgfx_render_elevator_scene_bands_rgb565_obj;
extern const mp_obj_fun_builtin_var_t lgfx_pick_swappable_monk_orb_native_obj;
extern const mp_obj_fun_builtin_var_t lgfx_update_swap_preview_native_obj;
extern const mp_obj_fun_builtin_var_t lgfx_update_monk_attack_native_obj;

#ifdef __cplusplus
}
#endif
