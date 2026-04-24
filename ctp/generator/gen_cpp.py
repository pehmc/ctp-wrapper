"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

from pathlib import Path
from typing import List
import argparse
import os
import jinja2

from gen_util import create_output_dir


class GenerateCpp:
    def __init__(self, filename: str, prefix: str, name: str, output_dir: str = '../src'):
        self.filename = filename
        self.prefix = prefix
        self.name = name
        self.output_dir = output_dir

        if self.name == "md":
            self.class_name = "MdApi"
            self.full_class_name = "CThostFtdcMdSpi"
            self.api_type = "CThostFtdcMdApi"
            self.module_name = "ctpmd"
            self.pybind_var = "mdapi"
        else:
            self.class_name = "TdApi"
            self.full_class_name = "CThostFtdcTraderSpi"
            self.api_type = "CThostFtdcTraderApi"
            self.module_name = "ctptd"
            self.pybind_var = "tdApi"

        self.h_filename = Path(self.filename).name
        self.file_prefix = f"{self.prefix}{self.name}"
        self.output_filename = f"{self.file_prefix}.cpp"
        self.output_header_filename = f"{self.file_prefix}.h"

        self.header_files = {
            'define': f'{self.prefix}_{self.name}_header_define.h',
            'function': f'{self.prefix}_{self.name}_header_function.h',
            'on': f'{self.prefix}_{self.name}_header_on.h',
            'process': f'{self.prefix}_{self.name}_header_process.h'
        }

        self.source_files = {
            'task': f'{self.prefix}_{self.name}_source_task.cpp',
            'switch': f'{self.prefix}_{self.name}_source_switch.cpp',
            'process': f'{self.prefix}_{self.name}_source_process.cpp',
            'function': f'{self.prefix}_{self.name}_source_function.cpp',
            'on': f'{self.prefix}_{self.name}_source_on.cpp',
            'module': f'{self.prefix}_{self.name}_source_module.cpp'
        }
        
        self.jinja_env = jinja2.Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        self._load_templates()

    def _load_templates(self):
        template_dir = Path(__file__).parent / "templates"
        if not template_dir.exists():
            raise RuntimeError(f"模板目录不存在: {template_dir}")
        self.jinja_env.loader = jinja2.FileSystemLoader(str(template_dir))
        self.header_template = self.jinja_env.get_template("ctp_header.j2")
        self.source_template = self.jinja_env.get_template("ctp_source.j2")

    @staticmethod
    def read_file_content(filename: str) -> str:
        try:
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()
        except Exception as e:
            print(f"读取文件 {filename} 失败: {e}")
            return ""
    
    def extract_virtual_functions_from_header(self, header_file_path: str, class_name: str) -> str:
        try:
            content = self.read_file_content(header_file_path)
            if not content:
                return ""
            class_start = content.find(f"class {class_name}")
            if class_start == -1:
                return ""
            brace_count = 0
            class_body_start = content.find("{", class_start)
            if class_body_start == -1:
                return ""
            class_end = class_body_start
            for i in range(class_body_start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        class_end = i
                        break
            class_body = content[class_body_start+1:class_end]
            virtual_functions = []
            lines = class_body.split('\n')
            current_function = ""
            in_function = False
            for line in lines:
                line = line.strip()
                if line.startswith('//') or line.startswith('/*') or line.startswith('*'):
                    continue
                if line.startswith('virtual') and '(' in line:
                    in_function = True
                    current_function = line
                    if ';' in line:
                        if '{' in current_function:
                            current_function = current_function[:current_function.find('{')].strip()
                        if current_function.endswith('{}'):
                            current_function = current_function[:-2].strip()
                        if current_function.endswith(';'):
                            current_function = current_function[:-1].strip()
                        virtual_functions.append(current_function + ';')
                        in_function = False
                        current_function = ""
                elif in_function:
                    current_function += " " + line
                    if ';' in line:
                        if '{' in current_function:
                            current_function = current_function[:current_function.find('{')].strip()
                        if current_function.endswith('{}'):
                            current_function = current_function[:-2].strip()
                        if current_function.endswith(';'):
                            current_function = current_function[:-1].strip()
                        virtual_functions.append(current_function + ';')
                        in_function = False
                        current_function = ""
            if virtual_functions:
                return '\n\n'.join('\t' + f.strip() for f in virtual_functions if f.strip())
            else:
                print(f"警告：无法从 {header_file_path} 提取虚函数")
                return ""
        except Exception as e:
            print(f"解析头文件 {header_file_path} 时出错: {e}")
            return ""

    @staticmethod
    def format_switch_case(case_content: str) -> str:
        lines = case_content.split('\n')
        formatted = []
        for line in lines:
            line = line.rstrip()
            if line.startswith('case '):
                formatted.append('\t\t\t' + line)
            elif line in ('{', '}'):
                formatted.append('\t\t\t' + line)
            elif line.strip() == 'break;':
                formatted.append('\t\t\t\t' + 'break;')
            elif line.strip().startswith('this->'):
                formatted.append('\t\t\t\t' + line.strip())
            elif line.strip() == '':
                formatted.append('')
            else:
                formatted.append('\t\t\t\t' + line.strip() if line.strip() else '')
        return '\n'.join(formatted)
    
    def _indent(self, content: str, level: int = 1) -> str:
        indent = '\t' * level
        return '\n'.join(indent + line if line.strip() else line for line in content.split('\n'))

    def generate_header_file(self) -> str:
        defines = self.read_file_content(self.header_files['define'])
        virtual_functions = self.extract_virtual_functions_from_header(self.filename, self.full_class_name)
        return self.header_template.render(
            h_filename=self.h_filename,
            defines=defines,
            class_name=self.class_name,
            base_class_name=self.full_class_name,
            api_type=self.api_type,
            virtual_functions=virtual_functions,
            process_declarations=self._indent(self.read_file_content(self.header_files['process']), 1),
            on_declarations=self._indent(self.read_file_content(self.header_files['on']), 1),
            function_declarations=self._indent(self.read_file_content(self.header_files['function']), 1),
        )

    def generate_cpp_file(self) -> str:
        module_content = self.read_file_content(self.source_files['module'])
        module_lines = module_content.split('\n')
        formatted_module = []
        for line in module_lines:
            if line.strip().startswith('.def'):
                formatted_module.append('\t\t' + line.strip())
            elif line.strip() == ';':
                formatted_module.append('\t\t' + line.strip())
            else:
                formatted_module.append('\t' + line.strip())
        return self.source_template.render(
            file_prefix=self.file_prefix,
            class_name=self.class_name,
            task_content=self.read_file_content(self.source_files['task']),
            switch_content=self.format_switch_case(self.read_file_content(self.source_files['switch'])),
            process_content=self.read_file_content(self.source_files['process']),
            function_content=self.read_file_content(self.source_files['function']),
            on_content=self._indent(self.read_file_content(self.source_files['on']), 1),
            module_content='\n'.join(formatted_module),
            module_name=self.module_name,
            pybind_var=self.pybind_var,
        )

    def fix_encoding_and_format(self, content: str) -> str:
        replacements = {
            "constants ": "const ",
            "void::": f"CThostFtdc{self.class_name}::",
            "\t    ": "\t",
            "    \t": "\t",
        }
        for old, new in replacements.items():
            content = content.replace(old, new)
        return content
    
    def assemble(self) -> None:
        output_path = create_output_dir(self.output_dir, self.file_prefix)
        if not output_path:
            print(f"无法创建输出目录{self.file_prefix}，终止生成")
            return

        header_content = self.fix_encoding_and_format(self.generate_header_file())
        cpp_content = self.fix_encoding_and_format(self.generate_cpp_file())
        
        try:
            with open(f"{output_path}/{self.output_header_filename}", 'w', encoding='gb2312') as f:
                f.write(header_content)
            print(f"  成功生成头文件: {output_path}/{self.output_header_filename}")
        except Exception as e:
            print(f"  写入头文件失败: {e}")
            
        try:
            with open(f"{output_path}/{self.output_filename}", 'w', encoding='gb2312') as f:
                f.write(cpp_content)
            print(f"  成功生成CPP文件: {output_path}/{self.output_filename}")
        except Exception as e:
            print(f"  写入CPP文件失败: {e}")
    
    def check_required_files(self) -> List[str]:
        missing = []
        for name, filename in self.header_files.items():
            if not os.path.exists(filename):
                missing.append(f"头文件: {filename}")
        for name, filename in self.source_files.items():
            if not os.path.exists(filename):
                missing.append(f"源文件: {filename}")
        return missing
    
    def run(self):
        print(f"  生成 {self.name.upper()} cpp、h 文件...")
        missing = self.check_required_files()
        if missing:
            print("  错误：以下必要文件不存在：")
            for file in missing:
                print(f"    - {file}")
            return
        self.assemble()


def main(include_dir='../include', output_dir='../src'):
    md = GenerateCpp(os.path.join(include_dir, "ThostFtdcMdApi.h"), "ctp", "md", output_dir)
    md.run()
    td = GenerateCpp(os.path.join(include_dir, "ThostFtdcTraderApi.h"), "ctp", "td", output_dir)
    td.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-dir', default='../include')
    parser.add_argument('--output-dir', default='../src')
    args = parser.parse_args()
    main(args.include_dir, args.output_dir)