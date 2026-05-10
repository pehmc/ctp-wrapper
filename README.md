<p align="center">
  <h3 align="center">CTP Wrapper</h3>
  <p align="center">
    Linux环境的CTP封装器
    <br />
    <a href="./demo">查看Demo</a>
    ·
    <a href="https://github.com/pehmc/ctp-wrapper/issues">报告Bug</a>
  </p>
</p>

<div align="center">

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

</div>

## 目录

- [上手指南](#上手指南)
  - [适配的版本](#适配的版本)
  - [安装步骤](#安装步骤)
- [文件目录说明](#文件目录说明)
- [使用到的框架](#使用到的框架)
- [鸣谢](#鸣谢)

### 上手指南

#### 适配的版本

1. CTP v6.7.13_20260225
2. TTS v6.7.11

#### 安装步骤

1. 克隆仓库，
2. ctp/v 管理版本
3. 运行 `python wrapper  <version>`
4. `from ctp.api import ...`

### 文件目录说明

封装成功后的ctp目录：

``` python
ctp
├── api
│   ├── __init__.py
│   ├── mdapi.py
│   ├── _mdapi.so
│   ├── tdapi.py
│   └── _tdapi.so
├── __init__.py
├── interface
│   ├── mdapi.i
│   └── tdapi.i
├── v
│   ├── tts_6.7.11
│   │   ├── include
│   │   │   ├── error.dtd
│   │   │   ├── error.xml
│   │   │   ├── ThostFtdcMdApi.h
│   │   │   ├── ThostFtdcTraderApi.h
│   │   │   ├── ThostFtdcUserApiDataType.h
│   │   │   └── ThostFtdcUserApiStruct.h
│   │   └── libs
│   │       ├── thostmduserapi_se.so
│   │       └── thosttraderapi_se.so
│   └── v6.7.13_20260225
│       ├── include
│       │   ├── error.dtd
│       │   ├── error.xml
│       │   ├── ThostFtdcMdApi.h
│       │   ├── ThostFtdcTraderApi.h
│       │   ├── ThostFtdcUserApiDataType.h
│       │   └── ThostFtdcUserApiStruct.h
│       ├── libs
│       │   ├── thostmduserapi_se.so
│       │   └── thosttraderapi_se.so
│       └── src
│           ├── mdapi.py
│           ├── mdapi_wrap.cpp
│           ├── mdapi_wrap.h
│           ├── mdapi_wrap.o
│           ├── tdapi.py
│           ├── tdapi_wrap.cpp
│           ├── tdapi_wrap.h
│           └── tdapi_wrap.o
└── wrapper.py
```

### 使用到的框架

- swig 4.4.1
- python 3.13

### 鸣谢

- [vnpy_ctp](https://github.com/vnpy/vnpy_ctp)
- [Homalos ctp](https://github.com/Homalos/ctp/tree/main/ctp)
- [openctp](http://www.openctp.cn/)

<!-- links -->
[your-project-path]:pehmc/ctp-wrapper
[contributors-shield]: https://img.shields.io/github/contributors/pehmc/ctp-wrapper.svg?style=flat-square
[contributors-url]: https://github.com/pehmc/ctp-wrapper/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/pehmc/ctp-wrapper.svg?style=flat-square
[forks-url]: https://github.com/pehmc/ctp-wrapper/network/members
[stars-shield]: https://img.shields.io/github/stars/pehmc/ctp-wrapper.svg?style=flat-square
[stars-url]: https://github.com/pehmc/ctp-wrapper/stargazers
[issues-shield]: https://img.shields.io/github/issues/pehmc/ctp-wrapper.svg?style=flat-square
[issues-url]: https://img.shields.io/github/issues/pehmc/ctp-wrapper.svg
[license-shield]: https://img.shields.io/github/license/pehmc/ctp-wrapper.svg?style=flat-square
[license-url]: https://github.com/pehmc/ctp-wrapper/blob/master/LICENSE.txt




