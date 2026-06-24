from conan import ConanFile
from conan.tools.apple import is_apple_os, XCRun
from conan.tools.build import build_jobs
from conan.tools.files import chdir, collect_libs, copy, get, save
from conan.tools.gnu import AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
from conan.tools.env import VirtualBuildEnv

import os
import shlex
import yaml

required_conan_version = ">=2.4"

_EXCLUDED_MODULES = ["python", "mpi", "graph_parallel", "cobalt", "stacktrace"]


class B2Toolchain:
    """Generates user-config.jam for Boost.Build with the active compiler and dependencies."""

    def __init__(self, conanfile):
        self._conanfile = conanfile
        tc = AutotoolsToolchain(conanfile)
        self.cxxflags = tc.cxxflags
        self.ldflags = tc.ldflags

    @property
    def toolset(self):
        conanfile = self._conanfile
        compiler = str(conanfile.settings.compiler)
        if conanfile.settings.os == "Windows":
            if compiler == "gcc":
                return "mingw"
            if compiler == "clang":
                return "clang-win"
        if compiler == "apple-clang":
            return "darwin"
        return compiler

    @property
    def _cxx(self):
        conanfile = self._conanfile
        compilers = conanfile.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        if "cpp" in compilers:
            return compilers["cpp"]
        vars = VirtualBuildEnv(conanfile).vars()
        if "CXX" in vars:
            return vars["CXX"]
        if is_apple_os(conanfile):
            return XCRun(conanfile).cxx
        return None

    def generate(self):
        conanfile = self._conanfile
        cxx = self._cxx
        # b2 misparses versioned binary names (e.g. g++-13); supply version explicitly.
        version = str(conanfile.settings.compiler.version) if cxx else ""
        cxx_spec = f" : {version} : \"{cxx}\"" if cxx else ""
        lines = [f"using {self.toolset}{cxx_spec} ;"]

        for dep_name, b2_name in [("zlib", "zlib"), ("bzip2", "bzip2"),
                                   ("xz_utils", "lzma"), ("zstd", "zstd")]:
            if dep_name not in conanfile.dependencies:
                continue
            dep = conanfile.dependencies[dep_name]
            info = dep.cpp_info.aggregated_components()
            inc = info.includedirs[0].replace("\\", "/")
            lib = info.libdirs[0].replace("\\", "/")
            lines.append(f'using {b2_name} : : <include>"{inc}" <search>"{lib}" ;')

        path = os.path.join(conanfile.source_folder, "tools", "build", "user-config.jam")
        save(conanfile, path, "\n".join(lines) + "\n")
        return path


