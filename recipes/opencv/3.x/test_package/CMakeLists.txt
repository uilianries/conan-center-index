cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

option(built_contrib "Enabled if opencv is built contrib sfm" OFF)

find_package(glib CONFIG REQUIRED)
find_package(gtk CONFIG REQUIRED)
find_package(OpenCV REQUIRED core imgproc CONFIG)

add_executable(${PROJECT_NAME} test_package.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE opencv_core opencv_imgproc $<TARGET_NAME_IF_EXISTS:opencv_sfm>)
if(built_contrib)
    target_compile_definitions(${PROJECT_NAME} PRIVATE BUILT_CONTRIB)
endif()

add_executable(test_opencv_gtk test_opencv_gtk.cpp)
target_link_libraries(test_opencv_gtk PRIVATE opencv::opencv gtk::gtk glib::glib)
