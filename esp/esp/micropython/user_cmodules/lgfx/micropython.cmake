add_library(usermod_lgfx INTERFACE)

target_sources(usermod_lgfx INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/lgfx_mp.cpp
    ${CMAKE_CURRENT_LIST_DIR}/lgfx_band.cpp
)

target_include_directories(usermod_lgfx INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_compile_definitions(usermod_lgfx INTERFACE
    MODULE_LGFX_ENABLED=1
    ESP_PLATFORM=1
)

target_compile_options(usermod_lgfx INTERFACE
    $<$<COMPILE_LANGUAGE:CXX>:-std=gnu++17>
    $<$<COMPILE_LANGUAGE:CXX>:-fno-rtti>
    $<$<COMPILE_LANGUAGE:CXX>:-mtext-section-literals>
)

target_link_libraries(usermod_lgfx INTERFACE
    idf::LovyanGFX
)

target_link_libraries(usermod INTERFACE
    usermod_lgfx
)
