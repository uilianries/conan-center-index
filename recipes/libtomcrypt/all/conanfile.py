from conan import ConanFile
from conan.tools.files import copy, chdir, get, rmdir, rm
from conan.tools.layout import basic_layout
from conan.tools.microsoft import is_msvc
from conan.tools.gnu import Autotools, AutotoolsToolchain, AutotoolsDeps
import os

conan_minimum_required = ">=2.4.0"

class LibtomcryptConan(ConanFile):
    name = "libtomcrypt"
    description = "A comprehensive, modular and portable cryptographic toolkit."
    license = "WTFPL"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://www.libtom.net/LibTomCrypt/"
    topics = ("cryptography", "encryption", "security")
    package_type = "library"
    languages = "C"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}
    implements = ["auto_shared_fpic"]

    def layout(self):
        basic_layout(self, src_folder="src")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def requirements(self):
        self.requires("libtommath/1.3.0")

    def generate(self):
        tc = AutotoolsDeps(self)
        tc.generate()
        
        tc = AutotoolsToolchain(self)
        tc.make_args = self._make_args()
        tc.generate()

    @property
    def _makefile(self):
        """
        Helper method to determine the appropriate makefile based on the build options and settings.
        """
        makefile = "makefile.shared" if self.options.shared else "makefile.unix"
        if is_msvc(self):
            makefile = "makefile.msvc"
        elif self.settings.os == "Windows":
            makefile = "makefile.mingw"
        return makefile

    def _make_args(self):
        """ Helper method to construct the arguments for the make command based on the build options and settings.
            Environment variables have no effect because those variables are listed in the makefiles as arguments, so we need to pass them explicitly.
        """
        args = ["PREFIX=", f"DESTDIR={self.package_folder}",]
        compilers_from_conf = self.conf.get("tools.build:compiler_executables", default={}, check_type=dict)
        autotools_vars = AutotoolsToolchain(self).vars()
        autotoolsdeps_vars = AutotoolsDeps(self).vars()
        cc = compilers_from_conf.get("c", autotools_vars.get("CC", "cc"))
        if cc:
            args.append(f'CC={cc}')
        cflags = self.conf.get("tools.build:cflags", default=[], check_type=list) or autotools_vars.get("CFLAGS")
        cppflags = self.conf.get("tools.build:cxxflags", default=[], check_type=list) or autotoolsdeps_vars.get("CPPFLAGS")
        if cppflags:
            cflags = f"{cflags} {cppflags}" if cflags else cppflags
        if cflags:
            args.append(f'CFLAGS={cflags}')
        ldflags = self.conf.get("tools.build:sharedlinkflags", default=[], check_type=list) or autotoolsdeps_vars.get("LDFLAGS")
        if ldflags:
            args.append(f'LDFLAGS={ldflags}')
        args.append(f"EXTRALIBS={autotoolsdeps_vars.get('LIBS', '')}")
        ar = autotools_vars.get("AR")
        if ar:
            args.append(f'AR={ar}')
        ld = autotools_vars.get("LD")
        if ld:
            args.append(f'LD={ld}')
        return args

    def build(self):
        with chdir(self, self.source_folder):
            autotools = Autotools(self)
            autotools.make(makefile=self._makefile)

    def package(self):
        copy(self, "LICENSE", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        with chdir(self, self.source_folder):
            autotools = Autotools(self) 
            autotools.install(makefile=self._makefile)
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rm(self, "*.la", os.path.join(self.package_folder, "lib"))
        if self.options.shared:
            rm(self, "*.a", os.path.join(self.package_folder, "lib"))

    def package_info(self):
        self.cpp_info.libs = ["tomcrypt"]