class BoostConan(ConanFile):
    name = "boost"
    description = "Boost provides free peer-reviewed portable C++ source libraries"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.boost.org"
    license = "BSL-1.0"
    topics = ("libraries", "cpp")
    package_type = "library"
    languages = ("C++",)
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "header_only": [True, False],
        "extra_b2_flags": [None, "ANY"],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "header_only": False,
        "extra_b2_flags": None,
    }
    implements = ["auto_shared_fpic", "auto_header_only"]

    def export(self):
        copy(self, f"dependencies/dependencies-{self.version}.yml",
             src=self.recipe_folder, dst=self.export_folder)

    @property
    def _dependencies(self):
        deps_file = os.path.join(self.recipe_folder, "dependencies",
                                 f"dependencies-{self.version}.yml")
        with open(deps_file, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def layout(self):
        basic_layout(self, src_folder="src")

    def requirements(self):
        if not self.options.header_only:
            # INFO: Boost Iostreams is the only module that requires these compression dependencies
            self.requires("zlib/[>=1.2.11 <2]")
            self.requires("bzip2/[>=1.0.8 <2]")
            self.requires("xz_utils/[>=5.4.5 <6]")
            self.requires("zstd/[>=1.5 <1.6]")
            # INFO: Required by Boost.Locale
            self.requires("icu/[>=73.2 <80]")

    def build_requirements(self):
        if not self.options.header_only:
            self.tool_requires("b2/[>=5.2 <6]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        if not self.options.header_only:
            B2Toolchain(self).generate()

    @property
    def _b2_os(self):
        return {
            "Windows": "windows", "WindowsStore": "windows", "Linux": "linux",
            "Android": "android", "Macos": "darwin", "iOS": "iphone",
            "watchOS": "iphone", "tvOS": "appletv", "FreeBSD": "freebsd",
            "SunOS": "solaris",
        }.get(str(self.settings.os), str(self.settings.os).lower())

    @property
    def _b2_arch(self):
        arch = str(self.settings.arch)
        for prefix, name in [("x86", "x86"), ("ppc", "power"), ("arm", "arm"),
                              ("sparc", "sparc"), ("mips64", "mips64"), ("mips", "mips1"),
                              ("s390", "s390x"), ("riscv", "riscv")]:
            if arch.startswith(prefix):
                return name

    @property
    def _b2_address_model(self):
        return "64" if self.settings.arch in (
            "x86_64", "ppc64", "ppc64le", "mips64", "armv8", "armv8.3",
            "sparcv9", "s390x", "riscv64", "wasm64",
        ) else "32"

    def build(self):
        if self.options.header_only:
            return

        #if cross_building(self, skip_x64_x86=True):
        #    # INFO: Boost.Build tries to build stacktrace module even if it is excluded, and fails when cross-building.
        #    replace_in_file(self, os.path.join(self.source_folder, "libs", "stacktrace", "build", "Jamfile.v2"), "$(>) > $(<)", 'echo "" > $(<)', strict=False)

        tc = B2Toolchain(self)
        user_config = tc.generate()

        flags = [
            "-q",
            f"toolset={tc.toolset}",
            "--layout=system",
            f"--user-config={user_config}",
            "threading=multi",
            f"link={'shared' if self.options.shared else 'static'}",
            "variant=debug" if self.settings.build_type == "Debug" else "variant=release",
        ]

        if self._b2_os:
            flags.append(f"target-os={self._b2_os}")
        if self._b2_arch:
            flags.append(f"architecture={self._b2_arch}")
        flags.append(f"address-model={self._b2_address_model}")

        if is_msvc(self):
            flags.append(f"runtime-link={'static' if is_msvc_static_runtime(self) else 'shared'}")

        for module in _EXCLUDED_MODULES:
            flags.append(f"--without-{module}")

        flags += ["-sNO_ZLIB=0", "-sNO_BZIP2=0", "-sNO_LZMA=0", "-sNO_ZSTD=0"]
        flags += ["boost.locale.icu=on", f"-sICU_PATH={self.dependencies['icu'].package_folder}"]

        if self.options.extra_b2_flags:
            flags.extend(shlex.split(str(self.options.extra_b2_flags)))

        if tc.cxxflags:
            flags.append(f'cxxflags="{" ".join(tc.cxxflags)}"')
        if tc.ldflags:
            flags.append(f'linkflags="{" ".join(tc.ldflags)}"')

        verbosity = self.conf.get("tools.build:verbosity", default="quiet", check_type=str)
        njobs = build_jobs(self)
        flags += [
            "install",
            f"--prefix={self.package_folder}",
            f"--libdir={os.path.join(self.package_folder, 'lib')}",
            f"-j{njobs}" if njobs else "",
            "--abbreviate-paths",
            "-d2" if verbosity == "verbose" else "-d0",
        ]

        with chdir(self, self.source_folder):
            self.run(f"b2 {' '.join(flags)}")

    def package(self):
        copy(self, "LICENSE_1_0.txt", src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"))
        if self.options.header_only:
            copy(self, "**", src=os.path.join(self.source_folder, "boost"),
                 dst=os.path.join(self.package_folder, "include", "boost"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Boost")
        self.cpp_info.set_property("pkg_config_name", "boost")

        if self.options.header_only:
            self.cpp_info.bindirs = []
            self.cpp_info.libdirs = []
            return

        deps = self._dependencies
        installed = set(collect_libs(self))

        for module, libs in deps["libs"].items():
            if module in _EXCLUDED_MODULES:
                continue
            comp = self.cpp_info.components[module]
            comp.libs = [lib for lib in libs if lib in installed]
            comp.set_property("cmake_target_name", f"Boost::{module}")
            inter = [d for d in deps["dependencies"].get(module, []) if d not in _EXCLUDED_MODULES]
            comp.requires = inter
            # Disable Boost's MSVC auto-link pragma for compiled modules
            if comp.libs:
                comp.defines = [f"BOOST_{module.upper()}_NO_LIB"]

        # Header-only umbrella; Boost::boost is the traditional alias (mirrors BoostConfig.cmake)
        self.cpp_info.components["headers"].libs = []
        self.cpp_info.components["headers"].set_property("cmake_target_name", "Boost::headers")
        self.cpp_info.components["headers"].set_property("cmake_aliases", ["Boost::boost"])

        # Utility interface targets from BoostConfig.cmake (Windows-only defines)
        for util, define in [("diagnostic_definitions", "BOOST_LIB_DIAGNOSTIC"),
                              ("disable_autolinking",    "BOOST_ALL_NO_LIB"),
                              ("dynamic_linking",        "BOOST_ALL_DYN_LINK")]:
            comp = self.cpp_info.components[util]
            comp.libs = []
            comp.set_property("cmake_target_name", f"Boost::{util}")
            if self.settings.os == "Windows":
                comp.defines = [define]
                
        if "iostreams" in self.cpp_info.components:
            self.cpp_info.components["iostreams"].requires.extend(["zlib::zlib", "bzip2::bzip2", "lzma::lzma", "zstd::zstd"])
        if "locale" in self.cpp_info.components:
            self.cpp_info.components["locale"].requires.append("icu::icu")

        # System libraries attached to the components that need them
        if self.settings.os in ("Linux", "FreeBSD"):
            self.cpp_info.components["thread"].system_libs = ["pthread", "rt"]
        elif self.settings.os == "Windows":
            self.cpp_info.components["headers"].system_libs = ["bcrypt"]
            if self.options.shared:
                self.cpp_info.bindirs.append("lib")
