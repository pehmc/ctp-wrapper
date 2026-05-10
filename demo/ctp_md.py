import os
import locale
import sys
import traceback
from pathlib import Path
from datetime import datetime
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
from ctp.api import CThostFtdcMdApi, CThostFtdcMdSpi, CThostFtdcReqUserLoginField


class CtpConst:
    REASON_MAPPING = {
        0x1001: "网络读失败",
        0x1002: "网络写失败",
        0x2001: "接收心跳超时",
        0x2002: "发送心跳失败",
        0x2003: "收到错误报文"
    }


class MdSpi(CThostFtdcMdSpi):
    def __init__(self, api: CThostFtdcMdApi) -> None:
        super().__init__()
        self._api = api
        self.connect_status = False
        self.login_status = False
        self.subscribe_symbol: set = set()
        self.broker_id: str = ""
        self.userid: str = ""
        self.password: str = ""

    def OnFrontConnected(self) -> None:
        print("MdSpi: OnFrontConnected - 前置机连接成功")
        self.connect_status = True
        self._login()

    def OnFrontDisconnected(self, nReason: int) -> None:
        self.connect_status = False
        self.login_status = False
        print(f"MdSpi: OnFrontDisconnected - reason={nReason}")

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast) -> None:
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"MdSpi: 登录失败 ErrorID={pRspInfo.ErrorID}, ErrorMsg={pRspInfo.ErrorMsg}")
            self.login_status = False
        else:
            print("MdSpi: 登录成功")
            self.login_status = True

    def OnRspSubMarketData(self, pSpecificInstrument, pRspInfo, nRequestID, bIsLast) -> None:
        symbol = pSpecificInstrument.InstrumentID if pSpecificInstrument else "?"
        print(f"MdSpi: 订阅响应 {symbol}")

    def OnRtnDepthMarketData(self, pDepthMarketData) -> None:
        if not pDepthMarketData:
            return
        print(f"[{pDepthMarketData.UpdateTime}] {pDepthMarketData.InstrumentID} "
              f"LastPrice={pDepthMarketData.LastPrice}")

    def _login(self) -> None:
        """发送登录请求"""
        # 创建结构体
        req = CThostFtdcReqUserLoginField()
        req.BrokerID = self.broker_id
        req.UserID = self.userid
        req.Password = self.password

        ret = self._api.ReqUserLogin(req, 1)
        print(f"MdSpi: ReqUserLogin 返回 {ret}")


class CtpMdApi:
    def __init__(self) -> None:
        self._api: CThostFtdcMdApi | None = None
        self._spi: MdSpi | None = None
        self.broker_id: str = ""
        self.userid: str = ""
        self.password: str = ""

    @property
    def connect_status(self) -> bool:
        """从前置机连接状态"""
        return self._spi.connect_status if self._spi else False

    @property
    def login_status(self) -> bool:
        """登录状态"""
        return self._spi.login_status if self._spi else False

    def connect(self, address: str, broker_id: str, userid: str, password: str) -> None:
        self.broker_id = broker_id
        self.userid = userid
        self.password = password

        ctp_con_dir = Path.cwd() / "con" / "md"
        ctp_con_dir.parent.mkdir(parents=True, exist_ok=True)

        # 工厂方法创建 API
        self._api = CThostFtdcMdApi.CreateFtdcMdApi(str(ctp_con_dir), False, False, True)
        print(f"CtpMdApi: CreateFtdcMdApi 成功")

        # 创建 SPI，并把登录信息传过去
        self._spi = MdSpi(self._api)
        self._spi.broker_id = broker_id
        self._spi.userid = userid
        self._spi.password = password

        self._api.RegisterSpi(self._spi)
        self._api.RegisterFront(address)
        self._api.Init()
        print(f"CtpMdApi: Init 已调用")

    def subscribe(self, symbol: str) -> None:
        if not self._api or not self._spi:
            print("CtpMdApi: API 未初始化")
            return

        if not self.login_status:
            print(f"CtpMdApi: 未登录，缓存订阅 {symbol}")
            self._spi.subscribe_symbol.add(symbol)
            return

        if symbol in self._spi.subscribe_symbol:
            print(f"CtpMdApi: {symbol} 已订阅")
            return

        ret = self._api.SubscribeMarketData([symbol], 1)
        print(f"CtpMdApi: SubscribeMarketData({symbol}) 返回 {ret}")
        self._spi.subscribe_symbol.add(symbol)

    def close(self) -> None:
        if self._api:
            self._api.Release()
            self._api = None
            self._spi = None
            print("CtpMdApi: 已释放")


class MarketData:
    """业务入口类"""

    def __init__(self):
        self.md_api: CtpMdApi | None = None

    def connect(self, setting: dict[str, Any]) -> None:
        try:
            md_address = setting.get("md_address", "")
            broker_id = setting.get("broker_id", "")
            user_id = setting.get("user_id", "")
            password = setting.get("password", "")

            if not all([md_address, broker_id, user_id, password]):
                raise ValueError("缺少必要的连接参数")

            self.md_api = CtpMdApi()
            self.md_api.connect(md_address, broker_id, user_id, password)

        except Exception as e:
            print(f"连接失败: {e}")
            traceback.print_exc()
            if self.md_api:
                self.md_api.close()

    def subscribe(self, symbol: str) -> None:
        if self.md_api:
            self.md_api.subscribe(symbol)
        else:
            print("行情 API 未连接")

    def close(self) -> None:
        if self.md_api:
            self.md_api.close()
            self.md_api = None


if __name__ == '__main__':
    import time

    ctp_config = {
        "md_address": "tcp://trading.openctp.cn:30011",
        "broker_id": "9999",
        "user_id": "18340",
        "password": "123456",
    }

    market = MarketData()
    market.connect(setting=ctp_config)

    # 等待连接和登录（CTP 是异步的）
    print("等待连接...")
    for _ in range(30):
        if market.md_api and market.md_api.connect_status:
            break
        time.sleep(0.1)

    if not market.md_api or not market.md_api.connect_status:
        print("连接超时")
        market.close()
        sys.exit(1)

    # 登录（通常在 OnFrontConnected 后自动触发，但这里显式调用）
    # market.md_api.login()

    print("等待登录...")
    for _ in range(50):
        if market.md_api.login_status:
            break
        time.sleep(0.1)

    if not market.md_api.login_status:
        print("登录超时")
        market.close()
        sys.exit(1)

    # 订阅合约
    contracts = ["SA609", "FG609"]
    for contract in contracts:
        market.subscribe(contract)
        time.sleep(1)

    # 接收行情
    print("开始接收行情，按 Ctrl+C 退出...")
    try:
        time.sleep(60)
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        market.close()