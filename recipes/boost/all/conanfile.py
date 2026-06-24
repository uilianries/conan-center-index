from conan import ConanFile
from conan.tools.apple import is_apple_os, XCRun
from conan.tools.build import build_jobs
from conan.tools.files import chdir, collect_libs, copy, get, save, rmdir, rm
from conan.tools.gnu import AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
from conan.tools.env import VirtualBuildEnv

import os
import shlex
import yaml

required_conan_version = ">=2.4"

# TODO: It can be extracted dynamically from dependencies.yml, but could result in different recipe revision.
_CONFIGURE_OPTIONS = (
    "atomic", "charconv", "chrono", "cobalt", "container", "context",
    "contract", "coroutine", "date_time", "exception", "fiber", "filesystem",
    "graph", "graph_parallel", "iostreams", "json", "locale", "log", "math",
    "mpi", "nowide", "process", "program_options", "python", "random",
    "regex", "serialization", "stacktrace", "system", "test", "thread",
    "timer", "type_erasure", "url", "wave",
)

# Disabled by default: require heavy external deps or are niche/C++20-only.
_DEFAULT_WITHOUT = {"python", "mpi", "graph_parallel", "cobalt", "stacktrace"}


class B2Toolchain:
    """Generates the user-config.jam used to build Boost with B2"""

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def toolset(self):
        if self._conanfile.settings.os == "Windows":
            if self._conanfile.settings.compiler == "gcc":
                return "mingw"
            if self._conanfile.settings.compiler == "clang":
                return "clang-win"
        if self._conanfile.settings.compiler == "apple-clang":
            return "darwin"
        return str(self._conanfile.settings.compiler)

    @property
    def _cxx(self):
        compilers = self._conanfile.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        if "cpp" in compilers:
            return compilers["cpp"]
        env_vars = VirtualBuildEnv(self._conanfile).vars()
        if "CXX" in env_vars:
            return env_vars["CXX"]
        if is_apple_os(self._conanfile):
            return XCRun(self._conanfile).cxx
        return None

    @property
    def user_config_path(self):
        return os.path.join(self._conanfile.source_folder, "tools", "build", "user-config.jam")

    def generate(self):
        version = str(self._conanfile.settings.compiler.version) if self._cxx else ""
        cxx_spec = f" : {version} : \"{self._cxx}\"" if self._cxx else ""
        lines = [f"using {self.toolset}{cxx_spec} ;"]

        for dep_name, b2_name in [("zlib", "zlib"), ("bzip2", "bzip2"),
                                   ("xz_utils", "lzma"), ("zstd", "zstd")]:
            if dep_name not in self._conanfile.dependencies:
                continue
            dep = self._conanfile.dependencies[dep_name]
            info = dep.cpp_info.aggregated_components()
            inc = info.includedirs[0].replace("\\", "/")
            lib = info.libdirs[0].replace("\\", "/")
            lines.append(f'using {b2_name} : : <include>"{inc}" <search>"{lib}" ;')

        save(self._conanfile, self.user_config_path, "\n".join(lines) + "\n")


