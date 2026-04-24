"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import os
import locale

# 设置 locale
os.environ['LC_ALL'] = 'C'
os.environ['LANG'] = 'C'
os.environ['LANGUAGE'] = 'C'
os.environ['LC_CTYPE'] = 'C'

try:
    locale.setlocale(locale.LC_ALL, 'C')
except locale.Error:
    pass

import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from ctp.api import MdApi


class CtpConst(object):

    # reason mapping
    REASON_MAPPING = {
        0x1001: "网络读失败",
        0x1002: "网络写失败",
        0x2001: "接收心跳超时",
        0x2002: "发送心跳失败",
        0x2003: "收到错误报文"
    }


class CtpMdApi(MdApi):

    def __init__(self) -> None:
        super().__init__()

        # 请求ID，对应响应里的nRequestID，无递增规则，由用户自行维护。
        self.req_id: int = 0
        self.subscribe_symbol: set = set()  # 已订阅的合约 Subscribed contracts
        self.address: str = ""              # 服务器地址 Server address
        self.broker_id: str = ""            # 经纪公司代码 Brokerage Company Code
        self.userid: str = ""               # 用户名 username
        self.password: str = ""             # 密码 password
        self.user_product_info = ""         # 用户端产品信息 User product information
        self.connect_status: bool = False  # 连接状态 Connection status
        self.login_status: bool = False     # 登录状态 Login status
        self.current_date = datetime.now().strftime("%Y%m%d")   # 当前日期 Current date

    def onFrontConnected(self) -> None:
        """
        行情服务器连接成功响应
        当客户端与交易托管系统建立起通信连接时（还未登录前），该方法被调用。本方法在完成初始化后调用，可以在其中完成用户登录任务。
        """
        print("ctp md api callback: onFrontConnected - The market data server is connected successfully")
        print("Start the login process")

        self.login()  # 调用登录方法, Calling the login method

    def onFrontDisconnected(self, reason: int) -> None:
        """
        行情服务器连接断开响应

        当客户端与交易托管系统通信连接断开时，该方法被调用。
        当发生这个情况后，API会自动重新连接，客户端可不做处理。
        自动重连地址，可能是原来注册的地址，也可能是系统支持的其它可用的通信地址，它由程序自动选择。
        注:重连之后需要重新登录。6.7.9及以后版本中，断线自动重连的时间间隔为固定1秒。
        :param reason: 错误代号，连接断开原因，为10进制值，因此需要转成16进制后再参照下列代码：
                0x1001（4097） 网络读失败。
                0x1002（4098） 网络写失败。
                0x2001（8193） 接收心跳超时。接收心跳超时。前置每53s会给一个心跳报文给api，如果api超过120s未收到任何新数据，
                则认为网络异常，断开连接
                0x2002（8194） 发送心跳失败。api每15s会发送一个心跳报文给前置，如果api检测到超过40s没发送过任何新数据，则认为网络异常，
                断开连接
                0x2003 收到错误报文
        :return: None
        """
        self.connect_status = False
        self.login_status = False
        reason_hex = hex(reason)
        reason_msg = CtpConst.REASON_MAPPING.get(reason, f"Unknown cause({reason_hex})")
        print(f"The market server connection is disconnected, the reason is：{reason_msg} ({reason_hex})")

    def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """
        登录请求响应，当ReqUserLogin后，该方法被调用。

        :param data: 用户登录应答
        :param error: 响应信息
        :param reqid: 返回用户操作请求的ID，该ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对nRequestID的最后一次返回。
        :return: None
        """
        if error["ErrorID"] == 0:
            print("ctp md api callback: onRspUserLogin - The market server login is successful")
            self.login_status = True

            self.update_date()
        else:
            print(f"Market server login failed: ErrorID={error.get('ErrorID', '')}, "
                  f"ErrorMsg={error.get('ErrorMsg', '')}")


    def onRspError(self, error: dict, reqid: int, last: bool) -> None:
        """
        请求报错响应，针对用户请求的出错通知。

        :param error: 响应信息
        :param reqid: 返回用户操作请求的ID，该ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对nRequestID的最后一次返回。
        :return: None
        """
        print(f"ctp md api callback: onRspError - Request error, ErrorID={error.get('ErrorID', '')}, "
              f"ErrorMsg={error.get('ErrorMsg', '')}")
        print("Market interface error", error)

    def onRspSubMarketData(self, data: dict, error: dict, reqid: int, last: bool) -> None:
        """
        订阅市场行情响应
        订阅行情应答，调用SubscribeMarketData后，通过此接口返回。

        :param data: 指定的合约
        :param error: 响应信息
        :param reqid: 返回用户操作请求的ID，该ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对nRequestID的最后一次返回。
        :return: None
        """
        symbol = data.get("InstrumentID", "UNKNOWN")
        print(f"ctp md api callback: onRspSubMarketData - Subscription feedback, Contract={symbol}, "
              f"ErrorID={error.get('ErrorID', 'N/A') if error else 'None'}")

        if data and "InstrumentID" in data:
            symbol = data["InstrumentID"]
            print(f"symbol: {symbol}")
        else:
            print(f"Market Quotes Subscription Failed: {error}")

    def onRtnDepthMarketData(self, data: dict) -> None:
        """
        深度行情通知，当SubscribeMarketData订阅行情后，行情通知由此推送。

        :param data: 深度行情
        :return: None
        """
        print(f"ctp md api callback: onRtnDepthMarketData")
        # 获取合约代码用于日志记录
        symbol: str = data.get("InstrumentID", "UNKNOWN")

        print(f"CTP Market data reception: {symbol} @ {data.get('UpdateTime', 'N/A')} "
              f"LastPrice={data.get('LastPrice', 'N/A')}")

        # 过滤没有时间戳的异常行情数据
        if not data["UpdateTime"]:
            print(f"Skip market data without timestamps: {symbol}")
            return

    def connect(self, address: str, broker_id: str, userid: str, password: str) -> None:
        """
        连接行情服务器

        :param address: 行情服务器地址
        服务器地址的格式为：“protocol://ipaddress:port”
        如：“tcp://127.0.0.1:17001”。“tcp”代表传输协议，“127.0.0.1”代表服务器地址。“17001”代表行情端口号。
        SSL前置格式：ssl://192.168.0.1:41205
        TCP前置IPv4格式：tcp://192.168.0.1:41205
        TCP前置IPv6格式：tcp6://fe80::20f8:aabb:7d59:887d:35001
        :param broker_id: 经纪公司代码
        :param userid: 用户代码
        :param password: 密码
        :return: None
        """
        self.broker_id = broker_id
        self.address = address
        self.userid = userid
        self.password = password

        # 是否使用UDP行情
        is_using_udp = False

        # 是否使用组播行情(组播行情只能在内网中使用，需要咨询所连接的系统是否支持组播行情。)
        is_multicast = False

        # 选在连接的是生产还是评测前置，True:使用生产版本的API False:使用测评版本API
        is_production_mode = True

        # 指定con文件目录来存贮交易托管系统发布消息的状态。默认值代表当前目录。
        ctp_con_dir: Path = Path.cwd().joinpath("con")

        if not ctp_con_dir.exists():
            ctp_con_dir.mkdir()

        # 消息的状态文件完整路径
        api_path_str = str(ctp_con_dir) + "/md"
        print("CtpMdApi：Trying to create an API with path {}".format(api_path_str))
        try:
            # 加上utf-8编码，否则中文路径会乱码
            self.createFtdcMdApi(api_path_str.encode("GBK").decode("utf-8"), is_using_udp, is_multicast,
                                 is_production_mode)
            print("CtpMdApi：createFtdcMdApi call succeeded.")

        except Exception as e_create:
            print("CtpMdApi：createFtdcMdApi failed! Error: {}".format(e_create))
            print("CtpMdApi：createFtdcMdApi Traceback: {}".format(traceback.format_exc()))
            return

        # 设置交易托管系统的网络通讯地址，交易托管系统拥有多个通信地址，用户可以注册一个或多个地址。
        # 如果注册多个地址则使用最先建立TCP连接的地址。
        try:
            self.registerFront(address)
            print("CtpMdApi：Try initializing the API using the address:{}...".format(address))
            # 初始化运行环境,只有调用后,接口才开始发起前置的连接请求。
            self.init()
            print("CtpMdApi：init call succeeded.")
            self.connect_status = True
        except Exception as e_init:
            print("CtpMdApi：Initialization failed! Error: {}".format(e_init))
            print("CtpMdApi：Initialize backtrace: {}".format(traceback.format_exc()))
            return

    def login(self) -> None:
        """
        用户登录
        """
        # 用户登录请求
        ctp_req: dict = {
            # BrokerID: 开启行情身份校验功能后，该字段必需正确填写
            "BrokerID": self.broker_id,
            # 操作员代码，后续请求中的investorid需要属于该操作员的组织架构下；开启行情身份校验功能后，该字段必需正确填写
            "UserID": self.userid,
            # 密码
            "Password": self.password,
            # 客户端的产品信息，如软件开发商、版本号等
            # CTP后台用户事件中的用户登录事件所显示的用户端产品信息取自ReqAuthentication接口里的UserProductInfo，而非ReqUserLogin里的。
            "UserProductInfo": self.user_product_info
        }

        self.req_id += 1
        # 用户登录请求，对应响应OnRspUserLogin。目前行情登陆不校验账号密码。
        # 自CTP交易系统升级6.6.2版本后，后台支持对用户登录行情前置进行身份校验。若启用该功能后，登录行情前置时要求当前交易日该IP
        # 已成功登录过交易系统，且发起登录行情的请求中必须正确填写BrokerID和UserID，与登录交易的信息保持一致。
        # 不填、填错或该IP未成功登录过交易系统，则校验不通过，会提示“CTP: 不合法登录”；若不启用，则无需验证，可直接发起登录。
        ret_code = self.reqUserLogin(ctp_req, self.req_id)

        # 0，代表成功。
        # -1，表示网络连接失败；
        # -2，表示未处理请求超过许可数；
        # -3，表示每秒发送请求数超过许可数。
        if ret_code == 0:
            print("CtpMdApi：reqUserLogin call succeeded.")
        else:
            print(f"CtpMdApi：reqUserLogin call failed, ret_code: {ret_code}")

    def subscribe(self, symbol: str) -> None:
        """
        订阅行情
        """
        print(f"Prepare subscription contract: {symbol}")

        # 过滤重复的订阅
        if symbol in self.subscribe_symbol:
            print(f"Contract {symbol} is already in the subscription list, skipping duplicate subscription")
            return

        if self.login_status:
            print(f"Send subscription request {symbol}")
            ret_code = self.subscribeMarketData(symbol)

            # 0，代表成功。
            # -1，表示网络连接失败；
            # -2，表示未处理请求超过许可数；
            # -3，表示每秒发送请求数超过许可数。

            if ret_code == 0:
                print(f"Subscription request sent {symbol}")
            else:
                print(f"Subscription request failed {symbol}, return code={ret_code}")
        else:
            print(f"Not logged in, cannot subscribe to {symbol}")

        # 添加订阅的合约
        self.subscribe_symbol.add(symbol)

    def close(self) -> None:
        """
        关闭连接
        """
        if self.connect_status:
            self.connect_status = False
            self.exit()

    def update_date(self) -> None:
        """
        更新当前日期
        """
        self.current_date = datetime.now().strftime("%Y%m%d")


