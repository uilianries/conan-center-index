#include <stdlib.h>
#include <stdio.h>

#include "librsvg/rsvg.h"


int main(void) {
    RsvgHandle *handle = rsvg_handle_new();
    g_object_unref (handle);

    printf("librsvg test package: OK\n");

    return EXIT_SUCCESS;
}
