cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(Boost REQUIRED)

# Header-only test (always runs)
add_executable(test_boost_lambda lambda.cpp)
target_link_libraries(test_boost_lambda PRIVATE Boost::boost)

if(NOT HEADER_ONLY)
    add_executable(test_boost_linked linked.cpp)
    target_link_libraries(test_boost_linked PRIVATE Boost::boost)
endif()
