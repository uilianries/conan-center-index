#include <cstdlib>
#include <cstddef>
#include <iostream>
#include "librsvg/rsvg.h"


int main(void) {
    auto handle = rsvg_handle_new();
    rsvg_handle_free(handle);
    std::cout << "librsvg test package" << std::endl;

    return EXIT_SUCCESS;
}
