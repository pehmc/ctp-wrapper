"""
Copyright (c) 2026 pehmc. Apache 2.0 License.
See LICENSE file in the project root for full license information.
"""

import os
import locale
import sys
import traceback
from pathlib import Path
from typing import Any

# 设置 locale
os.environ['LC_ALL'] = 'C'
os.environ['LANG'] = 'C'
os.environ['LANGUAGE'] = 'C'
os.environ['LC_CTYPE'] = 'C'
try:
    locale.setlocale(locale.LC_ALL, 'C')
except locale.Error:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from ctp.api import CThostFtdcTraderApi, CThostFtdcTraderSpi, CThostFtdcReqUserLoginField
from ctp.api.tdapi import (
    THOST_TERT_QUICK,
    THOST_FTDC_OPT_LimitPrice, THOST_FTDC_D_Buy, THOST_FTDC_D_Sell,
    THOST_FTDC_OF_Open, THOST_FTDC_OF_CloseToday, THOST_FTDC_CC_Immediately,
    THOST_FTDC_HF_Speculation, THOST_FTDC_FCC_NotForceClose, THOST_FTDC_TC_GFD,
    THOST_FTDC_VC_AV, THOST_FTDC_AF_Delete, THOST_FTDC_OST_Unknown,
    THOST_FTDC_OST_AllTraded, THOST_FTDC_OST_PartTradedQueueing,
    THOST_FTDC_OST_PartTradedNotQueueing, THOST_FTDC_OST_NoTradeQueueing,
    THOST_FTDC_OST_NoTradeNotQueueing, THOST_FTDC_OST_Canceled,
    CThostFtdcReqAuthenticateField,
    CThostFtdcSettlementInfoConfirmField,
    CThostFtdcInputOrderField,
    CThostFtdcInputOrderActionField
)


class CtpConst:
    REASON_MAPPING = {
        0x1001: "网络读失败",
        0x1002: "网络写失败",
        0x2001: "接收心跳超时",
        0x2002: "发送心跳失败",
        0x2003: "收到错误报文"
    }


