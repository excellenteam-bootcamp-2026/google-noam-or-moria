cmake_minimum_required(VERSION 3.20)
project(autocomplete_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(autocomplete_native SHARED
    src/autocomplete_engine.cpp
)
target_include_directories(autocomplete_native PUBLIC include)
target_compile_definitions(autocomplete_native PRIVATE AUTOCOMPLETE_NATIVE_EXPORTS)

if(MSVC)
    target_compile_options(autocomplete_native PRIVATE /W4 /permissive- /EHsc)
else()
    target_compile_options(autocomplete_native PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(autocomplete_native_tests
    tests/test_engine.cpp
)
target_link_libraries(autocomplete_native_tests PRIVATE autocomplete_native)

enable_testing()
add_test(NAME autocomplete_native_tests COMMAND autocomplete_native_tests)
