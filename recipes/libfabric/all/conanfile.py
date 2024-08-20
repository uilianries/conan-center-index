import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import is_apple_os, fix_apple_shared_install_name
from conan.tools.env import VirtualBuildEnv
from conan.tools.files import copy, get, rm, rmdir
from conan.tools.gnu import Autotools, AutotoolsToolchain, AutotoolsDeps
from conan.tools.layout import basic_layout

required_conan_version = ">=1.53.0"


class LibfabricConan(ConanFile):
    name = "libfabric"
    description = ("Libfabric, also known as Open Fabrics Interfaces (OFI), "
                   "defines a communication API for high-performance parallel and distributed applications.")
    license = ("BSD-2-Clause", "GPL-2.0-or-later")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "http://libfabric.org"
    topics = ("fabric", "communication", "framework", "service")

    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    _providers = [
        "cxi",
        "dmabuf_peer_mem",
        "efa",
        "hook_debug",
        "hook_hmem",
        "mrail",
        "opx",
        "perf",
        "profile",
        "psm2",
        "psm3",
        "rxd",
        "rxm",
        "shm",
        "sm2",
        "sockets",
        "tcp",
        "trace",
        "ucx",
        "udp",
        "usnic",
        "verbs",
        "xpmem",
    ]
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        **{ p: ["yes", "no", "dl"] for p in _providers },
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "cxi": "no",  # library not available on CCI
        "dmabuf_peer_mem": "yes",
        "efa": "yes",
        "hook_debug": "yes",
        "hook_hmem": "yes",
        "mrail": "yes",
        "opx": "no",  # Fails to build
        "perf": "yes",
        "profile": "yes",
        "psm2": "no",  # library not available on CCI
        "psm3": "no",  # library not available on CCI
        "rxd": "yes",
        "rxm": "yes",
        "shm": "yes",
        "sm2": "yes",
        "sockets": "yes",
        "tcp": "yes",
        "trace": "yes",
        "ucx": "no",
        "udp": "yes",
        "usnic": "yes",
        "verbs": "no",  # Configuration step fails
        "xpmem": "no",  # library not available on CCI
    }

    def config_options(self):
        if is_apple_os(self):
            # Requires libnl, which is not available on macOS
            del self.options.usnic
            # Require Linux-specific process_vm_readv syscall
            del self.options.shm
            del self.options.sm2
            # rdma-core is not available on macOS
            del self.options.efa
            del self.options.opx
            del self.options.verbs

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        self.settings.rm_safe("compiler.libcxx")
        self.settings.rm_safe("compiler.cppstd")

    def _is_enabled(self, opt):
        return self.options.get_safe(opt) in ["yes", "dl"]

    def requirements(self):

        if self._is_enabled("usnic"):
            self.requires("libnl/3.8.0")
        if self._is_enabled("efa") or self._is_enabled("opx") or self._is_enabled("usnic") or self._is_enabled("verbs"):
            self.requires("rdma-core/52.0")
        if self._is_enabled("opx"):
            self.requires("libnuma/2.0.16")
            self.requires("util-linux-libuuid/2.39.2")

    def layout(self):
        basic_layout(self, src_folder="src")

    def validate(self):
        if self.settings.os == "Windows":
            raise ConanInvalidConfiguration("libfabric is not available on Windows")

        for opt, _ in self.options.items():
            if opt in self._providers and self.options.get_safe(opt) not in ["yes", "no", "dl"]:
                path = str(self.options.get_safe(opt))
                if path.startswith("dl:"):
                    path = path[3:]
                if not os.path.isdir(path):
                    raise ConanInvalidConfiguration(
                        f"Option {opt} can only be 'yes', 'no', 'dl', or a directory path "
                        "(optionally with a 'dl:' prefix to build as a dynamic library)"
                    )

        if self._is_enabled("verbs"):
            if not self.dependencies["rdma-core"].options.build_librdmacm:
                raise ConanInvalidConfiguration("'-o rdma-core/*:build_librdmacm=True' is required when 'verbs' is enabled")

    def build_requirements(self):
        # Used in ./configure tests and build
        self.tool_requires("libtool/2.4.7")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        def yes_no_opt(opt):
            return "yes" if self.options.get_safe(opt) else "no"

        tc = AutotoolsToolchain(self)
        for p in self._providers:
            if p == "verbs" and not self.options.get_safe(p, "no") == "no":
                path = self.dependencies["rdma-core"].package_folder
                if self.options.verbs == "dl":
                    tc.configure_args.append(f"--enable-verbs=dl:{path}")
                else:
                    tc.configure_args.append(f"--enable-verbs={path}")
            else:
                tc.configure_args.append(f"--enable-{p}={self.options.get_safe(p, 'no')}")
        if self.settings.build_type == "Debug":
            tc.configure_args.append("--enable-debug")
        tc.configure_args.append(f"--with-bgq-progress={yes_no_opt('with_bgq_progress')}")
        tc.configure_args.append(f"--with-bgq-mr={yes_no_opt('with_bgq_mr')}")
        tc.configure_args.append("--with-cassin-headers=no")
        tc.configure_args.append("--with-cuda=no")  # TODO
        tc.configure_args.append("--with-curl=no")  # TODO
        tc.configure_args.append("--with-cxi-uapi-headers=no")
        tc.configure_args.append("--with-dsa=no")
        tc.configure_args.append("--with-gdrcopy=no")
        tc.configure_args.append("--with-json-c=no")  # TODO
        if self._is_enabled("usnic"):
            tc.configure_args.append(f"--with-libnl={self.dependencies['libnl'].package_folder}")
        else:
            tc.configure_args.append("--with-libnl=no")
        tc.configure_args.append("--with-lttng=no")
        tc.configure_args.append("--with-neuron=no")
        tc.configure_args.append(f"--with-numa={yes_no_opt('opx')}")
        tc.configure_args.append("--with-psm2-src=no")
        tc.configure_args.append("--with-psm3-rv=no")
        tc.configure_args.append("--with-rocr=no")
        tc.configure_args.append("--with-synapseai=no")
        tc.configure_args.append("--with-uring=no")  # TODO
        tc.configure_args.append("--with-ze=no")
        tc.generate()

        deps = AutotoolsDeps(self)
        deps.generate()

        VirtualBuildEnv(self).generate()

    def build(self):
        autotools = Autotools(self)
        autotools.configure()
        autotools.make()

    def package(self):
        copy(self, "COPYING", dst=os.path.join(self.package_folder, "licenses"), src=self.source_folder)
        autotools = Autotools(self)
        autotools.install()
        rmdir(self, os.path.join(self.package_folder, "share"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rm(self, "*.la", self.package_folder, recursive=True)
        fix_apple_shared_install_name(self)

    def package_info(self):
        self.cpp_info.set_property("pkg_config_name", "libfabric")
        self.cpp_info.libs = ["fabric"]
        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs = ["pthread", "m", "rt", "dl"]
        if self.settings.compiler in ["gcc", "clang"]:
            self.cpp_info.system_libs.append("atomic")
