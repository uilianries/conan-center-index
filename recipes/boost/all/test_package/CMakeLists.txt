cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(Boost CONFIG REQUIRED)

add_executable(${CMAKE_PROJECT_NAME} test_package.cpp)
target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE Boost::headers)

if (TARGET Boost::regex)
    target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE Boost::regex)
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE TEST_BOOST_REGEX)
endif()

if (TARGET Boost::filesystem)
    target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE Boost::filesystem)
    target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE TEST_BOOST_FILESYSTEM)
endif()
