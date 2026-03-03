cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(OpenCV REQUIRED core CONFIG)

add_executable(${PROJECT_NAME} ${PROJECT_NAME}.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE opencv_core)
