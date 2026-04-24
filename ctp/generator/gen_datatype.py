"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import re
from pathlib import Path
import argparse
import os

TYPE_CPP2PY = {
    "int": "int",
    "char": "char",
    "double": "double",
    "short": "int",
}


class DataTypeGenerator:
    def __init__(self, filename: str, prefix: str) -> None:
        self.filename = filename
        self.prefix = prefix
        self.f_cpp = None
        self.f_define = None
        self.f_typedef = None
        self.in_enum = False
        self.enum_content = []
        self.in_multiline_comment = False
        self.brace_count = 0

    def run(self) -> None:
        print("  生成 DataType...")
        current_file = Path(__file__).resolve()
        parent_path = current_file.parent.parent

        self.f_cpp = open(self.filename, encoding='gbk')
        self.f_define = open(f"{str(parent_path)}/{self.prefix}_constant.py", "w")
        self.f_typedef = open(f"{str(parent_path)}/{self.prefix}_typedef.py", "w")

        for line in self.f_cpp:
            self.process_line(line)

        self.f_cpp.close()
        self.f_define.close()
        self.f_typedef.close()
        print("  DataType生成完毕")

    def process_line(self, line: str) -> None:
        if self.in_multiline_comment:
            if '*/' in line:
                line = line[line.find('*/') + 2:]
                self.in_multiline_comment = False
            else:
                return

        if '//' in line:
            line = line.split('//')[0]
            if '/*' in line:
                if '*/' in line:
                    line = line[:line.find('/*')] + line[line.find('*/') + 2:]
                else:
                    line = line[:line.find('/*')]
                    self.in_multiline_comment = True

        line = line.replace("\n", "").replace(";", "").strip()

        if line.startswith("#define"):
            self.process_define(line)
        elif line.startswith("typedef"):
            self.process_typedef(line)
        else:
            self.process_enum(line)

    def process_define(self, line: str) -> None:
        words = [w for w in line.split(" ") if w]
        if len(words) < 3:
            return
        self.f_define.write(f"{words[1]} = {words[2]}\n")

    def process_typedef(self, line: str) -> None:
        words = [w for w in line.split(" ") if w != " "]
        name = words[2]
        typedef = TYPE_CPP2PY[words[1]]
        if typedef == "char" and "[" in name:
            typedef = "string"
            name = name[:name.index("[")]
        self.f_typedef.write(f'{name} = "{typedef}"\n')

    def process_enum(self, line: str) -> None:
        if not self.in_enum and re.match(r'^\s*enum\s+\w+', line):
            self.in_enum = True
            self.brace_count = 0
            self.enum_content = []

        if self.in_enum:
            self.brace_count += line.count('{')
            self.brace_count -= line.count('}')
            self.enum_content.append(line)
            if self.brace_count <= 0 and '}' in line:
                self.in_enum = False
                self.parse_enum_content(' '.join(self.enum_content))

    def parse_enum_content(self, enum_text) -> None:
        match = re.search(r'\{(.*?)}', enum_text, re.DOTALL)
        if not match:
            return
        inner = match.group(1).strip()
        if not inner:
            return
        current = 0
        for part in inner.split(','):
            part = part.strip()
            if not part:
                continue
            m = re.match(r'(\w+)(?:\s*=\s*(\d+))?', part)
            if m:
                name, val = m.groups()
                if val:
                    current = int(val)
                self.f_define.write(f"{name} = {current}\n")
                current += 1


def main(include_dir='../include', output_dir='../src'):
    generator = DataTypeGenerator(os.path.join(include_dir, "ThostFtdcUserApiDataType.h"), "ctp")
    generator.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-dir', default='../include')
    parser.add_argument('--output-dir', default='../src')
    args = parser.parse_args()
    main(args.include_dir, args.output_dir)