cmake_minimum_required(VERSION 3.16)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(phoenix)

idf_component_get_property(lwip_lib lwip COMPONENT_LIB)
target_include_directories(${lwip_lib} PRIVATE "${CMAKE_CURRENT_LIST_DIR}/main")
target_compile_definitions(${lwip_lib} PRIVATE ESP_IDF_LWIP_HOOK_FILENAME="lwip_hooks.h")
