from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout, CMakeDeps
from conan.tools.files import get, rmdir, copy, replace_in_file
from conan.tools.build import build_jobs
import os

required_conan_version = ">=2.4"

class LibNetconf2Conan(ConanFile):
    name = "libnetconf2"
    license = "BSD-3-Clause"
    url = "https://github.com/conan-io/conan-center-index"
    description = "NETCONF client/server library"
    homepage = "https://github.com/CESNET/libnetconf2"
    topics = ("yang", "netconf")
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False],
               "fPIC": [True, False]}
    default_options = {
        "shared": False,
        "fPIC": True
    }
    languages = "C"
    implements = ["auto_shared_fpic"]

    def requirements(self):
        # libnetconf2/session_client.h:23 #include <libyang/libyang.h>
        self.requires("libyang/4.2.2", transitive_headers=True)
        # libnetconf2/session_client.h:30 # include <libssh/libssh.h>
        self.requires("libssh/[>=0.10.6 <1]", transitive_headers=True)
        self.requires("openssl/[>=1.1 <4]")
        self.requires("libcurl/[>=7.78 <9]")
        self.requires("libxcrypt/4.4.36")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        # INFO: Inject find_package to find libxcrypt. Project uses check_library_exists only gets from system paths
        replace_in_file(self, os.path.join(self.source_folder, "CMakeLists.txt"),
            "check_library_exists",
            "find_package(libxcrypt CONFIG REQUIRED)\ncheck_library_exists")

    def generate(self):
        tc = CMakeToolchain(self)
        tc.cache_variables["ENABLE_EXAMPLES"] = False
        tc.cache_variables["ENABLE_TESTS"] = False
        tc.cache_variables["ENABLE_PAM"] = False
        tc.cache_variables["YANG_MODULE_DIR"] = os.path.join(self.package_folder, "res")
        tc.cache_variables["CMAKE_DISABLE_FIND_PACKAGE_Doxygen"] = True
        # INFO: Avoid consuming system TLS, use Conan OpenSSL package instead.
        tc.cache_variables["CMAKE_DISABLE_FIND_PACKAGE_MbedTLS"] = True
        tc.generate()

        deps = CMakeDeps(self)
        deps.set_property("libyang", "cmake_additional_variables_prefixes", ["LIBYANG"])
        deps.set_property("libssh", "cmake_additional_variables_prefixes", ["LIBSSH"])
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))

    def package_info(self):
        self.cpp_info.libs = ["netconf2"]
        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs = ["pthread"]
        self.cpp_info.resdirs = ["res"]
        self.cpp_info.set_property("cmake_file_name", "LibNETCONF2")
        self.cpp_info.set_property("cmake_additional_variables_prefixes", ["LIBNETCONF2",])
        self.cpp_info.set_property("cmake_extra_variables", {"LIBNETCONF2_ENABLED_SSH": True, "LIBNETCONF2_ENABLED_TLS": True})
        self.cpp_info.set_property("pkg_config_custom_content", {
            "LN2_SCHEMAS_DIR": os.path.join(self.package_folder, "res"),
            "LN2_MAX_THREAD_COUNT": build_jobs(self)
        })
