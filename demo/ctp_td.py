"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import queue
import traceback
from pathlib import Path
from typing import SupportsInt

from ctp.api import TdApi
from ctp.api.ctp_constant import THOST_FTDC_OPT_LimitPrice, THOST_FTDC_D_Buy, THOST_FTDC_D_Sell, \
    THOST_FTDC_OF_CloseToday, THOST_FTDC_CC_Immediately, THOST_FTDC_HF_Speculation, THOST_FTDC_FCC_NotForceClose, \
    THOST_FTDC_TC_GFD, THOST_FTDC_VC_AV, THOST_FTDC_AF_Delete, THOST_FTDC_OST_Unknown, THOST_FTDC_OST_AllTraded, \
    THOST_FTDC_OST_PartTradedQueueing, THOST_FTDC_OST_PartTradedNotQueueing, THOST_FTDC_OST_NoTradeQueueing, \
    THOST_FTDC_OST_NoTradeNotQueueing, THOST_FTDC_OST_Canceled, THOST_TERT_QUICK


class CtpConst(object):

    # reason mapping
    REASON_MAPPING = {
        0x1001: "网络读失败",
        0x1002: "网络写失败",
        0x2001: "接收心跳超时",
        0x2002: "发送心跳失败",
        0x2003: "收到错误报文"
    }


