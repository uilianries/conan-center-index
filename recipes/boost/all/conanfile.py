from conan import ConanFile
from conan.tools.apple import is_apple_os, XCRun
from conan.tools.build import build_jobs, cross_building
from conan.tools.files import (
    apply_conandata_patches, chdir, collect_libs, copy, export_conandata_patches,
    get, rename, replace_in_file, rm, rmdir, save
)
from conan.tools.gnu import AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime, msvc_runtime_flag

import os
import shlex

required_conan_version = ">=2.4"


_EXCLUDED_MODULES = ["python", "mpi", "graph_parallel", "cobalt", "stacktrace"]


class BoostConan(ConanFile):
    name = "boost"
    description = "Boost provides free peer-reviewed portable C++ source libraries"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.boost.org"
    license = "BSL-1.0"
    topics = ("libraries", "cpp")
    package_type = "library"
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

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        basic_layout(self, src_folder="src")

    def requirements(self):
        if not self.options.header_only:
            self.requires("zlib/[>=1.2.11 <2]")
            self.requires("bzip2/1.0.8")
            self.requires("xz_utils/[>=5.4.5 <6]")
            self.requires("zstd/[>=1.5 <1.6]")

    def build_requirements(self):
        if not self.options.header_only:
            self.tool_requires("b2/[>=5.2 <6]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        apply_conandata_patches(self)

    # -------------------------------------------------------------------------
    # Build helpers
    # -------------------------------------------------------------------------

    @property
    def _cxx(self):
        compilers = self.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        if "cpp" in compilers:
            return compilers["cpp"]
        if is_apple_os(self):
            return XCRun(self).cxx
        return None

    @property
    def _toolset(self):
        compiler = str(self.settings.compiler)
        if self.settings.os == "Windows":
            if compiler == "gcc":
                return "mingw"
            elif compiler == "clang":
                return "clang-win"
        if compiler == "apple-clang":
            return "darwin"
        return compiler

    @property
    def _b2_os(self):
        return {
            "Windows": "windows", "WindowsStore": "windows", "Linux": "linux",
            "Android": "android", "Macos": "darwin", "iOS": "iphone",
            "watchOS": "iphone", "tvOS": "appletv", "FreeBSD": "freebsd",
            "SunOS": "solaris",
        }.get(str(self.settings.os), str(self.settings.os))

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
    
    @property
    def _debug_flag(self):
        verbosity = self.conf.get("tools.compilation:verbosity", default="quiet", check_type=str)
        debug_level = {"quiet": 0, "verbose": 2}.get(verbosity)
        return f"-d{debug_level}"
    
    @property
    def _verbose_flag(self):
        verbosity = self.conf.get("tools.build:verbosity", default="quiet", check_type=str)
        return {"quiet": "", "verbose": "--verbose"}.get(verbosity)

    def _write_user_config_jam(self):
        """Write a minimal user-config.jam: compiler + external dependency paths."""
        cxx = self._cxx
        # b2 infers version from the compiler binary name (e.g. g++-13 → "13"),
        # but the path form confuses its parser. Supply the version explicitly.
        version = str(self.settings.compiler.version) if cxx else ""
        ver_part = f" : {version}" if version else ""
        cxx_part = f'{ver_part} : "{cxx}"' if cxx else ""
        lines = [f"using {self._toolset}{cxx_part} ;"]

        for dep_name, b2_name in [("zlib", "zlib"), ("bzip2", "bzip2"),
                                   ("xz_utils", "lzma"), ("zstd", "zstd")]:
            dep = self.dependencies[dep_name]
            info = dep.cpp_info.aggregated_components()
            inc = info.includedirs[0].replace("\\", "/")
            lib = info.libdirs[0].replace("\\", "/")
            lines.append(f'using {b2_name} : : <include>"{inc}" <search>"{lib}" ;')

        save(self, os.path.join(self.source_folder, "tools", "build", "user-config.jam"),
             "\n".join(lines) + "\n")

    def build(self):
        # iOS / watchOS / tvOS: b2 gcc.jam needs to exclude these from generic-os
        replace_in_file(self,
            os.path.join(self.source_folder, "tools", "build", "src", "tools", "gcc.jam"),
            "local generic-os = [ set.difference $(all-os) : aix darwin vxworks solaris osf hpux ] ;",
            "local generic-os = [ set.difference $(all-os) : aix darwin vxworks solaris osf hpux iphone appletv ] ;",
            strict=False)
        replace_in_file(self,
            os.path.join(self.source_folder, "tools", "build", "src", "tools", "gcc.jam"),
            "local no-threading = android beos haiku sgi darwin vxworks ;",
            "local no-threading = android beos haiku sgi darwin vxworks iphone appletv ;",
            strict=False)

        if self.options.header_only:
            return

        if cross_building(self, skip_x64_x86=True):
            replace_in_file(self,
                os.path.join(self.source_folder, "libs", "stacktrace", "build", "Jamfile.v2"),
                "$(>) > $(<)", 'echo "" > $(<)', strict=False)

        self._write_user_config_jam()

        # Use AutotoolsToolchain to get platform-appropriate cxxflags/ldflags
        tc = AutotoolsToolchain(self)
        cxx_flags = list(tc.cxxflags)
        link_flags = list(tc.ldflags)        

        flags = [
            "-q",
            f"toolset={self._toolset}",
            "--layout=system",
            f"--user-config={os.path.join(self.source_folder, 'tools', 'build', 'user-config.jam')}",
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
            flags.append(f"runtime-debugging={'on' if self.settings.runtime_type == 'Debug' else 'off'}")

        for module in _EXCLUDED_MODULES:
            flags.append(f"--without-{module}")

        flags += ["-sNO_ZLIB=0", "-sNO_BZIP2=0", "-sNO_LZMA=0", "-sNO_ZSTD=0"]

        if self.options.extra_b2_flags:
            flags.extend(shlex.split(str(self.options.extra_b2_flags)))

        if cxx_flags:
            flags.append(f'cxxflags="{" ".join(cxx_flags)}"')
        if link_flags:
            flags.append(f'linkflags="{" ".join(link_flags)}"')
            
        njobs = build_jobs(self)
        flags += [
            "install",
            f"--prefix={self.package_folder}",
            f"-j{njobs}" if njobs else "",
            "--abbreviate-paths",
            self._debug_flag,
            self._verbose_flag
        ]

        with chdir(self, self.source_folder):
            self.run(f"b2 {' '.join(flags)}")

    def package(self):
        copy(self, "LICENSE_1_0.txt", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        if self.options.header_only:
            # b2 was not run; copy headers from source manually
            copy(self, "**", src=os.path.join(self.source_folder, "boost"),
                 dst=os.path.join(self.package_folder, "include", "boost"))
            return
        # b2 install already placed files under package_folder; just clean up
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rm(self, "*.cmake", os.path.join(self.package_folder, "lib"))

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_file_name", "Boost")
        self.cpp_info.set_property("cmake_target_name", "Boost::boost")
        self.cpp_info.set_property("pkg_config_name", "boost")
        if self.options.header_only:
            self.cpp_info.bindirs = []
            self.cpp_info.libdirs = []
        else:
            self.cpp_info.libs = collect_libs(self)
            if self.settings.os in ("Linux", "FreeBSD"):
                self.cpp_info.system_libs = ["pthread", "rt"]
            elif self.settings.os == "Windows":
                self.cpp_info.system_libs = ["bcrypt"]
                if self.options.shared:
                    self.cpp_info.bindirs.append("lib")
