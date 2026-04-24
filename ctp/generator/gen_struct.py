"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import importlib
import argparse
import os
import sys
from pathlib import Path


class StructGenerator:
    def __init__(self, filename: str, prefix: str, typedefs: dict = None) -> None:
        self.filename = filename
        self.prefix = prefix
        self.typedefs = typedefs or {}
        self.f_cpp = None
        self.f_struct = None

        if not self.typedefs:
            self.load_constant()

    def load_constant(self) -> None:

        root_dir = Path(__file__).parent.parent
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))

        module = importlib.import_module(f"{self.prefix}_typedef")
        for name in dir(module):
            if "__" not in name:
                self.typedefs[name] = getattr(module, name)

    def run(self) -> None:
        print("  生成 Struct...")
        current_file = Path(__file__).resolve()
        parent_path = current_file.parent.parent

        self.f_cpp = open(self.filename, encoding='gbk')
        self.f_struct = open(f"{str(parent_path)}/{self.prefix}_struct.py", "w")

        for line in self.f_cpp:
            self.process_line(line)

        self.f_cpp.close()
        self.f_struct.close()
        print("  Struct生成完毕")

    def process_line(self, line: str) -> None:
        line = line.replace(";", "").replace("\n", "")

        if line.startswith("struct"):
            self.process_declare(line)
        elif line.startswith("{"):
            pass
        elif line.startswith("}"):
            self.process_end()
        elif "\t" in line and "///" not in line:
            self.process_member(line)

    def process_declare(self, line: str) -> None:
        words = line.split(" ")
        name = words[1]
        self.f_struct.write(f"{name} = {{\n")

    def process_end(self) -> None:
        self.f_struct.write("}\n\n")

    def process_member(self, line: str) -> None:
        words = line.split("\t")
        words = [w for w in words if w]

        if len(words) == 1:
            words = line.split()
            words = [w for w in words if w]

        if len(words) < 2:
            return

        type_name = words[0]
        field_name = words[-1]

        if type_name not in self.typedefs:
            print(f"    Warning: Unknown type '{type_name}' in line: {line.strip()}")
            return

        py_type = self.typedefs[type_name]
        self.f_struct.write(f'    "{field_name}": "{py_type}",\n')


def main(include_dir='../include', output_dir='../src'):
    generator = StructGenerator(os.path.join(include_dir, "ThostFtdcUserApiStruct.h"), "ctp")
    generator.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-dir', default='../include')
    parser.add_argument('--output-dir', default='../src')
    args = parser.parse_args()
    main(args.include_dir, args.output_dir)