#include "samarium/samarium.hpp"

int main()
{
    const auto im = sm::Image{};
    fmt::print(fmt::emphasis::bold, "\nSuccessful installation!\n");
    fmt::print(fmt::emphasis::bold, "Welcome to {}\n", sm::version);
}
