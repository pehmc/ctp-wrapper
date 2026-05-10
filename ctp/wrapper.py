"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import sysconfig
from pathlib import Path


class CtpWrapper:
    """
    CTP API SWIG Wrapper
    ----------------------------
    用法:
    python wrapper.py <version>       # 编译指定版本
    python wrapper.py tts_6.7.11
    python wrapper.py v6.7.13_20260225
    python wrapper.py clean           # 清理所有构建产物

    说明:
    - 调用 SWIG 生成 C++ 包装代码 -> v/{version}/src/
    - 编译并链接生成 .so 扩展模块 -> api/
    - 复制 SWIG 生成的 .py 包装文件 -> api/
    """
    def __init__(self, version: str):
        self.version = version
        self.root = Path(__file__).parent.resolve()

        # 路径配置
        self.version_dir = self.root / "v" / version
        self.include_dir = self.version_dir / "include"
        self.libs_dir = self.version_dir / "libs"
        self.src_dir = self.version_dir / "src"
        self.api_dir = self.root / "api"
        self.interface_dir = self.root / "interface"

        # Python 环境
        self.python_include = sysconfig.get_path("include")
        self.py_ver = sysconfig.get_python_version()

        # 接口定义: (swig文件, 模块名, 链接库文件名)
        # 模块名必须与 .i 文件中的 %module(name) 一致
        self.interfaces = [
            ("mdapi.i", "mdapi", "thostmduserapi_se"),
            ("tdapi.i", "tdapi", "thosttraderapi_se"),
        ]

        self._validate_env()

    def _validate_env(self):
        """校验目录和工具链"""
        if not self.version_dir.exists():
            available = [d.name for d in (self.root / "v").iterdir() if d.is_dir()]
            raise SystemExit(
                f"[错误] 版本目录不存在: {self.version_dir}\n"
                f"可用版本: {', '.join(available)}"
            )

        if not self.include_dir.exists():
            raise SystemExit(f"[错误] 头文件目录不存在: {self.include_dir}")
        if not self.libs_dir.exists():
            raise SystemExit(f"[错误] 库目录不存在: {self.libs_dir}")

        # 检查工具
        for tool in ["swig", "g++"]:
            if shutil.which(tool) is None:
                raise SystemExit(f"[错误] 未找到命令: {tool}，请先安装")

    def clean(self):
        """清理构建产物"""
        print("=== 清理构建产物 ===")

        # 清理版本对应的 src 目录
        if self.src_dir.exists():
            shutil.rmtree(self.src_dir)
            print(f"  已删除: {self.src_dir}")

        # 清理 api 目录下的旧产物（保留 __init__.py 和 __pycache__）
        if self.api_dir.exists():
            for pattern in ["_thost*.so*", "thost*.py"]:
                for f in self.api_dir.glob(pattern):
                    f.unlink()
                    print(f"  已删除: {f}")

    def run_swig(self, swig_file: str, module: str):
        """运行 SWIG 生成 C++ 包装代码"""
        out_cpp = self.src_dir / f"{module}_wrap.cpp"

        cmd = [
            "swig",
            "-c++",
            "-python",
            "-threads",
            f"-I{self.include_dir}",
            "-outdir", str(self.src_dir),
            "-o", str(out_cpp),
            str(self.interface_dir / swig_file),
        ]

        print(f"\n[SWIG] {module} <- {swig_file}")
        print(f"       {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print(f"       生成: {out_cpp.name}")

    def compile(self, module: str) -> Path:
        """编译 C++ 源文件为 .o"""
        src = self.src_dir / f"{module}_wrap.cpp"
        obj = self.src_dir / f"{module}_wrap.o"

        cmd = [
            "g++",
            "-c",
            "-fPIC",
            "-O2",
            "-std=c++11",
            f"-I{self.include_dir}",
            f"-I{self.python_include}",
            str(src),
            "-o", str(obj),
        ]

        print(f"\n[CC]   {src.name}")
        subprocess.run(cmd, check=True)
        return obj

    def link(self, module: str, lib_name: str, obj: Path):
        """链接生成 Python 扩展 .so"""
        so_name = f"_{module}.so"
        so_path = self.api_dir / so_name
        ctp_lib = self.libs_dir / f"{lib_name}.so"

        if not ctp_lib.exists():
            raise FileNotFoundError(f"CTP 库文件不存在: {ctp_lib}")

        cmd = [
            "g++",
            "-shared",
            "-fPIC",
            str(obj),
            str(ctp_lib),
            "-lboost_locale",                       # mdapi.i 中使用了 boost::locale
            f"-Wl,-rpath,{self.libs_dir}",          # 运行时自动找到 v/{version}/libs/ 下的依赖库
            "-o", str(so_path),
        ]

        print(f"\n[LD]   {so_name}")
        print(f"       链接库: {ctp_lib}")
        subprocess.run(cmd, check=True)
        print(f"       输出: {so_path}")

    def install_py(self, module: str):
        """将 SWIG 生成的 .py shadow 文件安装到 api/ 目录"""
        src_py = self.src_dir / f"{module}.py"
        dst_py = self.api_dir / f"{module}.py"

        if src_py.exists():
            shutil.copy2(src_py, dst_py)
            print(f"\n[INSTALL] {src_py.name} -> {dst_py}")

    def build(self):
        """完整构建流程"""
        print(f"{'='*50}")
        print(f"开始构建 CTP API")
        print(f"版本: {self.version}")
        print(f"Python: {self.py_ver}")
        print(f"{'='*50}")

        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.api_dir.mkdir(parents=True, exist_ok=True)

        for swig_file, module, lib_name in self.interfaces:
            self.run_swig(swig_file, module)
            obj = self.compile(module)
            self.link(module, lib_name, obj)
            self.install_py(module)

        print(f"\n{'='*50}")
        print("构建完成")
        print(f"扩展模块: {self.api_dir}/_thost*.so")
        print(f"Python 包装: {self.api_dir}/thost*.py")
        print(f"{'='*50}")


def list_versions(root: Path) -> list:
    """列出可用版本"""
    v_dir = root / "v"
    if not v_dir.exists():
        return []
    return sorted([d.name for d in v_dir.iterdir() if d.is_dir()])


def main():
    root = Path(__file__).parent.resolve()

    if len(sys.argv) < 2:
        versions = list_versions(root)
        print("用法:")
        print(f"  python wrapper.py <version>    # 编译指定版本")
        print(f"  python wrapper.py clean        # 清理构建产物")
        print(f"\n可用版本:")
        for v in versions:
            print(f"  - {v}")
        sys.exit(0)

    command = sys.argv[1]

    if command == "clean":
        # 清理所有版本的 src 和 api 下的产物
        print("=== 全局清理 ===")
        v_dir = root / "v"
        if v_dir.exists():
            for d in v_dir.iterdir():
                if d.is_dir():
                    src = d / "src"
                    if src.exists():
                        shutil.rmtree(src)
                        print(f"  已删除: {src}")

        api_dir = root / "api"
        if api_dir.exists():
            for pattern in ["_thost*.so*", "thost*.py"]:
                for f in api_dir.glob(pattern):
                    f.unlink()
                    print(f"  已删除: {f}")
        print("清理完成")
        return

    # 构建指定版本
    wrapper = CtpWrapper(command)
    wrapper.build()


if __name__ == "__main__":
    main()