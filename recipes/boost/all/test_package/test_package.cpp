#include <boost/any.hpp>
#ifdef TEST_BOOST_FILESYSTEM
#  include <boost/filesystem.hpp>
#endif
#ifdef TEST_BOOST_REGEX
#  include <boost/regex.hpp>
#endif
#include <cstdlib>
#include <iostream>

int main() {
#ifdef TEST_BOOST_FILESYSTEM
    boost::filesystem::path p = boost::filesystem::current_path();
    std::cout << "Boost Filesystem: " << p.size() << std::endl;
#endif
#ifdef TEST_BOOST_REGEX
    boost::regex pat("\\w+");
    boost::regex_match("conan", pat);
    std::cout << "Boost Regex: match" << std::endl;
#endif
    boost::any a = 42;
    std::cout << "Boost Any: " << boost::any_cast<int>(a) << std::endl;
    return EXIT_SUCCESS;
}
