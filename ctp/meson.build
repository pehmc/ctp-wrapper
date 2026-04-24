#
# Copyright (c) 2026 pehmc. Apache 2.0 License.
# See LICENSE file in the project root for full license information.
#

project(
  'ctp-wrapper-linux',
  'cpp',
  version: 'stable',
  license: 'Apache',
  meson_version: '>=1.9.0',
  default_options: [
    'buildtype=release',
    'cpp_std=c++17',
    'warning_level=2',
  ],
)

# 通过环境变量接收版本目录名
ctp_version = run_command('python3', '-c',
  'import os; print(os.environ.get("CTP_VERSION", "v6.7.13"))',
  check: true
).stdout().strip()
version_dir = 'v' / ctp_version
message('[*] 构建CTP版本: ' + ctp_version)

py = import('python').find_installation(pure: false)
py_dep = py.dependency()

pybind11_include_dir = run_command('python3', '-c', 'import pybind11; print(pybind11.get_include())', check: true).stdout().strip()
message('[*] 使用pybind11路径: ' + pybind11_include_dir)

pybind11_dep = declare_dependency(
  compile_args: ['-I' + pybind11_include_dir]
)

cpp = meson.get_compiler('cpp')
message('[*] 构建目标系统: ' + host_machine.system())

# 版本特定路径
lib_dir = meson.current_source_dir() / version_dir / 'libs'

include_dirs = include_directories(
  version_dir + '/include',
  version_dir + '/src',
)

extra_cpp_args = [
  '-O3',
  '-fPIC',
  '-Wno-delete-incomplete',
  '-Wno-sign-compare',
]

# 查找CTP库（编译链接必需）
thostmduserapi_lib = cpp.find_library('thostmduserapi_se',
                                     dirs: [lib_dir],
                                     required: true)
thosttraderapi_lib = cpp.find_library('thosttraderapi_se',
                                     dirs: [lib_dir],
                                     required: true)

# 创建MD模块（install: false，产物由 gen.py 手动整理）
md_module = py.extension_module(
  'ctpmd',
  sources: [version_dir + '/src/ctpmd/ctpmd.cpp'],
  include_directories: include_dirs,
  dependencies: [py_dep, pybind11_dep, thostmduserapi_lib],
  cpp_args: extra_cpp_args,
  build_rpath: '$ORIGIN',  # 关键：编译时写入ELF，确保复制到api/后能找到同目录官方库
  install: false
)

# 创建TD模块
td_module = py.extension_module(
  'ctptd',
  sources: [version_dir + '/src/ctptd/ctptd.cpp'],
  include_directories: include_dirs,
  dependencies: [py_dep, pybind11_dep, thosttraderapi_lib],
  cpp_args: extra_cpp_args,
  build_rpath: '$ORIGIN',
  install: false
)