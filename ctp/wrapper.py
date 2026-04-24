"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

# 项目根目录（脚本所在目录）
ROOT = Path(__file__).parent.resolve()
# meson build dir
build_dir = ROOT / ".build"

def run(cmd, cwd=None, env=None, check=True):
    """统一命令执行，带日志输出"""
    cmd_str = ' '.join(str(c) for c in cmd)
    ret = subprocess.run(cmd, cwd=cwd, env=env)
    if check and ret.returncode != 0:
        raise RuntimeError(f"[x] 命令失败: {cmd_str}")
    return ret


def check_environment(version_dir: Path):
    """统一环境检查"""
    print("[1/5] 环境检查")
    if sys.version_info < (3, 10):
        raise RuntimeError(f"[!] 需要 Python >= 3.10，当前: {sys.version}")

    if not version_dir.exists():
        raise RuntimeError(
            f"[x] 版本目录不存在: {version_dir}\n"
            f"[x] 请确认 {ROOT / 'v'}/ 目录下有该版本"
        )

    libs_dir = version_dir / "libs"
    for lib in ["thostmduserapi_se.so", "thosttraderapi_se.so"]:
        if not (libs_dir / lib).exists():
            raise RuntimeError(f"[x] 缺少 CTP 动态库: {libs_dir / lib}")

    try:
        __import__("mesonbuild")
    except ImportError:
        ret = subprocess.run(["meson", "--version"], capture_output=True)
        if ret.returncode != 0:
            raise RuntimeError("[x] 未找到 meson，请安装: pip install meson-python")

    deps = {
        "pybind11": "pybind11",
        "pybind11_stubgen": "pybind11_stubgen"
    }
    for mod, pkg in deps.items():
        try:
            __import__(mod)
        except ImportError:
            print(f"[*] 安装依赖: {pkg}")
            run([sys.executable, "-m", "pip", "install", pkg])

    if sys.prefix == sys.base_prefix:
        print("[!] 未检测到虚拟环境，建议激活 .venv")

    print("[*] 环境检查通过")


def generate_bindings(version: str, version_dir: Path):
    """生成 C++ 绑定代码"""
    print("\n[2/5] 生成 C++ 绑定代码")
    generator = ROOT / "generator" / "gen.py"
    if not generator.exists():
        raise RuntimeError(f"[x] 未找到生成器脚本: {generator}")

    run([
        sys.executable, str(generator),
        f"--include-dir={version_dir / 'include'}",
        f"--output-dir={version_dir / 'src'}"
    ])
    print("[*] 绑定代码生成完成")


def meson_build(version: str, clean: bool = False):
    """Meson 编译（setup + compile）"""
    print("\n[3/5] Meson 编译")
    
    if clean and build_dir.exists():
        shutil.rmtree(build_dir)
        print("[*] 已清理 .build/ 目录")

    env = os.environ.copy()
    env["CTP_VERSION"] = version

    if not (build_dir / "build.ninja").exists():
        run(["meson", "setup", str(build_dir)], cwd=ROOT, env=env)

    run(["meson", "compile", "-C", str(build_dir)], cwd=ROOT, env=env)
    print("[*] 编译完成")


def install_artifacts(version: str, version_dir: Path):
    """
    整理产物到 api/
    注意：meson 仅负责编译（install: false），所有产物复制/移动由本函数完成
    """
    print("\n[4/5] 整理产物到 api/")
    api_dir = ROOT / "api"
    api_dir.mkdir(exist_ok=True)

    init_file = api_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# CTP API package\n", encoding="utf-8")

    root_init = ROOT / "__init__.py"
    if not root_init.exists():
        root_init.write_text("# CTP package\n", encoding="utf-8")

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX") or ".so"

    # 复制扩展模块（meson compile 产物位于 .build/ 根目录）
    for mod_name in ["ctpmd", "ctptd"]:
        so_name = f"{mod_name}{ext_suffix}"
        src = build_dir / so_name

        if not src.exists():
            # 兜底：处理可能的命名差异
            pattern = build_dir / f"{mod_name}*.so*"
            found = glob.glob(str(pattern))
            if found:
                src = Path(found[0])

        if src.exists():
            dst = api_dir / so_name
            shutil.copy2(src, dst)
            print(f"[*] 已复制: {so_name}")
        else:
            raise RuntimeError(f"[x] 未找到 {mod_name} 构建产物: {build_dir / so_name}")

    # 复制 CTP 官方动态库（与扩展同目录，RPATH=$ORIGIN 确保运行时加载）
    lib_dir = version_dir / "libs"
    for lib in ["thostmduserapi_se.so", "thosttraderapi_se.so"]:
        src = lib_dir / lib
        if src.exists():
            dst = api_dir / lib
            shutil.copy2(src, dst)
            print(f"[*] 已复制: {lib}")
        else:
            raise RuntimeError(f"[x] 未找到官方库: {lib}")

    # 移动 generator 生成的 Python 常量文件到 api/
    for py_file in ["ctp_constant.py", "ctp_struct.py", "ctp_typedef.py"]:
        src = ROOT / py_file
        if src.exists():
            dst = api_dir / py_file
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            print(f"[*] 已移动: {py_file}")


def generate_stubs():
    """生成 .pyi 类型提示文件"""
    print("\n[5/5] 生成类型存根 (.pyi)")
    env = os.environ.copy()
    parent_dir = str(ROOT.parent)
    env["PYTHONPATH"] = parent_dir + os.pathsep + env.get("PYTHONPATH", "")

    for mod_base in ["ctp.api.ctpmd", "ctp.api.ctptd"]:
        print(f"[*] 生成: {mod_base}")
        ret = subprocess.run([
            sys.executable, "-m", "pybind11_stubgen",
            "-o=.", mod_base
        ], cwd=parent_dir, env=env)
        if ret.returncode != 0:
            print(f"[x] {mod_base} 存根生成失败，可稍后手动执行")

    print("[*] 存根生成完成")


def main():
    parser = argparse.ArgumentParser(
        description="CTP Python API 封装脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python gen.py --version v6.7.13             # 完整构建
  python gen.py --version v6.7.13 --clean     # 清理后重新构建
  python gen.py --skip-generate               # 跳过代码生成（仅编译）
  python gen.py --only-stubs                  # 仅重新生成存根
        """
    )
    parser.add_argument(
        "--version",
        default="v6.7.13",
        help="CTP 版本目录名，如 v6.7.13 (默认: v6.7.13)"
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="跳过 C++ 绑定代码生成（仅编译）"
    )
    parser.add_argument(
        "--skip-stubs",
        action="store_true",
        help="跳过 .pyi 存根生成"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="清理 .build/ 后重新构建"
    )
    parser.add_argument(
        "--only-stubs",
        action="store_true",
        help="仅重新生成存根文件（不编译）"
    )

    args = parser.parse_args()
    version = args.version
    version_dir = ROOT / "v" / version

    if args.only_stubs:
        try:
            generate_stubs()
            print("\n[*] 存根生成完成")
        except Exception as e:
            print(f"\n[x] 错误: {e}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        check_environment(version_dir)

        if not args.skip_generate:
            generate_bindings(version, version_dir)

        meson_build(version, clean=args.clean)
        install_artifacts(version, version_dir)

        if not args.skip_stubs:
            generate_stubs()

        print(f"\n构建成功 | 版本: {version}")
        print(f"产物路径: {ROOT / 'api'}")
        print("使用方式: from ctp.api import ctpmd, ctptd")

    except RuntimeError as e:
        print(f"\n[x] 错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[!] 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[x] 未预期错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()