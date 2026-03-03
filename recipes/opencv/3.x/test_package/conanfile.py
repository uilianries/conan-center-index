from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
import os


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "VirtualRunEnv"
    test_type = "explicit"

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        self.requires(self.tested_reference_str)        
        self.requires("gtk/3.24.51")
        self.requires("gdk-pixbuf/[>=2.42 <3]")

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["built_contrib"] = self.dependencies["opencv"].options.contrib
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if can_run(self):
            bin_path = os.path.join(self.cpp.build.bindirs[0], "core", "test_package")
            self.run(bin_path, env="conanrun")
