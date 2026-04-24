"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import argparse
import glob
import os
import subprocess
import sys


def delete_ctp_files(dirs):
    for d in dirs:
        if not os.path.exists(d):
            continue
        pattern = os.path.join(d, "ctp_*")
        for f in glob.glob(pattern):
            if os.path.isfile(f):
                try:
                    os.remove(f)
                    print(f"已删除: {f}")
                except Exception as e:
                    print(f"删除失败 {f}: {e}")


def run_step(script_name, include_dir, output_dir, error_message):
    """执行单个生成步骤，自动传递路径参数"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, script_name)

    if not os.path.exists(script_path):
        print(f"找不到脚本: {script_path}")
        sys.exit(1)

    try:
        result = subprocess.run([
            sys.executable, script_path,
            '--include-dir', include_dir,
            '--output-dir', output_dir
        ], cwd=script_dir)
        if result.returncode != 0:
            print(error_message)
            sys.exit(1)
    except Exception as e:
        print(f"执行 {script_name} 时发生错误: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='生成 CTP C++ 绑定代码')
    parser.add_argument('--include-dir', default='../include')
    parser.add_argument('--output-dir', default='../src')
    args = parser.parse_args()

    include_dir = args.include_dir
    output_dir = args.output_dir
    generator_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"头文件目录: {include_dir}")
    print(f"输出目录: {output_dir}")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'ctpmd'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'ctptd'), exist_ok=True)

    delete_ctp_files([generator_dir, output_dir])

    steps = [
        ('gen_func_const.py', "生成 API 函数常量文件失败"),
        ('gen_datatype.py', "生成 API DataType 文件失败"),
        ('gen_struct.py', "生成 API 结构体文件失败"),
        ('gen_func.py', "生成 API 函数文件失败"),
        ('gen_cpp.py', "生成 API cpp、h 文件失败")
    ]

    for script_name, error_message in steps:
        run_step(script_name, include_dir, output_dir, error_message)

    delete_ctp_files([generator_dir, output_dir])
    print("\n所有生成步骤已完成")


if __name__ == '__main__':
    main()