class CtpTdApi(TdApi):

    def __init__(self) -> None:
        super().__init__()

        self.req_id: int = 0
        self.order_ref: int = 0
        self.connect_status: bool = False
        self.login_status: bool = False
        self.auth_status: bool = False

        self.broker_id: str = ""
        self.userid: str = ""
        self.password: str = ""
        self.auth_code: str = ""
        self.appid: str = ""

        self.front_id: int = 0
        self.session_id: int = 0
        # 订单队列，存储订单ID  
        self.order_queue: queue.Queue[str] = queue.Queue(maxsize=100)
        
        # 订单状态跟踪字典 
        self.order_status_map: dict = {}
        # 测试的合约，纯碱SA609
        self.symbol_map: dict = {"SA609": "CZCE"}
        
        # 订单状态常量映射
        self.order_status_names = {
            THOST_FTDC_OST_Unknown: "未知",
            THOST_FTDC_OST_AllTraded: "全部成交",
            THOST_FTDC_OST_PartTradedQueueing: "部分成交还在队列中",
            THOST_FTDC_OST_PartTradedNotQueueing: "部分成交不在队列中",
            THOST_FTDC_OST_NoTradeQueueing: "未成交还在队列中",
            THOST_FTDC_OST_NoTradeNotQueueing: "未成交不在队列中",
            THOST_FTDC_OST_Canceled: "撤单"
        }

    def onFrontConnected(self) -> None:
        """
        交易服务器连接成功响应
        当客户端与交易托管系统建立起通信连接时（还未登录前），该方法被调用。
        本方法在完成初始化后调用，可以在其中完成用户登录任务。
        """
        print("ctp td api callback: onFrontConnected - Trading server connection successful")

        if self.auth_code:
            self.authenticate()  # 调用授权验证方法  
        else:
            self.login()  # 调用登录方法  

    def onFrontDisconnected(self, reason: SupportsInt) -> None:
        """
        交易服务器连接断开响应
        当客户端与交易托管系统通信连接断开时，该方法被调用。
        当发生这个情况后，API会自动重新连接，客户端可不做处理。
        自动重连地址，可能是原来注册的地址，也可能是系统支持的其它可用的通信地址，它由程序自动选择。
        注:重连之后需要重新认证、登录。6.7.9及以后版本中，断线自动重连的时间间隔为固定1秒。
        :param reason: 错误代号，连接断开原因，为10进制值，因此需要转成16进制后再参照下列代码：
                0x1001（4097） 网络读失败。recv=-1
                0x1002（4098） 网络写失败。send=-1
                0x2001（8193） 接收心跳超时。接收心跳超时。前置每53s会给一个心跳报文给api，如果api超过120s未收到任何新数据，
                则认为网络异常，断开连接
                0x2002（8194） 发送心跳失败。api每15s会发送一个心跳报文给前置，如果api检测到超过40s没发送过任何新数据，则认为网络异常，
                断开连接
                0x2003 收到错误报文
        :return: None
        """
        self.connect_status = False
        self.login_status = False
        reason_hex = hex(int(reason))  # 错误代码转换成16进制
        reason_msg = CtpConst.REASON_MAPPING.get(reason, f"Unknown cause({reason_hex})")
        print(f"The transaction server connection is disconnected. the reason is：{reason_msg} ({reason_hex})")

    def onRspAuthenticate(self, data: dict, error: dict, reqid: SupportsInt, last: bool) -> None:
        """
        用户授权验证响应，当执行 ReqAuthenticate 后，该方法被调用
        :param data: 客户端认证响应
        :param error: 响应信息
        :param reqid: 返回用户操作请求的 ID，该 ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对 reqid 的最后一次返回。
        :return: None
        """
        if not error.get('ErrorID'):
            self.auth_status = True
            print("Transaction server authorization verification successful")
            self.login()
        else:
            if error.get('ErrorID') == 63:
                self.auth_status = False
            print("Transaction server authorization verification failed", error)

    def onRspUserLogin(self, data: dict, error: dict, reqid: SupportsInt, last: bool) -> None:
        """
        用户登录请求响应，当执行 ReqUserLogin 后，该方法被调用。
        :param data: 用户登录应答
        :param error: 响应信息
        :param reqid: 返回用户操作请求的 ID，该 ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对 reqid 的最后一次返回。
        :return: 无
        """
        print(f"ctp td api callback: onRspUserLogin - Login Response, ErrorID={error.get('ErrorID', 'N/A')}")
        if not error.get("ErrorID"):
            print("Trading server login successful")
            self.login_status = True
            self.front_id = data["FrontID"]
            self.session_id = data["SessionID"]

            ctp_req: dict = {
                "BrokerID": self.broker_id,
                "InvestorID": self.userid
            }
            self.req_id += 1
            # 调用确认结算单方法
            self.reqSettlementInfoConfirm(ctp_req, self.req_id)
        else:
            self.login_status = False
            print("Trading server login failed", error)

    def onRspUserLogout(self, data: dict, error: dict, reqid: SupportsInt, last: bool) -> None:
        """
        登出请求响应，当执行ReqUserLogout后，该方法被调用。
        :param data: 用户登出请求
        :param error: 响应信息
        :param reqid: 返回用户操作请求的 ID，该 ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对 reqid 的最后一次返回。
        :return: None
        """
        print("Trading account: {} Logged out".format(data['UserID']))

    def onRspSettlementInfoConfirm(self, data: dict, error: dict, reqid: SupportsInt, last: bool) -> None:
        """
        投资者结算结果确认响应，当执行ReqSettlementInfoConfirm后，该方法被调用。
        :param data: 投资者结算结果确认信息
        :param error: 响应信息
        :param reqid: 返回用户操作请求的 ID，该 ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对 reqid 的最后一次返回。
        :return: None
        """
        if error.get('ErrorID') != 0:
            error_message = ("Settlement order confirmation failed, error message: {}, "
                             "error code: {}").format(error.get('ErrorMsg', 'N/A'), error.get('ErrorID', 'N/A'))
            print(error_message, error)
        else:
            if last and error.get("ErrorID") == 0:
                print("Settlement information confirmed successfully")
                # 当结算单确认成功后，将登录成功标志设置为True
                self.login_status = True

                # Next steps
                # print("Start querying all contract information...")
                # self.req_id += 1
                # self.reqQryInstrument({}, self.req_id)

    def onRspOrderInsert(self, data: dict, error: dict, reqid: SupportsInt, last: bool) -> None:
        """
        报单录入请求响应，当执行ReqOrderInsert后有字段填写不对之类的CTP报错则通过此接口返回
        :param data: 输入报单
        :param error: 响应信息
        :param reqid: 返回用户操作请求的ID，该ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对nRequestID的最后一次返回。
        :return: None
        """
        print("ctp td api callback: onRspOrderInsert")
        if error.get("ErrorID") == 0:
            # 没有错误，正常返回
            return

        print(f"ErrorID={error['ErrorID']}")
        print(f"ErrorMsg={error['ErrorMsg']}")

        # 验证数据完整性
        if not data or "InstrumentID" not in data:
            print("订单插入失败回报数据不完整", error)
            return

        symbol = data["InstrumentID"]

        # 获取订单数据
        order_ref: str = data["OrderRef"]
        orderid: str = f"{self.front_id}_{self.session_id}_{order_ref}"

        # 获取详细错误信息
        error_id = error.get("ErrorID", "N/A")
        error_msg = error.get("ErrorMsg", "Unknown")
        print(f"Transaction order failed - Order ID: {orderid}, Contract: {symbol}, Error code: {error_id}, "
              f"Error message: {error_msg}", error)


    def onErrRtnOrderInsert(self, data: dict, error: dict) -> None:
        """
        报单录入错误回报，当执行ReqOrderInsert后有字段填写不对之类的CTP报错则通过此接口返回
        :param data: 输入报单
        :param error: 响应信息
        :return: None
        """
        print("ctp td api callback: onErrRtnOrderInsert")
        if not error or error.get("ErrorID") == 0:
            # 没有错误，正常返回 No error, return normally
            return
        print(f"ErrorID={error['ErrorID']}")
        print(f"ErrorMsg={error['ErrorMsg']}")


    def onRtnOrder(self, data: dict) -> None:
        """
        报单通知，当执行ReqOrderInsert后并且报出后，收到返回则调用此接口，私有流回报。
        """
        print("ctp td api callback: onRtnOrder")
        if not data or "InstrumentID" not in data:

            # 订单更新数据不完整
            print("Order update data is incomplete")
            return

        symbol: str = data["InstrumentID"]


        front_id: int = data["FrontID"]
        session_id: int = data["SessionID"]
        order_ref: str = data["OrderRef"]
        orderid: str = f"{front_id}_{session_id}_{order_ref}"

        status = data["OrderStatus"]
        if not status:
            print(f"收到不支持的委托状态，委托号：{orderid}")
            return

        # 获取状态名称
        status_name = self.order_status_names.get(status, f"Unknown status({status})")
        print(f"订单状态更新 - 订单 ID：{orderid}，状态：{status_name} ({status})")

        # 记录当前订单状态 
        old_status = self.order_status_map.get(orderid, "新订单")
        self.order_status_map[orderid] = status

        # 检查是否为撤单状态 
        if status == THOST_FTDC_OST_Canceled:
            print(f"订单已撤销 - 订单号: {orderid}, 合约: {symbol}")
            print("撤单原因: 系统自动撤单或手动撤单")
        elif status == THOST_FTDC_OST_AllTraded:
            print(f"订单全部成交 - 订单号: {orderid}, 合约: {symbol}")
        elif status == THOST_FTDC_OST_PartTradedQueueing:
            print(f"订单部分成交，剩余在队列中 - 订单号: {orderid}, 合约: {symbol}")
        elif status == THOST_FTDC_OST_NoTradeQueueing:
            print(f"订单未成交，在队列中等待 - 订单号: {orderid}, 合约: {symbol}")
        elif status == THOST_FTDC_OST_NoTradeNotQueueing:
            print(f"订单未成交且不在队列中 - 订单号: {orderid}, 合约: {symbol}")
            print("可能原因: 价格超出涨跌停板、资金不足、合约不存在等")

        print(f"状态变化: {old_status} -> {status_name}")


    def onRtnTrade(self, data: dict) -> None:
        """
        成交通知，报单发出后有成交则通过此接口返回。私有流
        :param data: 成交  
        :return: None
        """
        print("ctp td api callback: onRtnTrade")
        if not data or "InstrumentID" not in data:
            print("成交回报数据不完整")
            return

        # 验证必要的订单系统ID映射
        if "OrderSysID" not in data:
            print(f"成交回报缺少订单系统ID映射: {data.get('OrderSysID', 'N/A')}")
            return

        trade_id = data["TradeID"]
        order_id: str = data["OrderSysID"]
        price = data["Price"]
        volume = data["Volume"]
        trade_date: str = data['TradeDate']
        trade_time: str = data['TradeTime']

        print(f"onRtnTrade trade_id: {trade_id}, order_id: {order_id}, price: {price}, volume: {volume}, "
              f"trade_date: {trade_date}, trade_time: {trade_time}")


    def onRspOrderAction(self, data: dict, error: dict, reqid: SupportsInt, last: bool) -> None:
        """
        报单操作请求响应，当执行ReqOrderAction后有字段填写不对之类的CTP报错则通过此接口返回

        ActionFlag：目前只有删除（撤单）的操作，修改（改单）的操作还没有，可以通过撤单之后重新报单实现。
        :param data: 输入报单操作
        :param error: 响应信息
        :param reqid: 返回用户操作请求的ID，该ID 由用户在操作请求时指定。
        :param last: 指示该次返回是否为针对nRequestID的最后一次返回。
        :return: None
        """
        # 交易撤单失败
        print("交易撤单失败", error)

    def connect(self, address: str, userid: str, password: str, broker_id: str, auth_code: str, appid: str) -> None:
        """
        连接交易服务器  连接交易服务器
        :param address: 交易服务器地址  Trading server address
        :param userid:
        :param password:
        :param broker_id:
        :param auth_code:
        :param appid:
        :return:
        """
        self.userid = userid
        self.password = password
        self.broker_id = broker_id
        self.auth_code = auth_code
        self.appid = appid

        # 定义连接的是生产还是评测前置，true:使用生产版本的API false:使用测评版本的API
        is_production_mode = True

        if not self.connect_status:
            ctp_con_dir: Path = Path.cwd().joinpath("con")

            if not ctp_con_dir.exists():
                ctp_con_dir.mkdir()

            api_path_str = str(ctp_con_dir) + "/td"
            print("CtpTdApi: Attempting to create an API with path {}".format(api_path_str))
            try:
                # 创建TraderApi实例  Create a TraderApi instance
                self.createFtdcTraderApi(api_path_str.encode("GBK").decode("utf-8"), is_production_mode)
                print("CtpTdApi: createFtdcTraderApi call succeeded.")
            except Exception as e_create:
                print("CtpTdApi: createFtdcTraderApi failed! Error: {}".format(e_create))
                print("CtpTdApi:createFtdcTraderApi Traceback: {}".format(traceback.format_exc()))
                return
            # 订阅私有流和公共流。
            # 私有流重传方式
            # THOST_TERT_RESTART: 从本交易日开始重传
            # THOST_TERT_RESUME: 从上次收到的续传
            # THOST_TERT_QUICK: 只传送登录后私有流/公有流的内容
            # 该方法要在Init方法前调用。若不调用则不会收到私有流/公有流的数据。
            self.subscribePrivateTopic(THOST_TERT_QUICK)
            self.subscribePublicTopic(THOST_TERT_QUICK)

            self.registerFront(address)
            print("CtpTdApi：尝试使用地址初始化 API：{}...".format(address))
            try:
                self.init()
                print("CtpTdApi：init 调用成功。")
            except Exception as e_init:
                print("CtpTdApi：初始化失败！错误：{}".format(e_init))
                print("CtpTdApi：初始化回溯：{}".format(traceback.format_exc()))
                return

            self.connect_status = True
        else:
            print("CtpTdApi：已连接，正在尝试身份验证。")
            self.authenticate()

    def authenticate(self) -> None:
        """
        发起授权验证
        :return:
        """
        print(f"开始认证，auth_status: {self.auth_status}")
        if self.auth_status:
            print("已经认证过，跳过认证")
            return

        ctp_req: dict = {
            "UserID": self.userid,
            "BrokerID": self.broker_id,
            "AuthCode": self.auth_code,
            "AppID": self.appid
        }

        self.req_id += 1
        print(f"发送认证请求，req_id: {self.req_id}")
        self.reqAuthenticate(ctp_req, self.req_id)


    def login(self) -> None:
        """
        用户登录
        :return:
        """
        print(f"开始登录，login_status: {self.login_status}")
        if self.login_status:
            print("已经登录过，跳过登录")
            return

        ctp_req: dict = {
            "BrokerID": self.broker_id,
            "UserID": self.userid,
            "Password": self.password
        }

        self.req_id += 1
        print(f"发送登录请求，req_id: {self.req_id}")
        self.reqUserLogin(ctp_req, self.req_id)

    def send_order(self, symbol: str, direction: str, price: float, volume: int) -> str:
        """
        委托下单
        :return:
        """
        self.order_ref += 1

        exchange_id = self.symbol_map.get(symbol)

        if direction == "BUY_OPEN":
            direction_field = THOST_FTDC_D_Buy  # 买卖方向
            comb_offset_flag = '0'  # 开平标志
        elif direction == "BUY_CLOSE":
            direction_field = THOST_FTDC_D_Buy
            comb_offset_flag = '1'
        elif direction == "SELL_OPEN":
            direction_field = THOST_FTDC_D_Sell
            comb_offset_flag = '0'
        elif direction == "SELL_CLOSE":
            direction_field = THOST_FTDC_D_Sell
            comb_offset_flag = '1'
        elif direction == "BUY_CLOSE_TODAY":
            direction_field = THOST_FTDC_D_Buy
            comb_offset_flag = THOST_FTDC_OF_CloseToday
        elif direction == "SELL_CLOSE_TODAY":
            direction_field = THOST_FTDC_D_Sell
            comb_offset_flag = THOST_FTDC_OF_CloseToday
        else:
            print("不支持的买卖方向：{}".format(direction))
            return ""

        ctp_req: dict = {
            "BrokerID": self.broker_id,
            "InvestorID": self.userid,
            "InstrumentID": symbol,
            "OrderRef": str(self.order_ref),
            "UserID": self.userid,
            "CombOffsetFlag": comb_offset_flag,  # 开平标志
            "CombHedgeFlag": THOST_FTDC_HF_Speculation,  # 投机套保标志，投机
            "GTDDate": "",  # GTD日期
            "ExchangeID": exchange_id,  # 交易所代码
            "InvestUnitID": "",  # 投资单元代码
            "AccountID": "",  # 投资者帐号
            "CurrencyID": "",  # 币种代码
            "ClientID": "",  # 客户代码
            "VolumeTotalOriginal": volume,  # 数量
            "MinVolume": 1,  # 最小成交量
            "IsAutoSuspend": 0,  # 自动挂起标志
            "RequestID": self.req_id,  # 请求编号
            "UserForceClose": 0,  # 用户强平标志
            "IsSwapOrder": 0,  # 互换单标志
            "OrderPriceType": THOST_FTDC_OPT_LimitPrice,  # 报单价格条件，普通限价单的默认参数
            "Direction": direction_field,  # 买卖方向
            "TimeCondition": THOST_FTDC_TC_GFD,  # 有效期类型，当日有效
            "VolumeCondition": THOST_FTDC_VC_AV,  # 成交量类型，任意数量
            "ContingentCondition": THOST_FTDC_CC_Immediately,  # 触发条件
            "ForceCloseReason": THOST_FTDC_FCC_NotForceClose,  # 强平原因，非强平
            "LimitPrice": price,  # 价格
            "StopPrice": 0  # 止损价
        }

        self.req_id += 1
        try:
            ret_code: int = self.reqOrderInsert(ctp_req, self.req_id)
            if ret_code == 0:
                print("委托请求发送成功")
            else:
                print("委托请求发送失败，错误代码：{}".format(ret_code))
                return ""
        except RuntimeError as e:
            print("CtpTdApi：reqOrderInsert 运行时错误！错误：{}".format(e))
            print("CtpTdApi：reqOrderInsert 回溯：{}".format(traceback.format_exc()))

        orderid: str = f"{self.front_id}_{self.session_id}_{self.order_ref}"
        print("委托下单成功，委托号：{}".format(orderid))
        self.order_queue.put(orderid)  # 存入委托号

        return orderid

    def cancel_order(self, symbol: str) -> None:
        """
        委托撤单
        :return:
        """
        front_id, session_id, order_ref = self.order_queue.get().split("_")

        ctp_req: dict = {
            "BrokerID": self.broker_id,
            "InvestorID": self.userid,
            "OrderRef": order_ref,
            "ExchangeID": self.symbol_map.get(symbol),
            "UserID": self.userid,
            "InstrumentID": symbol,
            "FrontID": int(front_id),
            "SessionID": int(session_id),
            "ActionFlag": THOST_FTDC_AF_Delete,  # 操作标志
        }

        self.req_id += 1
        self.reqOrderAction(ctp_req, self.req_id)

    def get_order_status_summary(self) -> None:
        """
        获取所有订单状态汇总
        :return:
        """
        print("\n" + "="*50)
        print(" 订单状态汇总")
        print("="*50)
        
        if not self.order_status_map:
            print(" 暂无订单记录")
            return
            
        for orderid, status in self.order_status_map.items():
            status_name = self.order_status_names.get(status, f"未知状态({status})")
            print(f"订单号: {orderid} | 状态: {status_name}")
            
        print("="*50 + "\n")

    def close(self) -> None:
        """
        关闭连接
        :return:
        """
        if self.connect_status:
            self.exit()