class TdSpi(CThostFtdcTraderSpi):
    def __init__(self, api: CThostFtdcTraderApi) -> None:
        super().__init__()
        self._api = api
        self.connect_status = False
        self.login_status = False
        self.auth_status = False
        self.settlement_confirmed = False
        self.broker_id: str = ""
        self.userid: str = ""
        self.password: str = ""
        self.auth_code: str = ""
        self.appid: str = ""

        self.front_id: int = 0
        self.session_id: int = 0

        # 订单状态跟踪
        self.order_status_map: dict = {}
        self.order_status_names = {
            THOST_FTDC_OST_Unknown: "未知",
            THOST_FTDC_OST_AllTraded: "全部成交",
            THOST_FTDC_OST_PartTradedQueueing: "部分成交还在队列中",
            THOST_FTDC_OST_PartTradedNotQueueing: "部分成交不在队列中",
            THOST_FTDC_OST_NoTradeQueueing: "未成交还在队列中",
            THOST_FTDC_OST_NoTradeNotQueueing: "未成交不在队列中",
            THOST_FTDC_OST_Canceled: "撤单"
        }

    def OnFrontConnected(self) -> None:
        print("TdSpi: OnFrontConnected - 前置机连接成功")
        self.connect_status = True
        if self.auth_code:
            self._authenticate()
        else:
            self._login()

    def OnFrontDisconnected(self, nReason: int) -> None:
        self.connect_status = False
        self.login_status = False
        self.auth_status = False
        self.settlement_confirmed = False
        print(f"TdSpi: OnFrontDisconnected - reason={nReason}")

    def OnRspAuthenticate(self, pRspAuthenticateField, pRspInfoField, nRequestID, bIsLast) -> None:
        if pRspInfoField and pRspInfoField.ErrorID != 0:
            print(f"TdSpi: 认证失败 ErrorID={pRspInfoField.ErrorID}, ErrorMsg={pRspInfoField.ErrorMsg}")
            self.auth_status = False
        else:
            print("TdSpi: 认证成功")
            self.auth_status = True
            self._login()

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast) -> None:
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"TdSpi: 登录失败 ErrorID={pRspInfo.ErrorID}, ErrorMsg={pRspInfo.ErrorMsg}")
            self.login_status = False
        else:
            print("TdSpi: 登录成功")
            self.login_status = True
            if pRspUserLogin:
                self.front_id = pRspUserLogin.FrontID
                self.session_id = pRspUserLogin.SessionID
            self._confirm_settlement()

    def OnRspUserLogout(self, pUserLogout, pRspInfo, nRequestID, bIsLast) -> None:
        print("TdSpi: 登出响应")
        self.login_status = False

    def OnRspSettlementInfoConfirm(self, pSettlementInfoConfirm, pRspInfo, nRequestID, bIsLast) -> None:
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"TdSpi: 结算单确认失败 ErrorID={pRspInfo.ErrorID}, ErrorMsg={pRspInfo.ErrorMsg}")
        else:
            print("TdSpi: 结算单确认成功")
            self.settlement_confirmed = True

    def OnRspOrderInsert(self, pInputOrder, pRspInfo, nRequestID, bIsLast) -> None:
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"TdSpi: 报单录入失败 ErrorID={pRspInfo.ErrorID}, ErrorMsg={pRspInfo.ErrorMsg}")

    def OnRtnOrder(self, pOrder) -> None:
        if not pOrder:
            return
        order_ref = pOrder.OrderRef
        orderid = f"{pOrder.FrontID}_{pOrder.SessionID}_{order_ref}"
        status = pOrder.OrderStatus
        status_name = self.order_status_names.get(status, f"未知状态({status})")
        print(f"TdSpi: 订单状态更新 - 订单ID: {orderid}, 状态: {status_name}")
        self.order_status_map[orderid] = status

    def OnRtnTrade(self, pTrade) -> None:
        if not pTrade:
            return
        print(f"TdSpi: 成交通知 - 合约: {pTrade.InstrumentID}, 价格: {pTrade.Price}, "
              f"数量: {pTrade.Volume}, 成交ID: {pTrade.TradeID}")

    def _authenticate(self) -> None:
        """发送认证请求"""
        req = CThostFtdcReqAuthenticateField()
        req.BrokerID = self.broker_id
        req.UserID = self.userid
        req.AuthCode = self.auth_code
        req.AppID = self.appid

        ret = self._api.ReqAuthenticate(req, 1)
        print(f"TdSpi: ReqAuthenticate 返回 {ret}")

    def _login(self) -> None:
        """发送登录请求"""
        req = CThostFtdcReqUserLoginField()
        req.BrokerID = self.broker_id
        req.UserID = self.userid
        req.Password = self.password

        ret = self._api.ReqUserLogin(req, 1)
        print(f"TdSpi: ReqUserLogin 返回 {ret}")

    def _confirm_settlement(self) -> None:
        """确认结算单"""
        req = CThostFtdcSettlementInfoConfirmField()
        req.BrokerID = self.broker_id
        req.InvestorID = self.userid

        ret = self._api.ReqSettlementInfoConfirm(req, 1)
        print(f"TdSpi: ReqSettlementInfoConfirm 返回 {ret}")


