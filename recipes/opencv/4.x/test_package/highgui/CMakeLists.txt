cmake_minimum_required(VERSION 3.15)
project(test_opencv_highgui LANGUAGES CXX)

find_package(OpenCV REQUIRED core imgproc highgui CONFIG)

add_executable(${PROJECT_NAME} ${PROJECT_NAME}.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE opencv_core opencv_imgproc opencv_highgui)