class MarketData(object):

    def __init__(self):
        # 行情接口实例
        self.md_api: CtpMdApi | None = None

    def connect(self, setting: dict[str, Any]) -> None:
        """
        连接行情服务器
        """
        try:
            print("Start connecting to CTP market server...")

            # 配置字段处理
            md_address_raw = setting.get("md_address", "")
            broker_id = setting.get("broker_id", "")
            user_id = setting.get("user_id", "")
            password = setting.get("password", "")

            # 参数验证
            if not all([md_address_raw, broker_id, user_id, password]):
                raise ValueError("Required connection parameters are missing")

            # 创建API实例
            if not self.md_api:
                self.md_api = CtpMdApi()

            md_address: str = md_address_raw
            self.md_api.connect(md_address, broker_id, user_id, password)

            print(f"Connecting to {md_address}...")

        except Exception as e:
            print(f"Connection failed: {e}")
            if self.md_api:
                self.md_api.close()

    def subscribe(self, symbol: str) -> None:
        """
        订阅合约行情
        """
        if self.md_api:
            self.md_api.subscribe(symbol)
        else:
            print("The market API is not connected and cannot be subscribed.")

    def close(self) -> None:
        """
        关闭连接

        Close the connection
        :return: None
        """
        if self.md_api:
            self.md_api.close()
            self.md_api = None