class CtpTdApi:
    def __init__(self) -> None:
        self._api: CThostFtdcTraderApi | None = None
        self._spi: TdSpi | None = None
        self.broker_id: str = ""
        self.userid: str = ""
        self.password: str = ""
        self.auth_code: str = ""
        self.appid: str = ""

        self.req_id: int = 0
        self.order_ref: int = 0
        self.symbol_map: dict = {"SA609": "CZCE"}

    @property
    def connect_status(self) -> bool:
        """从前置机连接状态"""
        return self._spi.connect_status if self._spi else False

    @property
    def login_status(self) -> bool:
        """登录状态"""
        return self._spi.login_status if self._spi else False

    @property
    def settlement_confirmed(self) -> bool:
        """结算单确认状态"""
        return self._spi.settlement_confirmed if self._spi else False

    def connect(self, address: str, broker_id: str, userid: str, password: str, 
               auth_code: str = "", appid: str = "") -> None:
        self.broker_id = broker_id
        self.userid = userid
        self.password = password
        self.auth_code = auth_code
        self.appid = appid

        ctp_con_dir = Path.cwd() / "con" / "td"
        ctp_con_dir.parent.mkdir(parents=True, exist_ok=True)

        # 工厂方法创建 API
        self._api = CThostFtdcTraderApi.CreateFtdcTraderApi(str(ctp_con_dir), False)
        print(f"CtpTdApi: CreateFtdcTraderApi 成功")

        # 创建 SPI，并把登录信息传过去
        self._spi = TdSpi(self._api)
        self._spi.broker_id = broker_id
        self._spi.userid = userid
        self._spi.password = password
        self._spi.auth_code = auth_code
        self._spi.appid = appid

        self._api.RegisterSpi(self._spi)
        self._api.RegisterFront(address)
        self._api.SubscribePublicTopic(THOST_TERT_QUICK)
        self._api.SubscribePrivateTopic(THOST_TERT_QUICK)
        self._api.Init()
        print(f"CtpTdApi: Init 已调用")

    def send_order(self, symbol: str, direction: str, price: float, volume: int) -> str:
        """发送订单"""
        if not self._api or not self._spi:
            print("CtpTdApi: API 未初始化")
            return ""

        if not self.login_status:
            print("CtpTdApi: 未登录，无法下单")
            return ""

        self.order_ref += 1

        # 确定买卖方向
        if direction == "BUY_OPEN":
            direction_field = THOST_FTDC_D_Buy
            comb_offset_flag = '0'
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
            print(f"CtpTdApi: 不支持的买卖方向: {direction}")
            return ""

        req = CThostFtdcInputOrderField()
        req.BrokerID = self.broker_id
        req.InvestorID = self.userid
        req.InstrumentID = symbol
        req.OrderRef = str(self.order_ref)
        req.UserID = self.userid
        req.CombOffsetFlag = comb_offset_flag
        req.CombHedgeFlag = THOST_FTDC_HF_Speculation
        req.ExchangeID = self.symbol_map.get(symbol, "")
        req.VolumeTotalOriginal = volume
        req.MinVolume = 1
        req.IsAutoSuspend = 0
        req.UserForceClose = 0
        req.IsSwapOrder = 0
        req.LimitPrice = price
        req.OrderPriceType = THOST_FTDC_OPT_LimitPrice
        req.TimeCondition = THOST_FTDC_TC_GFD
        req.VolumeCondition = THOST_FTDC_VC_AV
        req.ContingentCondition = THOST_FTDC_CC_Immediately
        req.ForceCloseReason = THOST_FTDC_FCC_NotForceClose

        ret = self._api.ReqOrderInsert(req, self.req_id + 1)
        orderid = f"{self._spi.front_id}_{self._spi.session_id}_{self.order_ref}"
        print(f"CtpTdApi: ReqOrderInsert({symbol}) 返回 {ret}, 订单ID: {orderid}")
        return orderid

    def cancel_order(self, orderid: str) -> None:
        """撤销订单"""
        if not self._api or not self._spi:
            print("CtpTdApi: API 未初始化")
            return

        try:
            front_id, session_id, order_ref = orderid.split('_')
            req = CThostFtdcInputOrderActionField()
            req.BrokerID = self.broker_id
            req.InvestorID = self.userid
            req.OrderRef = order_ref
            req.FrontID = int(front_id)
            req.SessionID = int(session_id)
            req.ActionFlag = THOST_FTDC_AF_Delete

            ret = self._api.ReqOrderAction(req, self.req_id + 1)
            print(f"CtpTdApi: ReqOrderAction({orderid}) 返回 {ret}")
        except Exception as e:
            print(f"CtpTdApi: 撤单失败: {e}")

    def get_order_status_summary(self) -> None:
        """获取订单状态汇总"""
        if self._spi and self._spi.order_status_map:
            print(f"CtpTdApi: 订单状态汇总 (共 {len(self._spi.order_status_map)} 个订单):")
            for orderid, status in self._spi.order_status_map.items():
                status_name = self._spi.order_status_names.get(status, f"未知({status})")
                print(f"  {orderid}: {status_name}")
        else:
            print("CtpTdApi: 暂无订单")

    def close(self) -> None:
        if self._api:
            self._api.Release()
            self._api = None
            self._spi = None
            print("CtpTdApi: 已释放")