class OrderTrader(object):

    def __init__(self) -> None:
        # 交易接口实例
        self.td_api: CtpTdApi | None = None

    def connect(self, setting: dict) -> None:
        """
        连接交易服务器
        :param setting:
        :return:
        """
        if not self.td_api:
            self.td_api = CtpTdApi()

        # 兼容性配置字段处理
        userid: str = setting.get("user_id", "")            # 用户名
        password: str = setting.get("password", "")         # 密码
        broker_id: str = setting.get("broker_id", "")       # 经纪商代码
        td_address: str = setting.get("td_address", "")     # 交易服务器
        appid: str = setting.get("appid", "")               # 产品名称
        auth_code: str = setting.get("auth_code", "")       # 授权编码

        # 验证必需字段
        if not all([userid, password, broker_id, td_address]):
            missing_fields = []
            if not userid: missing_fields.append("user_id")
            if not password: missing_fields.append("password")
            if not broker_id: missing_fields.append("broker_id")
            if not td_address: missing_fields.append("td_address")
            raise ValueError(f"CTP交易网关连接参数不完整，缺少字段: {missing_fields}")

        self.td_api.connect(td_address, userid, password, broker_id, auth_code, appid)


    def send_order(self, symbol: str, direction: str, price: float, volume: int) -> str:
        """
        委托下单
        :return:
        """
        if not self.td_api or not self.td_api.connect_status:
            print("无法发送订单：交易接口未连接或未初始化。")
            return ""
        print("正在委托下单...")
        print(f"symbol: {symbol}")
        print(f"direction: {direction}")
        print(f"price: {price}")
        print(f"volume: {volume}")
        return self.td_api.send_order(symbol, direction, price, volume)


    def cancel_order(self, symbol: str) -> None:
        """
        委托撤单
        :return:
        """
        if not self.td_api or not self.td_api.connect_status:
            print("无法撤销订单：交易接口未连接或未初始化。")
            return
        print("正在撤单...")
        print(f"symbol: {symbol}")
        self.td_api.cancel_order(symbol)


    def get_order_status_summary(self) -> None:
        """
        获取订单状态汇总
        :return:
        """
        if self.td_api:
            self.td_api.get_order_status_summary()
        else:
            print("交易接口未初始化")

    def close(self) -> None:
        """
        关闭接口
        :return:
        """
        if self.td_api and self.td_api.connect_status:
            self.td_api.close()


