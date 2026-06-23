cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

if(NOT HEADER_ONLY)
    if(WITH_RANDOM)
        find_package(Boost COMPONENTS random REQUIRED)
        add_executable(test_boost_random random.cpp)
        target_link_libraries(test_boost_random PRIVATE Boost::random)
    endif()

    if(WITH_REGEX)
        find_package(Boost COMPONENTS regex REQUIRED)
        add_executable(test_boost_regex regex.cpp)
        target_link_libraries(test_boost_regex PRIVATE Boost::regex)
    endif()

    if(WITH_CHRONO)
        find_package(Boost COMPONENTS chrono REQUIRED)
        add_executable(test_boost_chrono chrono.cpp)
        target_link_libraries(test_boost_chrono PRIVATE Boost::chrono)
    endif()

    if(WITH_FILESYSTEM)
        find_package(Boost COMPONENTS filesystem REQUIRED)
        add_executable(test_boost_filesystem filesystem.cpp)
        target_link_libraries(test_boost_filesystem PRIVATE Boost::filesystem)
    endif()

    if(WITH_JSON)
        find_package(Boost COMPONENTS json REQUIRED)
        add_executable(test_boost_json json.cpp)
        target_link_libraries(test_boost_json PRIVATE Boost::json)
    endif()

    if(WITH_URL)
        find_package(Boost COMPONENTS url REQUIRED)
        add_executable(test_boost_url url.cpp)
        target_link_libraries(test_boost_url PRIVATE Boost::url)
    endif()

endif()

# Test header-only target
find_package(Boost REQUIRED)
add_executable(test_boost_lambda lambda.cpp)
target_link_libraries(test_boost_lambda PRIVATE Boost::headers)
