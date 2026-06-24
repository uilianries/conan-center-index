import os
from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps"

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        self.requires(self.tested_reference_str)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.cache_variables["HEADER_ONLY"] = self.dependencies["boost"].options.header_only
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not can_run(self):
            return
        for file in os.listdir(self.cpp.build.bindirs[0]):
            if file.startswith("test_boost_"):
                if self.settings.os == "Windows" and not file.endswith(".exe"):
                    continue
                self.run(os.path.join(self.cpp.build.bindirs[0], file), env="conanrun")
