"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import sys
from pathlib import Path
import importlib
import re
import argparse
import os

from ctp_func_const import CtpFuncConst  # noqa
from gen_util import replace_function_name, process_func_type, format_pointer_arg, format_equal_arg


class GenerateApiFunc:
    """API生成器"""
    def __init__(self, filename: str, prefix: str, name: str, class_name: str) -> None:
        self.filename: str = filename  
        self.prefix: str = prefix  # "ctp"或"tts"
        self.name: str = name  # "md"或"td"
        self.class_name: str = class_name  # "MdApi"或"TdApi"

        self.f_cpp = None
        self.callbacks: dict[str, dict[str, str]] = {}  # 回调函数
        self.functions: dict[str, dict[str, str | dict[str, str]]] = {}  # 函数
        self.source_functions: dict[str, dict[str, str | dict[str, str]]] = {}  # source 函数
        self.lines: dict[str, str] = {}
        self.structs: dict[str, dict[str, str]] = {}
        self.function_names: list = []
        self.load_struct()

    def load_struct(self) -> None:
        """加载Struct"""
        root_dir = Path(__file__).parent.parent
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))

        module_name = f"{self.prefix}_struct"
        module = importlib.import_module(module_name)

        for name in dir(module):
            if "__" not in name:
                self.structs[name] = getattr(module, name)

    def run(self) -> None:
        """运行"""
        print("生成API函数文件")
        self.f_cpp = open(self.filename, encoding='gbk')

        for line in self.f_cpp:
            self.process_line(line)

        self.f_cpp.close()

        self.generate_header_define()  # callbacks
        self.generate_header_process()  # callbacks
        self.generate_header_on()  # callbacks
        self.generate_header_function()  # functions

        self.generate_source_task()  # callbacks
        self.generate_source_switch()  # callbacks
        self.generate_source_process()  # callbacks
        self.generate_source_function()  # source_functions
        self.generate_source_on()  # callbacks
        self.generate_source_module()  # functions and callbacks

        print(f"{self.prefix} {self.name} API生成成功")

    def process_line(self, line: str) -> None:
        """处理每行"""
        if not isinstance(line, str):
            return

        # 使用translate高效删除字符
        # 一次操作移除;、\n、\t
        translator = str.maketrans('', '', ';\n\t')
        line = line.translate(translator)

        # 移除 "{}"
        line = line.replace("{}", "")
        stripped_line = line.strip()

        if "virtual void On" in stripped_line:
            self.process_callback(line)  # 处理回调函数
        elif "virtual int Req" in stripped_line:
            self.process_function(line)  # 处理请求函数
        elif "static" in stripped_line or "virtual" in stripped_line:
            self.process_function(line)  # 处理其他函数

    @staticmethod
    def _process_function_type(type_and_func: str) -> tuple[str, str]:
        """处理函数类型"""
        # 输入验证
        if not isinstance(type_and_func, str):
            return '', ''

        # 提前过滤不匹配的行
        if not any(keyword in type_and_func for keyword in
                   ["virtual void On", "virtual int Req", "static", "virtual"]):
            return '', ''

        # 第一步：标准化空格（保留单词间单个空格）
        normalized = ' '.join(type_and_func.split())

        # 第二步：查找最后一个空格的位置
        last_space_index = normalized.rfind(' ')

        if last_space_index == -1:
            # 如果没有空格，整个字符串作为函数名部分
            return '', normalized

        # 特殊处理：RegisterSpi 函数替换为 Exit 函数
        if normalized.startswith("virtual void RegisterSpi"):
            return 'int', 'Exit'

        # 第三步：截取最后一个空格位置前后的字符串
        type_part = normalized[:last_space_index].strip()
        func_part = normalized[last_space_index + 1:].strip()

        # 去掉开头的 virtual 或 static 关键字及后面的空格（支持多个关键字）
        type_part = re.sub(r'^\s*(virtual|static)\s+', '', type_part)
        # 下方改进了正则表达式：使用 (?:(?:virtual|static)\s+)+ 来处理多个连续的关键字，但未测试
        # type_part = re.sub(r'^\s*(?:(?:virtual|static)\s+)+', '', type_part)

        # 将 const char 类型替换为 string
        if 'const char' in type_part:
            type_part = type_part.replace('const char', 'string')

        return type_part, func_part


    def process_callback(self, line: str) -> None:
        """
        处理回调函数定义，提取函数名和参数信息并存储到相应的字典中
        """
        try:
            # 从行中提取回调函数名（从"On"开始到"("结束）
            name = line[line.index("On"):line.index("(")]
            self.lines[name] = line

            # 生成回调函数参数字典并存储
            d = self.generate_arg_dict(line)
            self.callbacks[name] = d
        except ValueError:
            # Handle case where "On" or "(" is not found in line
            pass

    def process_function(self, line: str) -> None:
        """处理基础主动函数
        """
        # 从行中提取函数名，截取开头到"("之间的内容
        if not line or "(" not in line or ")" not in line:
            return

        try:
            newline = line[:line.index("(")]
            type_part, func_part = self._process_function_type(newline)

            if not type_part and not func_part:
                return

            if func_part.startswith("*"):
                func_part = func_part[1:]

            self.functions[func_part] = { "func_type": type_part}

            # 生成函数参数字典并存储到functions属性中
            func_args = self.generate_arg_dict(line)

            self.functions[func_part]['func_args'] = func_args
        except ValueError:
            # 处理line.index("(")可能抛出的异常
            return

    @staticmethod
    def generate_arg_dict(line: str) -> dict[str, str]:
        """
        生成参数字典
        从给定的字符串中解析出函数参数，并构建参数名到参数类型的映射字典
        """
        # 提取括号内的参数字符串
        args_str = line[line.index("(") + 1:line.index(")")]
        if not args_str.strip():
            return {}

        args = args_str.split(",")

        # 解析每个参数，构建参数名到参数类型的映射，例如 {'bIsProductionMode=true': 'bool'}
        func_args: dict[str, str] = {}
        for arg in args:
            arg = format_equal_arg(arg)  # 统一等号前后空格处理
            arg = ' '.join(arg.split())   # 移除多余空格
            arg = format_pointer_arg(arg)  # 确保 * 紧贴变量名，但与类型之间有空格，保证格式的统一

            words = arg.split(" ")
            words = [word for word in words if word]  # 保留非空字符串

            if len(words) == 2:  # 参数有两个字符串，例如：CThostFtdcDepthMarketDataField *pDepthMarketData
                param_name = words[1].replace("*", "")
                param_type = words[0]
                func_args[param_name] = param_type
            elif len(words) == 3:  # 参数有三个字符串，例如：const char *pszFlowPath
                param_name = words[2].replace("*", "")
                param_type = words[0] + " " + words[1]
                func_args[param_name] = param_type
            else:
                continue  # 忽略非法格式参数
        return func_args

    def generate_header_define(self) -> None:
        """
        生成头文件定义

        该函数创建一个头文件，其中包含回调函数名称到数字索引的宏定义映射。
        每个回调函数名被转换为大写并定义为对应的数字值。
        """
        filename = f"{self.prefix}_{self.name}_header_define.h"
        with open(filename, "w") as f:
            for n, name in enumerate(self.callbacks.keys()):
                line = f"#define {name.upper()} {n}\n"
                f.write(line)

    def generate_header_process(self) -> None:
        filename = f"{self.prefix}_{self.name}_header_process.h"
        with open(filename, "w") as f:
            for name in self.callbacks.keys():
                # 更精确的字符串替换，只替换开头的"On"为"process"
                if name.startswith("On"):
                    name = "process" + name[2:]
                line = f"void {name}(Task *task);\n\n"
                f.write(line)

    def generate_header_on(self) -> None:
        """
        生成包含回调函数声明的头文件
        该函数根据callbacks字典中定义的回调函数信息，生成相应的C++虚函数声明，
        并写入到指定的头文件中。函数名会将开头的"On"转换为"on"格式。
        """
        filename = f"{self.prefix}_{self.name}_header_on.h"

        # 类型映射字典，提高可维护性
        type_mapping = {
            "int": "int reqid",
            "bool": "bool last",
            "char*": "string data",
            "CThostFtdcRspInfoField": "const dict &error"
        }

        try:
            with open(filename, "w") as f:
                # 遍历所有回调函数定义，生成对应的虚函数声明
                for name, d in self.callbacks.items():
                    # 更精确的字符串替换，只替换开头的"On"
                    if name.startswith("On"):
                        name = "on" + name[2:]

                    args_list = []
                    # 根据参数类型映射生成参数列表
                    for type_ in d.values():
                        if type_ in type_mapping:
                            args_list.append(type_mapping[type_])
                        else:
                            args_list.append("const dict &data")

                    args_str = ", ".join(args_list)
                    line = f"virtual void {name}({args_str}) {{}};\n\n"
                    f.write(line)
        except IOError as e:
            raise IOError(f"Failed to write to file {filename}: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error occurred: {str(e)}")

    def generate_header_function(self) -> None:
        """
        根据函数定义生成对应的 C++ 头文件函数声明。
        """
        filename = f"{self.prefix}_{self.name}_header_function.h"
        try:
            with open(filename, "w") as f:
                for func_name, func_info in self.functions.items():
                    # 获取函数类型
                    func_type: str = func_info['func_type']
                    # 处理特殊函数返回类型为 void
                    new_func_type = process_func_type(func_type)
                    # 函数名处理为小写开头
                    new_func_name = replace_function_name(func_name)

                    # 初始化 source_functions 中的条目
                    self.source_functions[func_name] = {
                        'func_type': func_type,
                        'func_args': {}
                    }

                    # 如果函数没有参数，直接生成函数声明
                    if not func_info['func_args']:
                        header_line = f"{new_func_type} {new_func_name}();\n\n"
                    else:
                        converted_arg_types = []
                        pre_header_line = f"{new_func_type} {new_func_name}("

                        for arg_name, arg_type in func_info['func_args'].items():

                            # 特殊变量名的处理, v6.7.11
                            if arg_type.endswith("Field"):
                                self.source_functions[func_name]['func_field'] = arg_type
                                converted_arg_types.append("const dict &req")
                            elif arg_name == "nRequestID" and arg_type == "int":
                                converted_arg_types.append("int reqid")
                            elif arg_name == "pszFlowPath=\"\"" and arg_type == "const char":
                                converted_arg_types.append("string pszFlowPath=\"\"")
                            elif arg_name == "bIsUsingUdp=false" and arg_type == "const bool":
                                converted_arg_types.append("bool bIsUsingUdp=false")
                            elif arg_name == "bIsMulticast=false" and arg_type == "const bool":
                                converted_arg_types.append("bool bIsMulticast=false")
                            elif arg_name == "bIsProductionMode=true" and arg_type == "bool":
                                converted_arg_types.append("bool bIsProductionMode=true")
                            elif arg_name == "pszFrontAddress" and arg_type == "char":
                                converted_arg_types.append("string pszFrontAddress")
                            elif arg_name == "pszNsAddress" and arg_type == "char":
                                converted_arg_types.append("string pszNsAddress")
                            elif arg_name == "ppInstrumentID[]" and arg_type == "char":
                                converted_arg_types.append("string instrumentID")
                            elif arg_name == "nResumeType" and arg_type == "THOST_TE_RESUME_TYPE":
                                self.source_functions[func_name]['func_args']['nType'] = arg_type
                                converted_arg_types.append("int nType")

                        # 处理转换后的参数并更新 source_functions
                        for arg in converted_arg_types:
                            arg_normalized = ' '.join(arg.split())
                            if ' ' in arg_normalized:
                                last_space_index = arg_normalized.rfind(' ')
                                new_arg_type = arg_normalized[:last_space_index].strip()
                                new_arg_name = arg_normalized[last_space_index + 1:].strip()

                                # 跳过某些特定函数的参数处理
                                if func_name in (
                                        CtpFuncConst.SUBSCRIBE_PRIVATE_TOPIC,
                                        CtpFuncConst.SUBSCRIBE_PUBLIC_TOPIC
                                ):
                                    continue
                                self.source_functions[func_name]['func_args'][new_arg_name] = new_arg_type

                        arg_line = ", ".join(converted_arg_types)
                        header_line = f"{pre_header_line}{arg_line});\n\n"

                    f.write(header_line)
        except IOError as e:
            print(f"写入头文件失败: {e}")

    def generate_source_task(self) -> None:
        """"""
        filename = f"{self.prefix}_{self.name}_source_task.cpp"
        with open(filename, "w") as f:
            for name, d in self.callbacks.items():
                line = self.lines[name]

                # 替换函数声明
                method_decl = line.replace("virtual void ", f"void {self.class_name}::") + "\n"

                # 函数体开始
                body = "{\n"
                body += "\tTask task = Task();\n"
                body += f"\ttask.task_name = {name.upper()};\n"

                # 处理字段
                for field, type_ in d.items():
                    if type_ == "int":
                        body += f"\ttask.task_id = {field};\n"
                    elif type_ == "bool":
                        body += f"\ttask.task_last = {field};\n"
                    elif type_ == "CThostFtdcRspInfoField":
                        body += self._generate_field_assignment(field, type_, "task_error")
                    else:
                        body += self._generate_field_assignment(field, type_, "task_data")

                body += "\tthis->task_queue.push(task);\n"
                body += "};\n\n"

                # 写入文件
                f.write(method_decl + body)
    @staticmethod
    def _generate_field_assignment(field: str, type_: str, task_field: str) -> str:
        """生成字段赋值代码块"""
        code = f"\tif ({field})\n"
        code += "\t{\n"
        code += f"\t\t{type_} *{task_field} = new {type_}();\n"
        code += f"\t\t*{task_field} = *{field};\n"
        code += f"\t\ttask.{task_field} = {task_field};\n"
        code += "\t}\n"
        return code

    def generate_source_switch(self) -> None:
        """"""
        filename = f"{self.prefix}_{self.name}_source_switch.cpp"

        try:
            with open(filename, "w") as f:
                content_parts = []
                for name in self.callbacks.keys():
                    # 确保回调函数名以"On"开头
                    if not name.startswith("On"):
                        continue
                    # 更精确的字符串替换，只替换开头的"On"为"process"
                    if name.startswith("On"):
                        process_name = "process" + name[2:]
                    content_parts.extend([
                        f"case {name.upper()}:\n",
                        "{\n",
                        f"\tthis->{process_name}(&task);\n",
                        "\tbreak;\n",
                        "}\n\n"
                    ])
                f.write("".join(content_parts))
        except IOError as e:
            raise IOError(f"无法写入文件 {filename}: {str(e)}")

    def generate_source_process(self) -> None:
        """"""
        filename = f"{self.prefix}_{self.name}_source_process.cpp"
        lines = []

        for name, callback_fields in self.callbacks.items():
            # 更精确的字符串替换，只替换开头的"On"为"process"
            if not name.startswith("On"):
                continue
            else:
                process_name = "process" + name[2:]

            if not name.startswith("On"):
                continue
            else:
                on_name = "on" + name[2:]

            lines.append(f"void {self.class_name}::{process_name}(Task *task)\n{{")
            lines.append("\tgil_scoped_acquire acquire;")

            args = []

            # 处理 data等其他字段
            for field_name, field_type in callback_fields.items():
                if field_type == "int":
                    args.append("task->task_id")
                elif field_type == "bool":
                    args.append("task->task_last")
                elif field_type == "CThostFtdcRspInfoField":
                    args.append("error")
                    lines.append("\tdict error;")
                    lines.append("\tif (task->task_error)\n\t{")
                    lines.append(f"\t\t{field_type} *task_error = ({field_type}*)task->task_error;")

                    struct_fields = self.structs[field_type]
                    for struct_field, struct_type in struct_fields.items():
                        if struct_type == "string":
                            lines.append(f"\t\terror[\"{struct_field}\"] = toUtf(task_error->{struct_field});")
                        else:
                            lines.append(f"\t\terror[\"{struct_field}\"] = task_error->{struct_field};")

                    lines.append("\t\tdelete task_error;")
                    lines.append("\t}")
                else:
                    # 其他结构体
                    args.append("data")
                    lines.append("\tdict data;")
                    lines.append("\tif (task->task_data)\n\t{")
                    lines.append(f"\t\t{field_type} *task_data = ({field_type}*)task->task_data;")

                    struct_fields = self.structs[field_type]
                    for struct_field, struct_type in struct_fields.items():
                        if struct_type == "string":
                            lines.append(f"\t\tdata[\"{struct_field}\"] = toUtf(task_data->{struct_field});")
                        else:
                            lines.append(f"\t\tdata[\"{struct_field}\"] = task_data->{struct_field};")

                    lines.append("\t\tdelete task_data;")
                    lines.append("\t}")

            args_str = ", ".join(args)
            lines.append(f"\tthis->{on_name}({args_str});")
            lines.append("};\n")

        with open(filename, "w") as f:
            f.write("\n".join(lines))

    def generate_source_function(self) -> None:
        """"""
        filename = f"{self.prefix}_{self.name}_source_function.cpp"

        try:
            with open(filename, "w") as f:
                for func_name, func_info in self.source_functions.items():
                    # 定义字符串 list
                    arg_list = []
                    old_func_type: str = func_info.get('func_type', '')
                    # 处理特殊函数返回类型为 void
                    new_func_type = process_func_type(old_func_type)

                    func_args: dict = func_info.get('func_args', {})
                    # 处理参数名称中的 =""和=''
                    for arg_name, arg_type in func_args.items():
                        # 处理参数名称，去除 =""和='' 部分（如果有的话）
                        clean_arg_name = arg_name.replace('=""', '').replace("=''", "")
                        clean_arg_name = clean_arg_name.replace("=false", "").replace("=true", "")
                        # 参数类型 参数名称添加到 list
                        arg_list.append(f"{arg_type} {clean_arg_name}")

                    args_str = ", ".join(arg_list)
                    # 获取小写开头的函数名，生成函数名的时候需要
                    lowercase_func_name = replace_function_name(func_name)

                    # 写函数声明
                    if func_name in {CtpFuncConst.SUBSCRIBE_PRIVATE_TOPIC, CtpFuncConst.SUBSCRIBE_PUBLIC_TOPIC}:
                        f.write(f"{new_func_type} {self.class_name}::{lowercase_func_name}(int nType)\n")
                    else:
                        f.write(f"{new_func_type} {self.class_name}::{lowercase_func_name}({args_str})\n")
                    f.write("{\n")

                    # 特殊函数处理,v.6.7.11
                    if func_name == CtpFuncConst.CREATE_FTDC_MD_API:
                        if args_str:
                            args = [a.strip() for a in args_str.split(',') if a.strip()]
                            arg_names = []
                            for arg in args:
                                parts = arg.split()
                                if len(parts) >= 2:
                                    # 取参数名并清理默认值后缀
                                    name = parts[-1].replace('=""', '').replace("=''", "").replace("=false", "").replace("=true", "")
                                    arg_names.append(name)
                            
                            if arg_names:
                                # 第一个参数是 string 路径，需要 .c_str()；其余透传
                                call_args = [f"{arg_names[0]}.c_str()"]
                                call_args.extend(arg_names[1:])
                                
                                f.write(f"\tthis->api = {old_func_type}::{func_name}({', '.join(call_args)});\n")
                                f.write(f"\tthis->api->{CtpFuncConst.REGISTER_SPI}(this);\n")
                                f.write("};\n\n")

                    # 特殊函数处理,v6.7.11
                    elif func_name == CtpFuncConst.CREATE_FTDC_TRADER_API:
                        if args_str:
                            args = [a.strip() for a in args_str.split(',') if a.strip()]
                            arg_names = []
                            for arg in args:
                                parts = arg.split()
                                if len(parts) >= 2:
                                    name = parts[-1].replace('=""', '').replace("=''", "").replace("=false", "").replace("=true", "")
                                    arg_names.append(name)
                            
                            if arg_names:
                                call_args = [f"{arg_names[0]}.c_str()"]
                                call_args.extend(arg_names[1:])
                                
                                f.write(f"\tthis->api = {old_func_type}::{func_name}({', '.join(call_args)});\n")
                                f.write(f"\tthis->api->{CtpFuncConst.REGISTER_SPI}(this);\n")
                                f.write("};\n\n")

                    elif func_name == CtpFuncConst.RELEASE:
                        f.write(f"\tthis->api->{func_name}();\n")
                        f.write("};\n\n")

                    elif func_name == CtpFuncConst.INIT:
                        f.write("\tthis->active = true;\n")
                        f.write(f"\tthis->task_thread = thread(&{self.class_name}::processTask, this);\n\n")
                        f.write(f"\tthis->api->{func_name}();\n")
                        f.write("};\n\n")

                    elif func_name == CtpFuncConst.JOIN:
                        f.write(f"\tint i = this->api->{func_name}();\n")
                        f.write("\treturn i;\n")
                        f.write("};\n\n")

                    elif func_name == CtpFuncConst.EXIT:
                        f.write("\tthis->active = false;\n")
                        f.write("\tthis->task_queue.terminate();\n")
                        f.write("\tthis->task_thread.join();\n\n")
                        f.write(f"\tthis->api->{CtpFuncConst.REGISTER_SPI}(NULL);\n")
                        f.write(f"\tthis->api->{CtpFuncConst.RELEASE}();\n")
                        f.write("\tthis->api = NULL;\n")
                        f.write("\treturn 1;\n")
                        f.write("};\n\n")

                    elif func_name in {CtpFuncConst.GET_TRADING_DAY, CtpFuncConst.GET_API_VERSION}:
                        var_name = "day" if func_name == CtpFuncConst.GET_TRADING_DAY else "version"
                        f.write(f"\tstring {var_name} = this->api->{func_name}();\n")
                        f.write(f"\treturn {var_name};\n")
                        f.write("};\n\n")

                    elif func_name in {CtpFuncConst.REGISTER_FRONT, CtpFuncConst.REGISTER_NAME_SERVER}:
                        if ' ' in args_str:
                            arg_name = args_str.split(' ')[1]
                            f.write(f"\tthis->api->{func_name}((char*){arg_name}.c_str());\n")
                            f.write("};\n\n")

                    elif func_name in {CtpFuncConst.REGISTER_FENS_USER_INFO, CtpFuncConst.GET_FRONT_INFO}:
                        if "func_field" in func_info and func_info["func_field"] in self.structs:
                            self._write_struct_fields(f, func_info["func_field"])
                            f.write(f"\tthis->api->{func_name}(&myreq);\n")
                            f.write("};\n\n")

                    elif func_name in {
                        CtpFuncConst.SUBSCRIBE_MARKET_DATA,
                        CtpFuncConst.UN_SUBSCRIBE_MARKET_DATA,
                        CtpFuncConst.SUBSCRIBE_FOR_QUOTE_RSP,
                        CtpFuncConst.UN_SUBSCRIBE_FOR_QUOTE_RSP
                    }:
                        if ' ' in args_str:
                            arg_name = args_str.split(' ')[1]
                            f.write(f"\tchar* buffer = (char*){arg_name}.c_str();\n")
                            f.write("\tchar* myreq[1] = { buffer };\n")
                            f.write(f"\tint i = this->api->{func_name}(myreq, 1);\n")
                            f.write("\treturn i;\n")
                            f.write("};\n\n")

                    elif func_name in {CtpFuncConst.SUBSCRIBE_PRIVATE_TOPIC,
                                       CtpFuncConst.SUBSCRIBE_PUBLIC_TOPIC}:
                        if ' ' in args_str:
                            arg_type = args_str.split(' ')[0]
                            f.write(f"\tthis->api->{func_name}(({arg_type})nType);\n")
                            f.write("};\n\n")

                    elif new_func_type == "int" and not ',' in args_str and "func_field" in func_info:
                        if func_info["func_field"] in self.structs:
                            self._write_struct_fields(f, func_info["func_field"])
                            f.write(f"\tint i = this->api->{func_name}(&myreq);\n")
                            f.write("\treturn i;\n")
                            f.write("};\n\n")

                    elif func_name.startswith("Req") and "func_field" in func_info:
                        if func_info["func_field"] in self.structs:
                            self._write_struct_fields(f, func_info["func_field"])
                            f.write(f"\tint i = this->api->{func_name}(&myreq, reqid);\n")
                            f.write("\treturn i;\n")
                            f.write("};\n\n")
                    else:
                        pass
        except Exception as e:
            print(f"写入文件 {filename} 时发生错误: {e}")

    def _write_struct_fields(self, f, func_field):
        """提取结构体字段写入逻辑"""
        f.write(f"\t{func_field} myreq = {func_field}();\n")
        f.write("\tmemset(&myreq, 0, sizeof(myreq));\n")
        struct_fields = self.structs[func_field]
        for struct_field, struct_type in struct_fields.items():
            if struct_type == "string":
                line = f"\tgetString(req, \"{struct_field}\", myreq.{struct_field});\n"
            else:
                line = f"\tget{struct_type.capitalize()}(req, \"{struct_field}\", &myreq.{struct_field});\n"
            f.write(line)

    def generate_source_on(self) -> None:
        """"""
        filename = f"{self.prefix}_{self.name}_source_on.cpp"

        try:
            with open(filename, "w") as f:
                for name, d in self.callbacks.items():
                    if not name.startswith("On"):
                        continue
                    else:
                        on_name = "on" + name[2:]

                    args = []
                    bind_args = ["void", self.class_name, on_name]
                    type_mapping = {
                        "int": ("int reqid", "reqid"),
                        "bool": ("bool last", "last"),
                        "CThostFtdcRspInfoField": ("const dict &error", "error")
                    }

                    for _, type_ in d.items():
                        cpp_arg, bind_arg = type_mapping.get(type_, ("const dict &data", "data"))
                        args.append(cpp_arg)
                        bind_args.append(bind_arg)

                    args_str = ", ".join(args)
                    bind_args_str = ", ".join(bind_args)

                    lines = [
                        f"void {on_name}({args_str}) override",
                        "{",
                        "\ttry",
                        "\t{",
                        f"\t\tPYBIND11_OVERLOAD({bind_args_str});",
                        "\t}",
                        "\tcatch (const error_already_set &e)",
                        "\t{",
                        "\t\tcout << e.what() << endl;",
                        "\t}",
                        "};\n",
                        ""
                    ]

                    f.write("\n".join(lines))
        except IOError as e:
            print(f"Failed to write file {filename}: {e}")

    def generate_source_module(self) -> None:
        """"""
        filename = f"{self.prefix}_{self.name}_source_module.cpp"

        try:
            with open(filename, "w") as f:
                lines = []

                for name in self.functions.keys():
                    processed_name = replace_function_name(name)
                    lines.append(f".def(\"{processed_name}\", &{self.class_name}::{processed_name})\n")

                lines.append("\n")

                for name in self.callbacks.keys():
                    if not name.startswith("On"):
                        continue
                    else:
                        processed_name = "on" + name[2:]
                    lines.append(f".def(\"{processed_name}\", &{self.class_name}::{processed_name})\n")

                lines.append(";\n")

                f.writelines(lines)
        except IOError as e:
            # 处理文件操作异常
            raise IOError(f"无法写入文件 {filename}: {e}")


def main(include_dir='../include', output_dir='../src'):
    md = GenerateApiFunc(os.path.join(include_dir, "ThostFtdcMdApi.h"), "ctp", "md", "MdApi")
    md.run()
    td = GenerateApiFunc(os.path.join(include_dir, "ThostFtdcTraderApi.h"), "ctp", "td", "TdApi")
    td.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-dir', default='../include')
    parser.add_argument('--output-dir', default='../src')
    args = parser.parse_args()
    main(args.include_dir, args.output_dir)