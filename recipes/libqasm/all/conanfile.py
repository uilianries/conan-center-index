import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import fix_apple_shared_install_name
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMakeToolchain, CMakeDeps, CMake, cmake_layout
from conan.tools.env import VirtualBuildEnv
from conan.tools.files import copy, get, rm, rmdir
from conan.tools.scm import Version

required_conan_version = ">=1.53.0"


class LibqasmConan(ConanFile):
    name = "libqasm"
    license = "Apache-2.0"
    homepage = "https://github.com/QuTech-Delft/libqasm"
    url = "https://github.com/conan-io/conan-center-index"
    description = "Library to parse cQASM files"
    topics = ("code generation", "parser", "compiler", "quantum compilation", "quantum simulation")
    settings = "os", "compiler", "build_type", "arch"
    package_type = "library"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "build_python": [True, False]
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "build_python": False
    }

    @property
    def _should_build_test(self):
        return not self.conf.get("tools.build:skip_test", default=True, check_type=bool)

    @property
    def _min_cppstd(self):
        return "20"

    @property
    def _compilers_minimum_version(self):
        return {
            "gcc": "10",
            "clang": "13",
            "apple-clang": "14",
            "Visual Studio": "16",
            "msvc": "192"
        }

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def build_requirements(self):
        self.tool_requires("tree-gen/1.0.7")
        self.tool_requires("zulu-openjdk/11.0.19")
        if self.settings.arch == "wasm":
            self.tool_requires("emsdk/3.1.50")
        if self._should_build_test:
            self.test_requires("gtest/1.14.0")

    def validate(self):
        if self.settings.compiler.cppstd:
            check_min_cppstd(self, self._min_cppstd)
        minimum_version = self._compilers_minimum_version.get(str(self.settings.compiler), False)
        if minimum_version and Version(self.settings.compiler.version) < minimum_version:
            raise ConanInvalidConfiguration(f"{self.ref} requires C++{self._min_cppstd},"
                                            f"which your compiler does not support.")

    def requirements(self):
        self.requires("fmt/10.2.1", transitive_headers=True)
        self.requires("range-v3/0.12.0", transitive_headers=True)
        self.requires("tree-gen/1.0.7", transitive_headers=True, transitive_libs=True)
        if not self.settings.arch == "wasm":
            self.requires("antlr4-cppruntime/4.13.1", options={"shared": self.options.shared}, transitive_headers=True,
                          transitive_libs=True)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        tc.variables["BUILD_SHARED_LIBS"] = self.options.shared
        tc.variables["LIBQASM_BUILD_PYTHON"] = self.options.build_python
        tc.variables["LIBQASM_BUILD_TESTS"] = self._should_build_test
        tc.generate()
        env = VirtualBuildEnv(self)
        env.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "LICENSE.md", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()
        fix_apple_shared_install_name(self)
        rm(self, "*.interp", os.path.join(self.package_folder, "include"), recursive=True)
        rm(self, "*.pdb", os.path.join(self.package_folder, "bin"))
        rm(self, "*.tokens", os.path.join(self.package_folder, "include"), recursive=True)
        rm(self, "cmake_install.cmake", os.path.join(self.package_folder, "include"), recursive=True)
        rm(self, "Makefile", os.path.join(self.package_folder, "include"), recursive=True)
        rmdir(self, os.path.join(os.path.join(self.package_folder, "include", "CMakeFiles")))
        rmdir(self, os.path.join(os.path.join(self.package_folder, "include", "v3x", "CMakeFiles")))

    def package_info(self):
        self.cpp_info.libs = ["cqasm"]