if __name__ == '__main__':
    import time

    # thanks to openctp
    ctp_config = {
        "td_address": "tcp://trading.openctp.cn:30001",  # 交易服务器地址 Trade server address
        "broker_id": "9999",  # 经纪商代码 Broker Code
        "user_id": "18340",  # 用户代码 User Code
        "password": "123456",  # password
        "appid": "",
        "auth_code": ""
    }

    trader = OrderTrader()
    trader.connect(setting=ctp_config)

    # 等待连接和登录完成
    print("Waiting for connection and login to complete...")
    time.sleep(3)

    # 报单一些常用的期货合约（SimNow模拟环境中的活跃合约）
    print("\n 开始下单测试...")
    ret_order_id = trader.send_order("SA609", "BUY_OPEN", 1286, 1)
    print(f"下单完成，订单号: {ret_order_id}")
    
    # 等待一段时间观察订单状态
    print("\n 等待5秒观察订单状态...")
    time.sleep(5)
    
    # 显示订单状态汇总
    trader.get_order_status_summary()

    # # 如果需要测试撤单，可以取消注释下面的代码
    # print("\n 测试撤单...")
    # trader.cancel_order("SA601")
    # time.sleep(2)
    # trader.get_order_status_summary()

    try:
        # 保持程序运行60秒来观察订单状态变化
        
        for i in range(12):  # 60秒分成12个5秒间隔
            time.sleep(5)
            print(f"\n 时间检查点 {i+1}/12 (已运行{(i+1)*5}秒)")
            trader.get_order_status_summary()
            
    except KeyboardInterrupt:
        print("\n 用户中断程序")
    finally:
        print("\n 最终订单状态汇总:")
        trader.get_order_status_summary()
        print(" 正在关闭连接...")
        trader.close()
        print(" 程序结束")
