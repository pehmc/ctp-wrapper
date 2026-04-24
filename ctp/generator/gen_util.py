"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import os
import re
from pathlib import Path
import argparse


def create_output_dir(base_output_dir: str, output_dir_name: str) -> str:
    output_path = Path(base_output_dir) / output_dir_name
    output_dir = os.fspath(output_path)

    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            print(f"目录已创建: {output_path}")
            return output_dir
        except PermissionError:
            print(f"权限不足，无法创建目录: {output_path}")
            return ""
        except OSError as e:
            print(f"创建目录时出错: {e}")
            return ""
    else:
        return output_dir


def replace_function_name(func_name: str) -> str:
    prefix_mapping = {
        "Req": "req",
        "Create": "create",
        "Get": "get",
        "Release": "release",
        "Init": "init",
        "Join": "join",
        "Exit": "exit",
        "Register": "register",
        "Subscribe": "subscribe",
        "UnSubscribe": "unSubscribe",
        "Submit": "submit"
    }
    for old_prefix, new_prefix in prefix_mapping.items():
        if func_name.startswith(old_prefix):
            return new_prefix + func_name[len(old_prefix):]
    return func_name


def process_func_type(func_type: str) -> str:
    if func_type and (func_type == 'CThostFtdcMdApi' or func_type == 'CThostFtdcTraderApi'):
        new_func_type = func_type.replace('CThostFtdcMdApi', 'void')
        new_func_type = new_func_type.replace('CThostFtdcTraderApi', 'void')
        return new_func_type
    return func_type


def camel_to_underscore_upper(name: str) -> str:
    if not name:
        return ""
    part1 = re.sub('([a-z])([A-Z])', r'\1_\2', name)
    part2 = re.sub('([A-Z])([A-Z][a-z])', r'\1_\2', part1)
    return part2.upper()


def underscore_to_camelcase(name: str) -> str:
    if not name:
        return ""
    parts = name.split('_')
    return ''.join(part.capitalize() for part in parts if part)


def format_equal_arg(arg: str) -> str:
    return re.sub(r'\s*=\s*', '=', arg)


def format_pointer_arg(arg: str) -> str:
    return re.sub(r'(\w+)\s*\*\s*(\w+)', r'\1 *\2', arg)