if __name__ == '__main__':
    import time
    
    # thanks to openctp
    ctp_config = {
        "md_address": "tcp://trading.openctp.cn:30011",  # 7x24行情服务器地址 
        "broker_id": "9999",  # 经纪商代码 Broker Code
        "user_id": "18340",  # 用户代码 User Code
        "password": "123456",  # password
        "appid": "",
        "auth_code": ""
    }
    
    market = MarketData()
    market.connect(setting=ctp_config)
    
    # 等待连接和登录完成
    print("Waiting for connection and login to complete...")
    time.sleep(3)
    
    # 订阅一些常用的期货合约
    contracts_to_subscribe = [
        "SA609",
        "FG609"
    ]

    # 订阅合约的tick数量
    subscribe_count = 0
    
    print(f"Starting to subscribe to {len(contracts_to_subscribe)} contracts...")
    for contract in contracts_to_subscribe:
        print(f"Subscription contract: {contract}")
        market.subscribe(contract)
        subscribe_count += 1

        # 避免订阅请求过快
        time.sleep(1)

    print(f"Subscribed to {subscribe_count} contracts")
    print("Subscription completed, waiting for market data...")
    print("The program will run for 60 seconds to receive market data. Press Ctrl+C to exit early.")
    
    try:
        # 保持程序运行60秒来接收行情数据
        time.sleep(60)
    except KeyboardInterrupt:
        print("\nUser interrupt routine")
    finally:
        print("Closing connection...")
        market.close()
        print("End of program")