class OrderTrader:
    """交易业务入口类"""

    def __init__(self):
        self.td_api: CtpTdApi | None = None

    def connect(self, setting: dict[str, Any]) -> None:
        try:
            td_address = setting.get("td_address", "")
            broker_id = setting.get("broker_id", "")
            user_id = setting.get("user_id", "")
            password = setting.get("password", "")
            appid = setting.get("appid", "")
            auth_code = setting.get("auth_code", "")

            if not all([td_address, broker_id, user_id, password]):
                raise ValueError("缺少必要的连接参数")

            self.td_api = CtpTdApi()
            self.td_api.connect(td_address, broker_id, user_id, password, auth_code, appid)

        except Exception as e:
            print(f"连接失败: {e}")
            traceback.print_exc()
            if self.td_api:
                self.td_api.close()

    def send_order(self, symbol: str, direction: str, price: float, volume: int) -> str:
        if self.td_api:
            return self.td_api.send_order(symbol, direction, price, volume)
        else:
            print("交易 API 未连接")
            return ""

    def cancel_order(self, orderid: str) -> None:
        if self.td_api:
            self.td_api.cancel_order(orderid)
        else:
            print("交易 API 未连接")

    def get_order_status_summary(self) -> None:
        if self.td_api:
            self.td_api.get_order_status_summary()
        else:
            print("交易 API 未连接")

    def close(self) -> None:
        if self.td_api:
            self.td_api.close()
            self.td_api = None


if __name__ == '__main__':
    import time

    ctp_config = {
        "td_address": "tcp://trading.openctp.cn:30001",
        "broker_id": "9999",
        "user_id": "18340",
        "password": "123456",
        "appid": "",
        "auth_code": ""
    }

    trader = OrderTrader()
    trader.connect(setting=ctp_config)

    # 等待连接和登录（CTP 是异步的）
    print("等待连接...")
    for _ in range(30):
        if trader.td_api and trader.td_api.connect_status:
            break
        time.sleep(0.1)

    if not trader.td_api or not trader.td_api.connect_status:
        print("连接超时")
        trader.close()
        sys.exit(1)

    print("等待登录...")
    for _ in range(50):
        if trader.td_api.login_status and trader.td_api.settlement_confirmed:
            break
        time.sleep(0.1)

    if not trader.td_api.login_status or not trader.td_api.settlement_confirmed:
        print("登录或结算单确认超时")
        trader.close()
        sys.exit(1)

    # 下单测试
    print("\n开始下单测试...")
    order_id = trader.send_order("SA609", "BUY_OPEN", 1286, 1)
    print(f"下单完成，订单号: {order_id}")

    # 等待一段时间观察订单状态
    print("\n等待5秒观察订单状态...")
    time.sleep(5)

    # 显示订单状态汇总
    trader.get_order_status_summary()

    # 接收订单和成交回报
    print("开始接收订单和成交回报，按 Ctrl+C 退出...")
    try:
        time.sleep(60)
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        print("\n最终订单状态汇总:")
        trader.get_order_status_summary()
        trader.close()
        print("程序结束")