class B2Tool:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def _os(self):
        return {
            "Windows": "windows", "WindowsStore": "windows", "Linux": "linux",
            "Android": "android", "Macos": "darwin", "iOS": "iphone",
            "watchOS": "iphone", "tvOS": "appletv", "FreeBSD": "freebsd",
            "SunOS": "solaris",
        }.get(str(self._conanfile.settings.os))

    @property
    def _arch(self):
        arch = str(self._conanfile.settings.arch)
        for prefix, name in [("x86", "x86"), ("ppc", "power"), ("arm", "arm"),
                              ("sparc", "sparc"), ("mips64", "mips64"), ("mips", "mips1"),
                              ("s390", "s390x"), ("riscv", "riscv")]:
            if arch.startswith(prefix):
                return name
        return None

    @property
    def _address_model(self):
        return "64" if str(self._conanfile.settings.arch) in (
            "x86_64", "ppc64", "ppc64le", "mips64", "armv8", "armv8.3",
            "sparcv9", "s390x", "riscv64", "wasm64",
        ) else "32"

    @property
    def _abi(self):
        if str(self._conanfile.settings.arch).startswith("arm"):
            return "aapcs"
        if str(self._conanfile.settings.os) in ("Linux", "FreeBSD", "SunOS", "Android"):
            return "sysv"
        if str(self._conanfile.settings.os) == "Windows":
            return "ms" if is_msvc(self._conanfile) else "sysv"
        return None

    @property
    def _binary_format(self):
        return {
            "Windows": "pe", "WindowsStore": "pe",
            "Linux": "elf", "FreeBSD": "elf", "Android": "elf", "SunOS": "elf",
            "Macos": "mach-o", "iOS": "mach-o", "watchOS": "mach-o", "tvOS": "mach-o",
        }.get(str(self._conanfile.settings.os))

    def build(self, user_config, toolset):
        flags = [
            "-q",
            f"toolset={toolset}",
            "--layout=system",
            f"--user-config={user_config}",
            "threading=multi",
            f"link={'shared' if self._conanfile.options.shared else 'static'}",
            "variant=debug" if self._conanfile.settings.build_type == "Debug" else "variant=release",
        ]

        if self._os:
            flags.append(f"target-os={self._os}")
        if self._arch:
            flags.append(f"architecture={self._arch}")
        flags.append(f"address-model={self._address_model}")
        if self._abi:
            flags.append(f"abi={self._abi}")
        if self._binary_format:
            flags.append(f"binary-format={self._binary_format}")

        if is_msvc(self._conanfile):
            flags.append(f"runtime-link={'static' if is_msvc_static_runtime(self._conanfile) else 'shared'}")

        for module in _CONFIGURE_OPTIONS:
            if self._conanfile.options.get_safe(f"without_{module}"):
                flags.append(f"--without-{module}")

        if not self._conanfile.options.without_iostreams:
            flags += ["-sNO_ZLIB=0", "-sNO_BZIP2=0", "-sNO_LZMA=0", "-sNO_ZSTD=0"]
        if not self._conanfile.options.without_locale and "icu" in self._conanfile.dependencies:
            flags += ["boost.locale.icu=on",
                      f"-sICU_PATH={self._conanfile.dependencies['icu'].package_folder}"]

        if self._conanfile.options.extra_b2_flags:
            flags.extend(shlex.split(str(self._conanfile.options.extra_b2_flags)))

        tc = AutotoolsToolchain(self._conanfile)
        tc.generate()

        if tc.cxxflags:
            flags.append(f'cxxflags="{" ".join(tc.cxxflags)}"')
        if tc.ldflags:
            flags.append(f'linkflags="{" ".join(tc.ldflags)}"')

        verbosity = self._conanfile.conf.get("tools.build:verbosity", default="quiet", check_type=str)
        njobs = build_jobs(self._conanfile)
        flags += [
            "install",
            f"--prefix={self._conanfile.package_folder}",
            f"--libdir={os.path.join(self._conanfile.package_folder, 'lib')}",
            f"-j{njobs}" if njobs else "",
            "--abbreviate-paths",
            "-d2" if verbosity == "verbose" else "-d0",
        ]

        with chdir(self._conanfile, self._conanfile.source_folder):
            self._conanfile.run(f"b2 {' '.join(flags)}")

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
        **{f"without_{o}": [True, False] for o in _CONFIGURE_OPTIONS},
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "header_only": False,
        "extra_b2_flags": None,
        **{f"without_{o}": o in _DEFAULT_WITHOUT for o in _CONFIGURE_OPTIONS},
    }
    implements = ["auto_shared_fpic", "auto_header_only"]
    no_copy_source = True

    def export(self):
        copy(self, f"dependencies-{self.version}.yml", src=os.path.join(self.recipe_folder, "dependencies"), dst=self.export_folder)

    @property
    def _dependencies(self):
        deps_file = os.path.join(self.source_folder, f"dependencies-{self.version}.yml")
        with open(deps_file, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def layout(self):
        basic_layout(self, src_folder="src")

    def requirements(self):
        if not self.options.header_only:
            if not self.options.without_iostreams:
                self.requires("zlib/[>=1.2.11 <2]")
                self.requires("bzip2/[>=1.0.8 <2]")
                self.requires("xz_utils/[>=5.4.5 <6]")
                self.requires("zstd/[>=1.5 <1.6]")
            if not self.options.without_locale:
                self.requires("icu/[>=73.2 <80]")

    def build_requirements(self):
        if not self.options.header_only:
            self.tool_requires("b2/[>=5.2 <6]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        if not self.options.header_only:
            tc = B2Toolchain(self)
            tc.generate()

    def build(self):
        if self.options.header_only:
            return
        tc = B2Toolchain(self)
        b2 = B2Tool(self)
        b2.build(tc.user_config_path, tc.toolset)

    def package(self):
        copy(self, "LICENSE_1_0.txt", src=self.source_folder,
             dst=os.path.join(self.package_folder, "licenses"))
        if self.options.header_only:
            copy(self, "**", src=os.path.join(self.source_folder, "boost"), dst=os.path.join(self.package_folder, "include", "boost"))
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        # FIXME: Some libraries produce both static and shared
        # https://github.com/boostorg/boost/issues/1051
        if self.options.shared:
            rm(self, "*.a", os.path.join(self.package_folder, "lib"))
        else:
            rm(self, "*.so*", os.path.join(self.package_folder, "lib"))
            rm(self, "*.dylib*", os.path.join(self.package_folder, "lib"))

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "Boost")
        self.cpp_info.set_property("pkg_config_name", "boost")

        if self.options.header_only:
            self.cpp_info.bindirs = []
            self.cpp_info.libdirs = []
            return

        deps = self._dependencies
        installed = set(collect_libs(self))

        # INFO: Mimic BoostConfig.cmake
        for module, libs in deps["libs"].items():
            if self.options.get_safe(f"without_{module}"):
                continue
            comp = self.cpp_info.components[module]
            comp.libs = [lib for lib in libs if lib in installed]
            comp.set_property("cmake_target_name", f"Boost::{module}")
            inter = [d for d in deps["dependencies"].get(module, [])
                     if not self.options.get_safe(f"without_{d}", False)]
            comp.requires = inter
            if module == "iostreams":
                comp.requires.extend(["zlib::zlib", "bzip2::bzip2", "xz_utils::xz_utils", "zstd::zstd"])
            elif module == "locale":
                comp.requires.append("icu::icu")
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
                
        # System libraries attached to the components that need them
        if self.settings.os in ("Linux", "FreeBSD"):
            self.cpp_info.components["thread"].system_libs = ["pthread", "rt"]
        elif self.settings.os == "Windows":
            self.cpp_info.components["headers"].system_libs = ["bcrypt"]
            if self.options.shared:
                self.cpp_info.bindirs.append("lib")
