from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout
from conan.tools.files import copy, rmdir, get
import os


class MsQuicConan(ConanFile):
    name = "msquic"
    package_type = "library"

    # Metadata
    license = "MIT"
    url = "https://github.com/conan-io/conan-center-index"
    description = "Cross-platform, C implementation of the IETF QUIC protocol"
    homepage = "https://github.com/microsoft/msquic"
    topics = ("quic", "networking", "protocol", "microsoft", "ietf")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}
    implements = ["auto_shared_fpic"]

    def source(self):
        get(self, **self.conan_data["sources"][self.version],
            destination=self.source_folder, strip_root=True)
            
        get(self, **self.conan_data["quictls"][self.version],
            destination=os.path.join(self.source_folder, "submodules", "quictls"), strip_root=True)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def generate(self):
        tc = CMakeToolchain(self)
        tc.cache_variables["QUIC_BUILD_TOOLS"] = False
        tc.cache_variables["QUIC_BUILD_TEST"] = False
        tc.cache_variables["QUIC_BUILD_PERF"] = False
        tc.cache_variables["QUIC_BUILD_SHARED"] = self.options.shared
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "LICENSE",
             src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "share"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "msquic")
        
        self.cpp_info.components["msquic"].set_property("cmake_target_name", "msquic::msquic")
        self.cpp_info.components["msquic"].libs = ["msquic"]
        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.components["msquic"].system_libs = ["pthread", "dl", "m"]
        if self.settings.os == "Macos":
            self.cpp_info.components["msquic"].frameworks = ["CoreFoundation", "Security"]

        if self.options.shared:
            self.cpp_info.components["platform"].set_property("cmake_target_name", "msquic::platform")
            self.cpp_info.components["platform"].libs = ["msquic_platform"]
