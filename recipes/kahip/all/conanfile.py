from conan import ConanFile
from conan.tools.files import copy, get, replace_in_file
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
import os


required_conan_version = ">=2.4"

class KahipConan(ConanFile):
    name = "kahip"
    license = "MIT"
    homepage = "https://github.com/KaHIP/KaHIP"
    url = "https://github.com/conan-io/conan-center-index"
    description = "Karlsruhe High Quality Partitioning"
    topics = ("graph", "partitioning", "algorithms")
    package_type    = "library"
    settings = "os", "compiler", "arch", "build_type"
    options  = {
        "shared"         : [True, False],
        "fPIC"           : [True, False],
    }
    default_options = {
        "shared"         : False,
        "fPIC"           : True,
    }
    implements = ["auto_shared_fpic"]
    languages = "C++"

    def validate(self):
        check_min_cppstd(self, 11)

    def layout(self):
        cmake_layout(self)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        # INFO: The project forces C++11, remove it to let the user choose the standard
        replace_in_file(self, os.path.join(self.source_folder, "CMakeLists.txt"), "set(CMAKE_CXX_STANDARD 11)", "")

    def generate(self):
        tc = CMakeToolchain(self)
        # INFO: MPI requires openmpi/*:enable_cxx=True
        tc.cache_variables["NOMPI"] = True
        tc.generate()
        
        deps = CMakeDeps(self)
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        copy(self, "LICENSE", dst=os.path.join(self.package_folder, "licenses"), src=self.source_folder)

    def package_info(self):
        self.cpp_info.libs = ["kahip"]
