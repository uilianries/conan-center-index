from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.apple import is_apple_os, to_apple_arch, XCRun
from conan.tools.build import build_jobs, cross_building, cppstd_flag
from conan.tools.env import VirtualBuildEnv
from conan.tools.files import (
    apply_conandata_patches, chdir, collect_libs, copy, export_conandata_patches,
    get, mkdir, rename, replace_in_file, rm, rmdir, save
)
from conan.tools.gnu import AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime, msvc_runtime_flag, VCVars
from conan.tools.scm import Version

import glob
import os
import re
import shlex
import yaml

required_conan_version = ">=2.4"

# Modules always excluded: require heavy optional external deps or C++20 coroutines
_EXCLUDED_MODULES = {"python", "mpi", "graph_parallel", "cobalt"}


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
        "multithreading": [True, False],
        "zlib": [True, False],
        "bzip2": [True, False],
        "lzma": [True, False],
        "zstd": [True, False],
        "i18n_backend_iconv": ["libc", "libiconv", "off"],
        "i18n_backend_icu": [True, False],
        "visibility": ["global", "protected", "hidden"],
        "numa": [True, False],
        "with_stacktrace_backtrace": [True, False],
        "addr2line_location": ["ANY"],
        "extra_b2_flags": [None, "ANY"],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "header_only": False,
        "multithreading": True,
        "zlib": True,
        "bzip2": True,
        "lzma": False,
        "zstd": False,
        "i18n_backend_iconv": "libc",
        "i18n_backend_icu": False,
        "visibility": "hidden",
        "numa": True,
        "with_stacktrace_backtrace": True,
        "addr2line_location": "/usr/bin/addr2line",
        "extra_b2_flags": None,
    }

    short_paths = True
    no_copy_source = True
    _cached_dependencies = None

    def export(self):
        copy(self, f"dependencies/{self._dependency_filename}", src=self.recipe_folder, dst=self.export_folder)

    def export_sources(self):
        export_conandata_patches(self)

    @property
    def _dependency_filename(self):
        return f"dependencies-{self.version}.yml"

    @property
    def _dependencies(self):
        if self._cached_dependencies is None:
            dependencies_filepath = os.path.join(self.recipe_folder, "dependencies", self._dependency_filename)
            if not os.path.isfile(dependencies_filepath):
                raise ConanException(f"Cannot find {dependencies_filepath}")
            with open(dependencies_filepath, encoding='utf-8') as f:
                self._cached_dependencies = yaml.safe_load(f)
        return self._cached_dependencies

    @property
    def _settings_build(self):
        return getattr(self, "settings_build", self.settings)

    @property
    def _is_clang_cl(self):
        return self.settings.os == "Windows" and self.settings.compiler == "clang"

    @property
    def _is_windows_platform(self):
        return self.settings.os in ["Windows", "WindowsStore", "WindowsCE"]

    @property
    def _is_apple_embedded_platform(self):
        return self.settings.os in ["iOS", "watchOS", "tvOS"]

    @property
    def _fPIC(self):
        return self.options.get_safe("fPIC", self.default_options["fPIC"])

    @property
    def _shared(self):
        return self.options.get_safe("shared", self.default_options["shared"])

    @property
    def _stacktrace_addr2line_available(self):
        if self._is_apple_embedded_platform or self.settings.get_safe("os.subsystem") == "catalyst":
            return False
        return not self.options.header_only and self.settings.os != "Windows"

    @property
    def _stacktrace_from_exception_available(self):
        if self.options.header_only:
            return False
        if Version(self.version) == "1.85.0":
            return self.settings.os != "Windows"
        elif Version(self.version) >= "1.91.0":
            if self.settings.get_safe("os.subsystem") == "cygwin":
                return False
            return True
        elif Version(self.version) >= "1.86.0":
            return self._b2_architecture == "x86"
        return False

    @property
    def _with_zlib(self):
        return not self.options.header_only and self._with_dependency("zlib") and self.options.zlib

    @property
    def _with_bzip2(self):
        return not self.options.header_only and self._with_dependency("bzip2") and self.options.bzip2

    @property
    def _with_lzma(self):
        return not self.options.header_only and self._with_dependency("lzma") and self.options.lzma

    @property
    def _with_zstd(self):
        return not self.options.header_only and self._with_dependency("zstd") and self.options.zstd

    @property
    def _with_icu(self):
        return not self.options.header_only and self._with_dependency("icu") and self.options.get_safe("i18n_backend_icu")

    @property
    def _with_iconv(self):
        return not self.options.header_only and self._with_dependency("iconv") and self.options.get_safe("i18n_backend_iconv") == "libiconv"

    @property
    def _with_stacktrace_backtrace(self):
        return not self.options.header_only and self.options.get_safe("with_stacktrace_backtrace", False)

    def _with_dependency(self, dependency):
        for name, reqs in self._dependencies["requirements"].items():
            if dependency in reqs:
                if name not in _EXCLUDED_MODULES:
                    return True
        return False

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
            del self.options.with_stacktrace_backtrace
            self.options.i18n_backend_iconv = "off"
        elif self.settings.os == "SunOS":
            self.options.i18n_backend_iconv = "off"
        elif is_apple_os(self):
            self.options.i18n_backend_iconv = "libiconv"
        elif self.settings.os == "Android":
            api_level = self.settings.get_safe("os.api_level")
            if api_level and Version(api_level) < "28":
                self.options.i18n_backend_iconv = "libiconv"

        if not self._stacktrace_addr2line_available:
            del self.options.addr2line_location

    def configure(self):
        if self.options.header_only:
            self.options.rm_safe("shared")
            self.options.rm_safe("fPIC")
            self.options.rm_safe("numa")
        elif self.options.shared:
            self.options.rm_safe("fPIC")
        if not self._stacktrace_addr2line_available:
            self.options.rm_safe("addr2line_location")

    def layout(self):
        basic_layout(self, src_folder="src")

    def validate(self):
        if is_msvc(self) and self._shared and is_msvc_static_runtime(self):
            raise ConanInvalidConfiguration("Boost can not be built as shared library with MT runtime.")
        if self._stacktrace_addr2line_available:
            if not os.path.isabs(str(self.options.addr2line_location)):
                raise ConanInvalidConfiguration("addr2line_location must be an absolute path to addr2line")

    def requirements(self):
        if self._with_zlib:
            self.requires("zlib/[>=1.2.11 <2]")
        if self._with_bzip2:
            self.requires("bzip2/1.0.8")
        if self._with_lzma:
            self.requires("xz_utils/[>=5.4.5 <6]")
        if self._with_zstd:
            self.requires("zstd/[>=1.5 <1.6]")
        if self._with_stacktrace_backtrace:
            self.requires("libbacktrace/cci.20210118", transitive_headers=True, transitive_libs=True)
        if self._with_icu:
            self.requires("icu/74.2")
        if self._with_iconv:
            self.requires("libiconv/1.17")

    def package_id(self):
        if self.info.options.header_only:
            self.info.clear()

    def build_requirements(self):
        if not self.options.header_only:
            self.tool_requires("b2/[>=5.2 <6]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version],
            destination=self.source_folder, strip_root=True)
        apply_conandata_patches(self)

    def generate(self):
        if not self.options.header_only:
            env = VirtualBuildEnv(self)
            env.generate()
            VCVars(self).generate()

    ##################### BUILDING METHODS ###########################

    @property
    def _b2_exe(self):
        return "b2"

    @property
    def _boost_build_dir(self):
        return os.path.join(self.source_folder, "tools", "build")

    def _clean(self):
        clean_dirs = [
            os.path.join(self.build_folder, "bin.v2"),
            os.path.join(self.build_folder, "architecture"),
            os.path.join(self.source_folder, "dist", "bin"),
            os.path.join(self.source_folder, "stage"),
            os.path.join(self.source_folder, "tools", "build", "src", "engine", "bootstrap"),
            os.path.join(self.source_folder, "tools", "build", "src", "engine", "bin.ntx86"),
            os.path.join(self.source_folder, "tools", "build", "src", "engine", "bin.ntx86_64"),
        ]
        for d in clean_dirs:
            if os.path.isdir(d):
                self.output.warning(f"removing '{d}'")
                shutil.rmtree(d)

    def build(self):
        stacktrace_jamfile = os.path.join(self.source_folder, "libs", "stacktrace", "build", "Jamfile.v2")
        if cross_building(self, skip_x64_x86=True):
            replace_in_file(self, stacktrace_jamfile, "$(>) > $(<)", "echo \"\" > $(<)", strict=False)
        if self._with_stacktrace_backtrace and self.settings.os != "Windows" and not cross_building(self):
            linker_var = "DYLD_LIBRARY_PATH" if self.settings.os == "Macos" else "LD_LIBRARY_PATH"
            libbacktrace_libdir = self.dependencies["libbacktrace"].cpp_info.aggregated_components().libdirs[0]
            patched_run_rule = f"{linker_var}={libbacktrace_libdir} $(>) > $(<)"
            replace_in_file(self, stacktrace_jamfile, "$(>) > $(<)", patched_run_rule, strict=False)
            if self.dependencies["libbacktrace"].options.shared:
                replace_in_file(self, stacktrace_jamfile, "<link>static", "<link>shared", strict=False)

        replace_in_file(self, os.path.join(self.source_folder, "boost", "stacktrace", "detail", "libbacktrace_impls.hpp"),
                              "/* thread_local */", "thread_local", strict=False)
        replace_in_file(self, os.path.join(self.source_folder, "boost", "stacktrace", "detail", "libbacktrace_impls.hpp"),
                              "/* static __thread */", "static __thread", strict=False)
        if self.settings.compiler == "apple-clang" or (self.settings.compiler == "clang" and Version(self.settings.compiler.version) < 6):
            replace_in_file(self, os.path.join(self.source_folder, "boost", "stacktrace", "detail", "libbacktrace_impls.hpp"),
                                  "thread_local", "/* thread_local */")
            replace_in_file(self, os.path.join(self.source_folder, "boost", "stacktrace", "detail", "libbacktrace_impls.hpp"),
                                  "static __thread", "/* static __thread */")
        replace_in_file(self, os.path.join(self.source_folder, "tools", "build", "src", "tools", "gcc.jam"),
                              "local generic-os = [ set.difference $(all-os) : aix darwin vxworks solaris osf hpux ] ;",
                              "local generic-os = [ set.difference $(all-os) : aix darwin vxworks solaris osf hpux iphone appletv ] ;",
                              strict=False)
        replace_in_file(self, os.path.join(self.source_folder, "tools", "build", "src", "tools", "gcc.jam"),
                              "local no-threading = android beos haiku sgi darwin vxworks ;",
                              "local no-threading = android beos haiku sgi darwin vxworks iphone appletv ;",
                              strict=False)
        replace_in_file(self, os.path.join(self.source_folder, "libs", "fiber", "build", "Jamfile.v2"),
                              "    <conditional>@numa",
                              "    <link>shared:<library>.//boost_fiber : <conditional>@numa",
                              strict=False)
        if self.settings.os == "Android":
            replace_in_file(self, os.path.join(self.source_folder, "boostcpp.jam"),
                            "! [ $(property-set).get <target-os> ] in windows cygwin darwin aix &&",
                            "! [ $(property-set).get <target-os> ] in windows cygwin darwin aix android &&",
                            strict=False)

        if self.options.header_only:
            self.output.warning("Header only package, skipping build")
            return

        self._clean()
        self._create_user_config_jam(self._boost_build_dir)

        b2_flags = " ".join(self._build_flags)
        full_command = f"{self._b2_exe} {b2_flags}"
        full_command += f' --debug-configuration --build-dir="{self.build_folder}"'
        self.output.warning(full_command)

        with chdir(self, self.source_folder):
            self.run(full_command)

    @property
    def _b2_os(self):
        return {
            "Windows": "windows",
            "WindowsStore": "windows",
            "Linux": "linux",
            "Android": "android",
            "Macos": "darwin",
            "iOS": "iphone",
            "watchOS": "iphone",
            "tvOS": "appletv",
            "FreeBSD": "freebsd",
            "SunOS": "solaris",
        }.get(str(self.settings.os))

    @property
    def _b2_address_model(self):
        if self.settings.arch in ("x86_64", "ppc64", "ppc64le", "mips64", "armv8", "armv8.3", "sparcv9", "s390x", "riscv64", "wasm64"):
            return "64"
        return "32"

    @property
    def _b2_binary_format(self):
        return {
            "Windows": "pe",
            "WindowsStore": "pe",
            "Linux": "elf",
            "Android": "elf",
            "Macos": "mach-o",
            "iOS": "mach-o",
            "watchOS": "mach-o",
            "tvOS": "mach-o",
            "FreeBSD": "elf",
            "SunOS": "elf",
        }.get(str(self.settings.os))

    @property
    def _b2_architecture(self):
        if str(self.settings.arch).startswith("x86"):
            return "x86"
        if str(self.settings.arch).startswith("ppc"):
            return "power"
        if str(self.settings.arch).startswith("arm"):
            return "arm"
        if str(self.settings.arch).startswith("sparc"):
            return "sparc"
        if str(self.settings.arch).startswith("mips64"):
            return "mips64"
        if str(self.settings.arch).startswith("mips"):
            return "mips1"
        if str(self.settings.arch).startswith("s390"):
            return "s390x"
        if str(self.settings.arch).startswith("riscv"):
            return "riscv"
        return None

    @property
    def _b2_abi(self):
        if str(self.settings.arch).startswith("x86"):
            return "ms" if str(self.settings.os) in ["Windows", "WindowsStore"] else "sysv"
        if str(self.settings.arch).startswith("ppc"):
            return "sysv"
        if str(self.settings.arch).startswith("arm"):
            return "aapcs"
        if str(self.settings.arch).startswith("mips"):
            return "o32"
        if str(self.settings.arch).startswith("riscv"):
            return "sysv"
        return None

    @property
    def _gnu_cxx11_abi(self):
        try:
            if str(self.settings.compiler.libcxx) == "libstdc++":
                return "0"
            if str(self.settings.compiler.libcxx) == "libstdc++11":
                return "1"
        except ConanException:
            pass
        return None

    @property
    def _build_flags(self):
        flags = []
        if self._build_cross_flags:
            flags.append(f'compileflags="{" ".join(self._build_cross_flags)}"')

        flags.append("-q")

        if self.options.get_safe("numa"):
            flags.append("numa=on")

        if not self._is_apple_embedded_platform and self._b2_os:
            flags.append(f"target-os={self._b2_os}")
        if self._b2_architecture:
            flags.append(f"architecture={self._b2_architecture}")
        if self._b2_address_model:
            flags.append(f"address-model={self._b2_address_model}")
        if self._b2_binary_format:
            flags.append(f"binary-format={self._b2_binary_format}")
        if self._b2_abi:
            flags.append(f"abi={self._b2_abi}")

        flags.append("--layout=system")
        flags.append(f"--user-config={os.path.join(self._boost_build_dir, 'user-config.jam')}")
        flags.append(f"-sNO_ZLIB={'0' if self._with_zlib else '1'}")
        flags.append(f"-sNO_BZIP2={'0' if self._with_bzip2 else '1'}")
        flags.append(f"-sNO_LZMA={'0' if self._with_lzma else '1'}")
        flags.append(f"-sNO_ZSTD={'0' if self._with_zstd else '1'}")

        if self.options.get_safe("i18n_backend_icu"):
            flags.append("boost.locale.icu=on")
        else:
            flags.append("boost.locale.icu=off")
            flags.append("--disable-icu")
        if self.options.get_safe("i18n_backend_iconv") in ["libc", "libiconv"]:
            flags.append("boost.locale.iconv=on")
            if self.options.get_safe("i18n_backend_iconv") == "libc":
                flags.append("boost.locale.iconv.lib=libc")
            else:
                flags.append("boost.locale.iconv.lib=libiconv")
        else:
            flags.append("boost.locale.iconv=off")
            flags.append("--disable-iconv")

        def add_defines(library):
            for define in self.dependencies[library].cpp_info.aggregated_components().defines:
                flags.append(f"define={define}")

        if self._with_zlib:
            add_defines("zlib")
        if self._with_bzip2:
            add_defines("bzip2")
        if self._with_lzma:
            add_defines("xz_utils")
        if self._with_zstd:
            add_defines("zstd")

        for define in self.conf.get("tools.build:defines", default=[], check_type=list):
            flags.append(f"define={define}")

        if is_msvc(self):
            flags.append(f"runtime-link={'static' if is_msvc_static_runtime(self) else 'shared'}")
            flags.append(f"runtime-debugging={'on' if 'd' in msvc_runtime_flag(self) else 'off'}")

        flags.append(f"threading={'single' if not self.options.multithreading else 'multi'}")
        flags.append(f"visibility={self.options.visibility}")

        flags.append(f"link={'shared' if self._shared else 'static'}")
        if self.settings.build_type == "Debug":
            flags.append("variant=debug")
        else:
            flags.append("variant=release")

        # Always exclude modules requiring heavy optional deps or C++20 coroutines
        for module in _EXCLUDED_MODULES:
            flags.append(f"--without-{module}")

        flags.append(f"toolset={self._toolset}")

        # C++ standard: extract from cppstd_flag() and pass as b2's cxxstd= parameter
        std_flag = cppstd_flag(self)
        if std_flag:
            m = re.match(r"-std=(?:gnu\+\+|c\+\+)(\w+)", std_flag)
            if m:
                flags.append(f"cxxstd={m.group(1)}")
                if "gnu++" in std_flag:
                    flags.append("cxxstd-dialect=gnu")

        # CXX and link flags
        cxx_flags = []
        link_flags = []

        if self._fPIC:
            cxx_flags.append("-fPIC")
        if self.settings.build_type == "RelWithDebInfo":
            if self.settings.compiler == "gcc" or "clang" in str(self.settings.compiler):
                cxx_flags.append("-g")
            elif is_msvc(self):
                cxx_flags.append("/Z7")

        if self.settings.os not in ("Android", "Emscripten"):
            try:
                if self._gnu_cxx11_abi:
                    flags.append(f"define=_GLIBCXX_USE_CXX11_ABI={self._gnu_cxx11_abi}")
                if self.settings.compiler in ("clang", "apple-clang"):
                    libcxx = {
                        "libstdc++11": "libstdc++",
                    }.get(str(self.settings.compiler.libcxx), str(self.settings.compiler.libcxx))
                    cxx_flags.append(f"-stdlib={libcxx}")
                    link_flags.append(f"-stdlib={libcxx}")
            except ConanException:
                pass

        if is_apple_os(self):
            apple_min_version_flag = AutotoolsToolchain(self).apple_min_version_flag
            if apple_min_version_flag:
                cxx_flags.append(apple_min_version_flag)
                link_flags.append(apple_min_version_flag)
            if self.settings.get_safe("os.subsystem") == "catalyst":
                cxx_flags.append("--target=arm64-apple-ios-macabi")
                link_flags.append("--target=arm64-apple-ios-macabi")

        if self.settings.os == "iOS":
            if self.options.multithreading:
                cxx_flags.append("-DBOOST_SP_USE_SPINLOCK")
            if self.conf.get("tools.apple:enable_bitcode", check_type=bool):
                cxx_flags.append("-fembed-bitcode")

        if self._with_stacktrace_backtrace:
            flags.append(f"-sLIBBACKTRACE_PATH={self.dependencies['libbacktrace'].package_folder}")
        if self._stacktrace_from_exception_available and "x86" not in str(self.settings.arch):
            flags.append("define=BOOST_STACKTRACE_LIBCXX_RUNTIME_MAY_CAUSE_MEMORY_LEAK=1")
        if self._with_iconv:
            flags.append(f"-sICONV_PATH={self.dependencies['libiconv'].package_folder}")
        if self._with_icu:
            flags.append(f"-sICU_PATH={self.dependencies['icu'].package_folder}")
            if not self.dependencies["icu"].options.shared:
                icu_system_libs = self.dependencies["icu"].cpp_info.aggregated_components().system_libs
                if is_msvc(self):
                    icu_ldflags = " ".join(f"{l}.lib" for l in icu_system_libs)
                else:
                    icu_ldflags = " ".join(f"-l{l}" for l in icu_system_libs)
                link_flags.append(icu_ldflags)

        if self.options.get_safe("addr2line_location"):
            cxx_flags.append(f"-DBOOST_STACKTRACE_ADDR2LINE_LOCATION={self.options.addr2line_location}")

        flags.append(f'linkflags="{" ".join(link_flags)}"')
        flags.append(f'cxxflags="{" ".join(cxx_flags)}"')

        if self.options.extra_b2_flags:
            flags.extend(shlex.split(str(self.options.extra_b2_flags)))

        njobs = build_jobs(self)
        njobs = f"-j{njobs}" if njobs else ""
        flags.extend([
            "install",
            f"--prefix={self.package_folder}",
            njobs,
            "--abbreviate-paths",
            "-d0",
        ])
        return flags

    @property
    def _build_cross_flags(self):
        flags = []
        if not cross_building(self):
            return flags
        arch = self.settings.get_safe("arch")
        self.output.info("Cross building, detecting compiler...")

        if arch.startswith("arm"):
            if "hf" in arch:
                flags.append("-mfloat-abi=hard")
        elif self.settings.os == "Emscripten":
            pass
        elif arch in ["x86", "x86_64"]:
            pass
        elif arch.startswith("ppc"):
            pass
        elif arch.startswith("mips"):
            pass
        elif arch.startswith("riscv"):
            pass
        else:
            self.output.warning(f"Unable to detect the appropriate ABI for {arch} architecture.")
        self.output.info(f"Cross building flags: {flags}")
        return flags

    @property
    def _ar(self):
        ar = VirtualBuildEnv(self).vars().get("AR")
        if ar:
            return ar
        if is_apple_os(self) and self.settings.compiler == "apple-clang":
            return XCRun(self).ar
        return None

    @property
    def _ranlib(self):
        ranlib = VirtualBuildEnv(self).vars().get("RANLIB")
        if ranlib:
            return ranlib
        if is_apple_os(self) and self.settings.compiler == "apple-clang":
            return XCRun(self).ranlib
        return None

    @property
    def _cxx(self):
        compilers_by_conf = self.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        cxx = compilers_by_conf.get("cpp") or VirtualBuildEnv(self).vars().get("CXX")
        if cxx:
            return cxx
        if is_apple_os(self) and self.settings.compiler == "apple-clang":
            return XCRun(self).cxx
        compiler_version = str(self.settings.compiler.version)
        major = compiler_version.split(".", maxsplit=1)[0]
        if self.settings.compiler == "gcc":
            return shutil.which(f"g++-{compiler_version}") or shutil.which(f"g++-{major}") or shutil.which("g++") or ""
        if self.settings.compiler == "clang":
            return shutil.which(f"clang++-{compiler_version}") or shutil.which(f"clang++-{major}") or shutil.which("clang++") or ""
        return ""

    def _create_user_config_jam(self, folder):
        self.output.warning("Patching user-config.jam")

        def create_library_config(deps_name, name):
            aggregated_cpp_info = self.dependencies[deps_name].cpp_info.aggregated_components()
            if len(aggregated_cpp_info.libs) == 0:
                return ""
            includedir = aggregated_cpp_info.includedirs[0].replace("\\", "/")
            libdir = aggregated_cpp_info.libdirs[0].replace("\\", "/")
            lib = aggregated_cpp_info.libs[0]
            version = self.dependencies[deps_name].ref.version
            return (f"\nusing {name} : {version} : "
                    f"<include>\"{includedir}\" "
                    f"<search>\"{libdir}\" "
                    f"<name>{lib} ;")

        contents = ""

        if self._with_zlib:
            contents += create_library_config("zlib", "zlib")
        if self._with_bzip2:
            contents += create_library_config("bzip2", "bzip2")
        if self._with_lzma:
            contents += create_library_config("xz_utils", "lzma")
        if self._with_zstd:
            contents += create_library_config("zstd", "zstd")

        contents += f'\nusing "{self._toolset}" : {self._toolset_version} : '

        cxx_fwd_slashes = self._cxx.replace("\\", "/")
        if cxx_fwd_slashes:
            contents += f" \"{cxx_fwd_slashes}\""

        if is_apple_os(self):
            if self.settings.compiler == "apple-clang":
                contents += f" -isysroot {XCRun(self).sdk_path}"
            if self.settings.get_safe("arch"):
                contents += f" -arch {to_apple_arch(self)}"

        contents += " : \n"
        if self._ar:
            ar_path = self._ar.replace("\\", "/")
            contents += f'<archiver>"{ar_path}" '
        if self._ranlib:
            ranlib_path = self._ranlib.replace("\\", "/")
            contents += f'<ranlib>"{ranlib_path}" '
        cxxflags = " ".join(self.conf.get("tools.build:cxxflags", default=[], check_type=list)) + " "
        cflags = " ".join(self.conf.get("tools.build:cflags", default=[], check_type=list)) + " "
        buildenv_vars = VirtualBuildEnv(self).vars()
        cppflags = buildenv_vars.get("CPPFLAGS", "") + " "
        ldflags = " ".join(self.conf.get("tools.build:sharedlinkflags", default=[], check_type=list)) + " "
        asflags = buildenv_vars.get("ASFLAGS", "") + " "

        sysroot = self.conf.get("tools.build:sysroot")
        if sysroot and not is_msvc(self):
            sysroot = sysroot.replace("\\", "/")
            sysroot = f'"{sysroot}"' if ' ' in sysroot else sysroot
            cppflags += f"--sysroot={sysroot} "
            ldflags += f"--sysroot={sysroot} "

        if self._with_stacktrace_backtrace:
            backtrace_aggregated_cpp_info = self.dependencies["libbacktrace"].cpp_info.aggregated_components()
            cppflags += " ".join(f"-I{p}" for p in backtrace_aggregated_cpp_info.includedirs) + " "
            ldflags += " ".join(f"-L{p}" for p in backtrace_aggregated_cpp_info.libdirs) + " "

        if cxxflags.strip():
            contents += f'<cxxflags>"{cxxflags.strip()}" '
        if cflags.strip():
            contents += f'<cflags>"{cflags.strip()}" '
        if cppflags.strip() or self._build_cross_flags:
            compiler_flags = cppflags.strip() + " "
            compiler_flags += " ".join(self._build_cross_flags)
            contents += f'<compileflags>"{compiler_flags}" '
        if ldflags.strip():
            contents += f'<linkflags>"{ldflags.strip()}" '
        if asflags.strip():
            contents += f'<asmflags>"{asflags.strip()}" '

        if self._is_apple_embedded_platform:
            contents += f'<target-os>"{self._b2_os}" '

        contents += " ;"

        self.output.warning(contents)
        filename = f"{folder}/user-config.jam"
        save(self, filename, contents)

    @property
    def _toolset_version(self):
        if is_msvc(self):
            # Map msvc version (e.g. 193) to toolset version (e.g. "14.3")
            version = str(self.settings.compiler.version)
            if len(version) == 3:
                return f"{version[:2]}.{version[2]}"
        return ""

    @property
    def _toolset(self):
        if is_msvc(self):
            return "clang-win" if self.settings.compiler.get_safe("toolset") == "ClangCL" else "msvc"
        if self.settings.os == "Windows" and self.settings.compiler == "clang":
            return "clang-win"
        if self.settings.os == "Emscripten" and self.settings.compiler in ("clang", "emcc"):
            return "emscripten"
        if self.settings.compiler == "gcc" and is_apple_os(self):
            return "darwin"
        if self.settings.compiler == "apple-clang":
            return "clang-darwin"
        if self.settings.os == "Android" and self.settings.compiler == "clang":
            return "clang-linux"
        if self.settings.compiler in ["clang", "gcc"]:
            return str(self.settings.compiler)
        if self.settings.compiler == "sun-cc":
            return "sunpro"
        if "intel" in str(self.settings.compiler):
            return {
                "Macos": "intel-darwin",
                "Windows": "intel-win",
                "Linux": "intel-linux",
            }[str(self.settings.os)]
        return str(self.settings.compiler)

    @property
    def _toolset_tag(self):
        compiler = {
            "apple-clang": "",
            "Visual Studio": "vc",
            "msvc": "vc",
        }.get(str(self.settings.compiler), str(self.settings.compiler))
        if (self.settings.compiler, self.settings.os) == ("gcc", "Windows"):
            compiler = "mgw"
        os_ = ""
        if self.settings.os == "Macos":
            os_ = "darwin"
        if is_msvc(self):
            toolset_version = self._toolset_version.replace(".", "")
        else:
            toolset_version = str(Version(self.settings.compiler.version).major)
        toolset_parts = [compiler, os_]
        toolset_tag = "-".join(part for part in toolset_parts if part) + toolset_version
        return toolset_tag

    def package(self):
        copy(self, "LICENSE_1_0.txt", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        if self.options.header_only:
            copy(self, "*", src=os.path.join(self.source_folder, "boost"),
                            dst=os.path.join(self.package_folder, "include", "boost"))

        if self.settings.os == "Emscripten" and not self.options.header_only:
            self._create_emscripten_libs()

        if is_msvc(self) and self._shared:
            all_libs = set(collect_libs(self, "lib"))
            static_libs = set(l for l in all_libs if l.startswith("lib"))
            shared_libs = all_libs.difference(static_libs)
            static_libs = set(l[3:] for l in static_libs)
            common_libs = static_libs.intersection(shared_libs)
            for common_lib in common_libs:
                common_lib_fullname = f"lib{common_lib}.lib"
                self.output.info(f'Unlinking static duplicate library: {os.path.join(self.package_folder, "lib", common_lib_fullname)}')
                os.unlink(os.path.join(self.package_folder, "lib", common_lib_fullname))

        dll_pdbs = glob.glob(os.path.join(self.package_folder, "lib", "*.dll")) + \
                    glob.glob(os.path.join(self.package_folder, "lib", "*.pdb"))
        if dll_pdbs:
            mkdir(self, os.path.join(self.package_folder, "bin"))
            for bin_file in dll_pdbs:
                rename(self, bin_file, os.path.join(self.package_folder, "bin", os.path.basename(bin_file)))

        rm(self, "*.pdb", os.path.join(self.package_folder, "bin"))
        if (is_apple_os(self) or self.settings.os == "Linux") and not self._shared and Version(self.version) >= "1.88.0":
            rm(self, "*.dylib", os.path.join(self.package_folder, "lib"))
            rm(self, "*.so*", os.path.join(self.package_folder, "lib"))

    def _create_emscripten_libs(self):
        staged_libs = os.path.join(self.package_folder, "lib")
        if not os.path.exists(staged_libs):
            self.output.warning(f"Lib folder doesn't exist, can't collect libraries: {staged_libs}")
            return
        for bc_file in os.listdir(staged_libs):
            if bc_file.startswith("lib") and bc_file.endswith(".bc"):
                a_file = bc_file[:-3] + ".a"
                cmd = f"emar q {os.path.join(staged_libs, a_file)} {os.path.join(staged_libs, bc_file)}"
                self.output.info(cmd)
                self.run(cmd)

    @staticmethod
    def _option_to_conan_requirement(name):
        return {
            "lzma": "xz_utils",
            "iconv": "libiconv",
        }.get(name, name)

    def package_info(self):
        self.env_info.BOOST_ROOT = self.package_folder

        self.cpp_info.set_property("cmake_file_name", "Boost")
        self.cpp_info.filenames["cmake_find_package"] = "Boost"
        self.cpp_info.filenames["cmake_find_package_multi"] = "Boost"
        self.cpp_info.names["cmake_find_package"] = "Boost"
        self.cpp_info.names["cmake_find_package_multi"] = "Boost"

        self.cpp_info.components["headers"].libs = []
        self.cpp_info.components["headers"].libdirs = []
        self.cpp_info.components["headers"].set_property("cmake_target_name", "Boost::headers")
        self.cpp_info.components["headers"].names["cmake_find_package"] = "headers"
        self.cpp_info.components["headers"].names["cmake_find_package_multi"] = "headers"
        self.cpp_info.components["headers"].names["pkg_config"] = "boost"

        # Boost::boost is an alias of Boost::headers
        self.cpp_info.components["_boost_cmake"].requires = ["headers"]
        self.cpp_info.components["_boost_cmake"].set_property("cmake_target_name", "Boost::boost")
        self.cpp_info.components["_boost_cmake"].names["cmake_find_package"] = "boost"
        self.cpp_info.components["_boost_cmake"].names["cmake_find_package_multi"] = "boost"
        if self.options.header_only:
            self.cpp_info.components["_boost_cmake"].libdirs = []

        if not self.options.header_only:
            self.cpp_info.components["_libboost"].requires = ["headers"]

            self.cpp_info.components["diagnostic_definitions"].libs = []
            self.cpp_info.components["diagnostic_definitions"].set_property("cmake_target_name", "Boost::diagnostic_definitions")
            self.cpp_info.components["diagnostic_definitions"].names["cmake_find_package"] = "diagnostic_definitions"
            self.cpp_info.components["diagnostic_definitions"].names["cmake_find_package_multi"] = "diagnostic_definitions"
            self.cpp_info.components["diagnostic_definitions"].names["pkg_config"] = "boost_diagnostic_definitions"
            self.cpp_info.components["headers"].requires.append("diagnostic_definitions")

            self.cpp_info.components["disable_autolinking"].libs = []
            self.cpp_info.components["disable_autolinking"].set_property("cmake_target_name", "Boost::disable_autolinking")
            self.cpp_info.components["disable_autolinking"].names["cmake_find_package"] = "disable_autolinking"
            self.cpp_info.components["disable_autolinking"].names["cmake_find_package_multi"] = "disable_autolinking"
            self.cpp_info.components["disable_autolinking"].names["pkg_config"] = "boost_disable_autolinking"
            self.cpp_info.components["headers"].requires.append("disable_autolinking")
            if is_msvc(self) or self._is_clang_cl:
                # DISABLES AUTO LINKING by default
                self.cpp_info.components["disable_autolinking"].defines = ["BOOST_ALL_NO_LIB"]

            self.cpp_info.components["dynamic_linking"].libs = []
            self.cpp_info.components["dynamic_linking"].set_property("cmake_target_name", "Boost::dynamic_linking")
            self.cpp_info.components["dynamic_linking"].names["cmake_find_package"] = "dynamic_linking"
            self.cpp_info.components["dynamic_linking"].names["cmake_find_package_multi"] = "dynamic_linking"
            self.cpp_info.components["dynamic_linking"].names["pkg_config"] = "boost_dynamic_linking"
            self.cpp_info.components["headers"].requires.append("dynamic_linking")
            if self._shared:
                self.cpp_info.components["dynamic_linking"].defines = ["BOOST_ALL_DYN_LINK"]

            # With system layout, library names have no suffix
            libsuffix = ""

            def add_libprefix(n):
                libprefix = ""
                if is_msvc(self) and (not self._shared or n in self._dependencies["static_only"]):
                    libprefix = "lib"
                elif self._toolset == "clang-win":
                    libprefix = "lib"
                return libprefix + n

            def filter_transform_module_libraries(names):
                libs = []
                for name in names:
                    if name in ("boost_stacktrace_windbg", "boost_stacktrace_windbg_cached") and self.settings.os != "Windows":
                        continue
                    if name in ("boost_math_c99l", "boost_math_tr1l") and (
                            str(self.settings.arch).startswith("ppc") or
                            (Version(self.version) >= "1.87.0" and self.settings.os == "Emscripten")):
                        continue
                    if name in ("boost_stacktrace_addr2line", "boost_stacktrace_backtrace", "boost_stacktrace_basic") and self.settings.os == "Windows":
                        continue
                    if name == "boost_stacktrace_from_exception" and not self._stacktrace_from_exception_available:
                        continue
                    if name == "boost_stacktrace_addr2line" and not self._stacktrace_addr2line_available:
                        continue
                    if name == "boost_stacktrace_backtrace" and self.options.get_safe("with_stacktrace_backtrace") == False:
                        continue
                    if not self.options.get_safe("numa") and "_numa" in name:
                        continue
                    libs.append(add_libprefix(name) + libsuffix)
                return libs

            all_detected_libraries = set(l[:-4] if l.endswith(".dll") else l for l in collect_libs(self))
            all_expected_libraries = set()
            incomplete_components = []

            for module in self._dependencies["dependencies"].keys():
                if module in _EXCLUDED_MODULES:
                    continue

                module_libraries = filter_transform_module_libraries(self._dependencies["libs"][module])

                if self._dependencies["libs"][module] and not module_libraries:
                    continue

                all_expected_libraries = all_expected_libraries.union(module_libraries)
                if set(module_libraries).difference(all_detected_libraries):
                    incomplete_components.append(module)

                # Boost.System is header-only since 1.69.0; stub lib built for compatibility
                if module == "system":
                    module_libraries = []

                self.cpp_info.components[module].libs = module_libraries
                self.cpp_info.components[module].requires = self._dependencies["dependencies"][module] + ["_libboost"]
                self.cpp_info.components[module].set_property("cmake_target_name", "Boost::" + module)
                self.cpp_info.components[module].names["cmake_find_package"] = module
                self.cpp_info.components[module].names["cmake_find_package_multi"] = module
                self.cpp_info.components[module].names["pkg_config"] = f"boost_{module}"

                dependencies = [d.ref.name for d, _ in self.dependencies.direct_host.items()]
                for requirement in self._dependencies.get("requirements", {}).get(module, []):
                    if self.options.get_safe(requirement, None) == False:
                        continue
                    conan_requirement = self._option_to_conan_requirement(requirement)
                    if conan_requirement not in dependencies:
                        continue
                    if module == "locale" and requirement in ("icu", "iconv"):
                        if requirement == "icu" and not self._with_icu:
                            continue
                        if requirement == "iconv" and not self._with_iconv:
                            continue
                    self.cpp_info.components[module].requires.append(f"{conan_requirement}::{conan_requirement}")

            for incomplete_component in incomplete_components:
                self.output.warning(f"Boost component '{incomplete_component}' is missing libraries. Try passing '--without-{incomplete_component}' via extra_b2_flags.")

            non_used = all_detected_libraries.difference(all_expected_libraries)
            if non_used:
                self.output.warning(f"These libraries were built, but were not mapped to any boost module: {non_used}")

            non_built = all_expected_libraries.difference(all_detected_libraries)
            if non_built:
                self.output.warning(f"These libraries were expected to be built, but were not found: {non_built}")

            if "stacktrace" in self._dependencies["dependencies"]:
                if self.settings.os in ("Linux", "FreeBSD"):
                    self.cpp_info.components["stacktrace_basic"].system_libs.append("dl")
                    if self._stacktrace_addr2line_available:
                        self.cpp_info.components["stacktrace_addr2line"].system_libs.append("dl")
                    if self._with_stacktrace_backtrace:
                        self.cpp_info.components["stacktrace_backtrace"].system_libs.append("dl")
                    if self._stacktrace_from_exception_available:
                        self.cpp_info.components["stacktrace_from_exception"].system_libs.append("dl")

                if self._stacktrace_addr2line_available:
                    self.cpp_info.components["stacktrace_addr2line"].defines.extend([
                        f"BOOST_STACKTRACE_ADDR2LINE_LOCATION=\"{self.options.addr2line_location}\"",
                        "BOOST_STACKTRACE_USE_ADDR2LINE",
                    ])

                if self._with_stacktrace_backtrace:
                    self.cpp_info.components["stacktrace_backtrace"].defines.append("BOOST_STACKTRACE_USE_BACKTRACE")
                    self.cpp_info.components["stacktrace_backtrace"].requires.append("libbacktrace::libbacktrace")

                self.cpp_info.components["stacktrace_noop"].defines.append("BOOST_STACKTRACE_USE_NOOP")

                if self.settings.os == "Windows":
                    self.cpp_info.components["stacktrace_windbg"].defines.append("BOOST_STACKTRACE_USE_WINDBG")
                    self.cpp_info.components["stacktrace_windbg"].system_libs.extend(["ole32", "dbgeng"])
                    self.cpp_info.components["stacktrace_windbg_cached"].defines.append("BOOST_STACKTRACE_USE_WINDBG_CACHED")
                    self.cpp_info.components["stacktrace_windbg_cached"].system_libs.extend(["ole32", "dbgeng"])
                elif is_apple_os(self) or self.settings.os == "FreeBSD":
                    self.cpp_info.components["stacktrace"].defines.append("BOOST_STACKTRACE_GNU_SOURCE_NOT_REQUIRED")

            if "process" in self._dependencies["dependencies"] and "process" not in _EXCLUDED_MODULES:
                if self.settings.os == "Windows":
                    self.cpp_info.components["process"].system_libs.extend(["ntdll", "shell32", "advapi32", "user32"])
                if self._shared:
                    self.cpp_info.components["process"].defines.append("BOOST_PROCESS_DYN_LINK")

            if is_msvc(self) or self._is_clang_cl:
                self.cpp_info.components["_libboost"].system_libs.append("bcrypt")
            elif self.settings.os == "Linux":
                self.cpp_info.components["_libboost"].system_libs.append("rt")
                if self.options.multithreading:
                    self.cpp_info.components["_libboost"].system_libs.append("pthread")
            elif self.settings.os == "Emscripten":
                if self.options.multithreading:
                    arch = str(self.settings.arch)
                    if arch.startswith("x86") or arch.startswith("wasm"):
                        self.cpp_info.components["_libboost"].cxxflags.append("-pthread")
                        self.cpp_info.components["_libboost"].sharedlinkflags.extend(["-pthread", "--shared-memory"])
                        self.cpp_info.components["_libboost"].exelinkflags.extend(["-pthread", "--shared-memory"])
            elif self.settings.os == "iOS":
                if self.options.multithreading:
                    self.cpp_info.components["headers"].defines.append("BOOST_SP_USE_SPINLOCK")
                else:
                    self.cpp_info.components["headers"].defines.extend(["BOOST_AC_DISABLE_THREADS", "BOOST_SP_DISABLE_THREADS"])

        self.user_info.stacktrace_addr2line_available = self._stacktrace_addr2line_available
        self.conf_info.define("user.boost:stacktrace_addr2line_available", self._stacktrace_addr2line_available)
