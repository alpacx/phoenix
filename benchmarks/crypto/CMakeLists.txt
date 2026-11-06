cmake_minimum_required(VERSION 3.16)
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../../managed_components/esphome__libsodium")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(phoenix_crypto_benchmark)
