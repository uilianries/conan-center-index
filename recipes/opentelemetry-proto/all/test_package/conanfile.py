import os
from conans import ConanFile


class TestPackageConan(ConanFile):

    def test(self):
        res_folder = self.deps_user_info["opentelemetry-proto"].proto_root
        include_folder = self.deps_cpp_info["opentelemetry-proto"].include_paths[0]
        assert os.path.isfile(os.path.join(include_folder, "opentelemetry", "proto", "common", "v1", "common.pb.cc"))
        assert os.path.isfile(os.path.join(include_folder, "opentelemetry", "proto", "common", "v1", "common.pb.h"))
        assert os.path.isfile(os.path.join(res_folder, "opentelemetry", "proto", "common", "v1", "common.proto"))
