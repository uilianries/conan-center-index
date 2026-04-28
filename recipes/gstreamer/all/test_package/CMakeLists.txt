cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES C)

find_package(GStreamer REQUIRED CONFIG)

add_executable(${PROJECT_NAME} test_package.c)

if (CMAKE_SYSTEM_NAME STREQUAL "Windows")
    target_link_libraries(${PROJECT_NAME} PRIVATE
        GStreamer::gstreamer-1.0 GStreamer::gstreamer-base-1.0 GStreamer::gstreamer-controller-1.0
        GStreamer::gstreamer-net-1.0 GStreamer::gstreamer-check-1.0)
    if (TARGET GStreamer::gstcoreelements)
        target_link_libraries(${PROJECT_NAME} PRIVATE GStreamer::gstcoreelements)
    endif ()
else()
    find_package(PkgConfig REQUIRED)
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_SYSTEM_NAME STREQUAL "FreeBSD")
        find_package(libva REQUIRED CONFIG)
    endif()
    pkg_check_modules(gstreamer-1.0 REQUIRED IMPORTED_TARGET gstreamer-1.0)
    pkg_check_modules(gstreamer-base-1.0 REQUIRED IMPORTED_TARGET gstreamer-base-1.0)
    pkg_check_modules(gstreamer-controller-1.0 REQUIRED IMPORTED_TARGET gstreamer-controller-1.0)
    pkg_check_modules(gstreamer-net-1.0 REQUIRED IMPORTED_TARGET gstreamer-net-1.0)
    pkg_check_modules(gstreamer-check-1.0 REQUIRED IMPORTED_TARGET gstreamer-check-1.0)
    pkg_check_modules(gstcoreelements IMPORTED_TARGET gstcoreelements)
    target_link_libraries(${PROJECT_NAME} PRIVATE PkgConfig::gstreamer-1.0 PkgConfig::gstreamer-base-1.0 PkgConfig::gstreamer-controller-1.0
        PkgConfig::gstreamer-net-1.0 PkgConfig::gstreamer-check-1.0)
    if (TARGET PkgConfig::gstcoreelements)
        target_link_libraries(${PROJECT_NAME} PRIVATE PkgConfig::gstcoreelements)
    endif ()
    if(CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_SYSTEM_NAME STREQUAL "FreeBSD")
        target_link_libraries(${PROJECT_NAME} PRIVATE libva::libva)
    endif()
endif()
