from conan import ConanFile
from conan.tools.files import copy, get, rmdir
from conan.tools.gnu import PkgConfigDeps
from conan.tools.layout import basic_layout
from conan.tools.meson import Meson, MesonToolchain
import os


required_conan_version = ">=2.0"


class PackageConan(ConanFile):
    name = "librsvg"
    description = "A library to render SVG images to Cairo surfaces"
    license = "LGPL-2.1-or-later"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://gitlab.gnome.org/GNOME/librsvg"
    topics = ("svg", "cairo", "graphics")
    package_type = "library"
    languages = "C"
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

    def layout(self):
        basic_layout(self, src_folder="src")

    def build_requirements(self):
        self.tool_requires("meson/[>=1.2.3 <2]")
        if not self.conf.get("tools.gnu:pkg_config", default=False, check_type=str):
            self.tool_requires("pkgconf/[>=2.2 <3]")
            
    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        self.output.warning("Building librsvg requires rustc, cargo and cargo-c installed in your system.")
        tc = MesonToolchain(self)
        tc.project_options["introspection"] = "disabled"
        tc.project_options["rsvg-convert"] = "disabled"
        tc.project_options["docs"] = "disabled"
        tc.project_options["tests"] = False
        tc.generate()

        deps = PkgConfigDeps(self)
        deps.generate()
        
    def requirements(self):
        self.requires("glib/[>=2.50.0 <3]", transitive_headers=True)
        self.requires("cairo/[>=1.18.0 <2]", transitive_headers=True)
        self.requires("harfbuzz/[>=2.0 <13]")
        self.requires("pango/[>=1.50.0 <2]")
        self.requires("libxml2/[>=2.9.0 <3]")

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()

    def package(self):
        copy(self, "COPYING.LIB", self.source_folder, os.path.join(self.package_folder, "licenses"))
        meson = Meson(self)
        meson.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "share"))

    def package_info(self):
        self.cpp_info.libs = ["rsvg-2"]
        self.cpp_info.includedirs = [os.path.join("include", "librsvg-2.0")]
        self.cpp_info.set_property("pkg_config_name", "package")
        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs.extend(["m", "pthread", "dl", "rt"])
