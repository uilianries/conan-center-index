from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import fix_apple_shared_install_name
from conan.tools.build import check_min_cppstd
from conan.tools.files import copy, get, rm, rmdir, chdir
from conan.tools.gnu import PkgConfigDeps
from conan.tools.layout import basic_layout
from conan.tools.meson import Meson, MesonToolchain
from conan.tools.microsoft import is_msvc
import os


required_conan_version = ">=2.4"

class PackageConan(ConanFile):
    name = "librsvg"
    description = "A library to render SVG images to Cairo surfaces"
    license = "LGPL-2.1-or-later"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://wiki.gnome.org/Projects/LibRsvg"
    topics = ("svg", "cairo", "graphics", "gnome")
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }
    implements = ["auto_shared_fpic"]
    languages = ["C"]

    def layout(self):
        basic_layout(self, src_folder="src")

    def requirements(self):
        self.requires("cairo/[^1.18]", transitive_headers=True)
        self.requires("gdk-pixbuf/[^2.42]", transitive_headers=True)
        self.requires("glib/[^2.78]", transitive_headers=True, override=True)
        self.requires("freetype/[^2.13]")
        self.requires("harfbuzz/[>=8.3.0]")
        self.requires("libxml2/[^2.12]")        
        self.requires("pango/[^1.50]")
        self.requires("dav1d/[^1.3]")        
        self.requires("gobject-introspection/[^1.78]")

    def build_requirements(self):
        # INFO: Cargo and Rust are mandatory to build librsvg
        # self.tool_requires("cargo/[^1.85]")
        # self.tool_requires("rust/[^1.85]")

        self.tool_requires("meson/[>=1.3 <2]")        
        if not self.conf.get("tools.gnu:pkg_config", default=False, check_type=str):
            self.tool_requires("pkgconf/[>=2.2 <3]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        def feature(v): return "enabled" if v else "disabled"
        tc = MesonToolchain(self)
        tc.project_options["docs"] = "disabled"
        tc.project_options["tests"] = False
        tc.generate()

        deps = PkgConfigDeps(self)
        deps.generate()

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()

    def package(self):
        copy(self, "LICENSE", self.source_folder, os.path.join(self.package_folder, "licenses"))
        meson = Meson(self)
        meson.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))

    def package_info(self):
        self.cpp_info.libs = ["rsvg-2"]
        self.cpp_info.set_property("pkg_config_name", "librsvg-2.0")
        self.cpp_info.includedirs.append("include/librsvg-2.0")
