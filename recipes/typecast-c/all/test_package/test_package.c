#include <typecast.h>
#include <stdio.h>

int main(void) {
    const char* version = typecast_version();
    printf("Typecast SDK version: %s\n", version);
    return 0;
}
