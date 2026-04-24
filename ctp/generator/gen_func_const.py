"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import datetime
import re
from pathlib import Path
import argparse
import os

from gen_util import underscore_to_camelcase, camel_to_underscore_upper


class GeneratorFunctionConst:
    def __init__(self, filename: str, prefix: str, name: str, class_name: str) -> None:
        self.filename = filename
        self.prefix = prefix
        self.name = name
        self.class_name = class_name
        self.file_cpp = None
        self.function_names = ["Exit"]

    def run(self):
        print(f"  解析 {self.name.upper()} 函数...")
        self.file_cpp = open(self.filename, encoding='gbk')
        for line in self.file_cpp:
            func_name = self.process_function_name(line)
            if func_name and func_name not in self.function_names:
                self.function_names.append(func_name)
        self.file_cpp.close()

    @staticmethod
    def process_function_name(line: str) -> str | None:
        if line and isinstance(line, str):
            translator = str.maketrans('', '', ';\n\t')
            line = line.translate(translator).replace("{}", "")
            stripped = line.strip()
            no_forbidden = not re.search(r"virtual void On|virtual int Req", stripped)
            has_required = re.search(r"static|virtual", stripped) is not None
            if no_forbidden and has_required:
                newline = stripped[0:stripped.index("(")]
                normalized = ' '.join(newline.split())
                last_space = normalized.rfind(' ')
                func_part = normalized[last_space + 1:].strip().replace('*', '')
                return func_part

    def write_file(self):
        func_filename = f"{self.prefix}_func_const.py"
        camel_name = underscore_to_camelcase(f"{self.prefix}_func_const")
        funcs_path = Path(func_filename)

        if self.name == "md":
            if funcs_path.exists():
                funcs_path.unlink()
            with open(func_filename, "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env python\n")
                f.write("# -*- coding: utf-8 -*-\n")
                f.write(f'"""\n@Description: {self.prefix} md和td基础函数名称文件\n"""\n\n\n')
                f.write(f"class {camel_name}:\n")
                f.write("\t# 原有函数名\n")
                for func_name in self.function_names:
                    upper = camel_to_underscore_upper(func_name)
                    f.write(f"\t{upper}: str = \"{func_name}\"\n")
                f.write("\n")
            print(f"  {func_filename} 生成完毕")
        else:
            if not funcs_path.exists():
                return
            with open(func_filename, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'class CtpFuncConst:' not in content:
                print("  类 CtpFuncConst 不存在")
                return
            existing = re.findall(r'(\w+): str = "([^"]+)"', content)
            existing_vals = [v for _, v in existing]
            with open(func_filename, "a", encoding="utf-8") as f:
                f.write("\t# 新增函数名\n")
                for func_name in self.function_names:
                    if func_name not in existing_vals:
                        upper = camel_to_underscore_upper(func_name)
                        f.write(f"\t{upper}: str = \"{func_name}\"\n")
            print(f"  {func_filename} 写入完毕")


def main(include_dir='../include', output_dir='../src'):
    md = GeneratorFunctionConst(os.path.join(include_dir, "ThostFtdcMdApi.h"), "ctp", "md", "MdApi")
    md.run()
    md.write_file()
    td = GeneratorFunctionConst(os.path.join(include_dir, "ThostFtdcTraderApi.h"), "ctp", "td", "TdApi")
    td.run()
    td.write_file()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-dir', default='../include')
    parser.add_argument('--output-dir', default='../src')
    args = parser.parse_args()
    main(args.include_dir, args.output_dir)