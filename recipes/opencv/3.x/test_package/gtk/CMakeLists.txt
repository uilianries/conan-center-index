cmake_minimum_required(VERSION 3.15)
project(test_opencv_gtk LANGUAGES CXX)

find_package(gtk CONFIG REQUIRED)
find_package(OpenCV REQUIRED core imgproc CONFIG)
find_package(gdk-pixbuf REQUIRED CONFIG)

add_executable(${PROJECT_NAME} ${PROJECT_NAME}.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE gtk::gtk gdk-pixbuf::gdk-pixbuf opencv_core opencv_imgproc)
