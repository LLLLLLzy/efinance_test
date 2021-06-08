from typing import Dict, List, Union
from retry import retry
from urllib.parse import urlencode
import pandas as pd
import requests
from .utils import (gen_secid,
                    get_stock_market_type,
                    update_local_market_stocks_info)
from .config import (EastmoneyKlines,
                     EastmoneyHeaders,
                     EastmoneyBills,
                     EastmoneyQuotes,
                     EastmoneyStockInfo)
import multitasking
import signal
from tqdm import tqdm

signal.signal(signal.SIGINT, multitasking.killall)


def get_base_info_single(stock_code: str) -> pd.Series:
    '''
    获取股票基本信息

    Parameters
    ----------
    stock_code : 6 位股票代码

    Return
    -------
    Series : 包含单只股票基本信息
    '''
    fields = ",".join(EastmoneyStockInfo.keys())
    params = (
        ('ut', 'fa5fd1943c7b386f172d6893dbfba10b'),
        ('invt', '2'),
        ('fltt', '2'),
        ('fields', fields),
        ('secid', gen_secid(stock_code)),

    )

    json_response = requests.get('http://push2.eastmoney.com/api/qt/stock/get',
                                 headers=EastmoneyHeaders,
                                 params=params).json()

    s = pd.Series(json_response['data']).rename(index=EastmoneyStockInfo)
    return s[EastmoneyStockInfo.values()]


def get_base_info_muliti(stock_codes: List[str]) -> pd.Series:
    '''
    获取股票多只基本信息

    Parameters
    ----------
    stock_codes : 6 位股票代码列表

    Return
    -------
    DataFrame : 包含多只股票基本信息
    '''
    ss = []

    @multitasking.task
    def start(stock_code: str):
        s = get_base_info_single(stock_code)
        ss.append(s)
        bar.update()
        bar.set_description(f'processing {stock_code}')
    bar = tqdm(total=len(stock_codes))
    for stock_code in stock_codes:
        start(stock_code)
    multitasking.wait_for_tasks()
    df = pd.DataFrame(ss)
    return df


def get_base_info(stock_codes: Union[str, List[str]]) -> pd.Series:
    '''
    获取股票基本信息

    Parameters
    ----------
    stock_codes : 6 位股票代码 或 6 位股票代码构成的列表

    Return
    -------
    Series 或 DataFrane
        Series : 包含单只股票基本信息(当 stock_codes 是字符串时)
        DataFrane : 包含多只股票基本信息(当 stock_codes 是字符串列表时)

    '''
    if isinstance(stock_codes, str):
        return get_base_info_single(stock_codes)
    elif hasattr(stock_codes, '__iter__'):
        return get_base_info_muliti(stock_codes)
    raise TypeError(f'所给的 {stock_codes} 不符合参数要求')


def get_quote_history(stock_codes: str,
                      beg: str = '19000101',
                      end: str = '20500101',
                      klt: int = 101,
                      fqt: int = 1) -> pd.DataFrame:
    '''
    获取k线数据

    Parameters
    ----------
    stock_codes : 6 位股票代码 或者 6 位股票代码构成的列表
    beg : 开始日期 例如 20200101
    end : 结束日期 例如 20200201
    klt : k线间距 默认为 101 即日k
            klt : 1 1 分钟
            klt : 5 5 分钟
            klt : 101 日
            klt : 102 周
    fqt: 复权方式
            不复权 : 0
            前复权 : 1
            后复权 : 2 

    Return
    ------
    DateFrame : 包含股票k线数据

    '''
    if isinstance(stock_codes, str):
        return get_quote_history_single(stock_codes,
                                        beg=beg,
                                        end=end,
                                        klt=klt,
                                        fqt=fqt)
    elif hasattr(stock_codes, '__iter__'):
        stock_codes = list(stock_codes)
        return get_quote_history_multi(stock_codes,
                                       beg=beg,
                                       end=end,
                                       klt=klt,
                                       fqt=fqt)
    else:
        raise TypeError(
            '股票代码类型数据输入不正确！'
        )


def get_quote_history_single(stock_code: str,
                             beg: str = '19000101',
                             end: str = '20500101',
                             klt: int = 101,
                             fqt: int = 1) -> pd.DataFrame:
    '''
    获取k线数据

    Parameters
    ----------
    stock_code : 6 位股票代码
    beg : 开始日期 例如 20200101
    end : 结束日期 例如 20200201
    klt : k线间距 默认为 101 即日k
            klt : 1 1 分钟
            klt : 5 5 分钟
            klt : 101 日
            klt : 102 周
    fqt: 复权方式
            不复权 : 0
            前复权 : 1
            后复权 : 2 

    Return
    ------
    DateFrame : 包含股票k线数据

    '''

    fields = list(EastmoneyKlines.keys())
    columns = list(EastmoneyKlines.values())
    fields2 = ",".join(fields)
    secid = gen_secid(stock_code)
    params = (
        ('fields1', 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13'),
        ('fields2', fields2),
        ('beg', beg),
        ('end', end),
        ('rtntype', '6'),
        ('secid', secid),
        ('klt', f'{klt}'),
        ('fqt', f'{fqt}'),
    )
    base_url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
    url = base_url+'?'+urlencode(params)
    json_response = requests.get(
        url, headers=EastmoneyHeaders).json()
    data = json_response.get('data')
    if data is None:
        return pd.DataFrame(columns=columns)
    # 股票名称
    stock_name = data['name']
    klines: List[str] = data['klines']
    rows = [kline.split(',') for kline in klines]
    df = pd.DataFrame(rows, columns=columns)
    df.insert(0, '股票代码', [stock_code] * len(df))
    df.insert(0, '股票名称', [stock_name] * len(df))

    return df


def get_quote_history_multi(stock_codes: List[str],
                            beg: str = '19000101',
                            end: str = '20500101',
                            klt: int = 101,
                            fqt: int = 1,
                            tries: int = 3) -> Dict[str, pd.DataFrame]:
    '''
    获取多只股票历史行情信息

    Parameters
    ----------
    stock_codes : 多个 6 位股票代码的列表
    beg : 开始日期 例如 20200101
    end : 结束日期 例如 20200201
    klt : k线间距 默认为 101 即日k
            klt : 1 1 分钟
            klt : 5 5 分钟
            klt : 101 日
            klt : 102 周
    fqt: 复权方式
            不复权 : 0
            前复权 : 1
            后复权 : 2 

    Return
    ------
    DateFrame : 包含股票k线数据
    '''
    dfs: Dict[str, pd.DataFrame] = {}
    total = len(stock_codes)
    if total != 0:
        update_local_market_stocks_info()

    @retry(tries=tries)
    @multitasking.task
    def start(stock_code: str):
        _df = get_quote_history_single(
            stock_code, beg=beg, end=end, klt=klt, fqt=fqt)
        dfs[stock_code] = _df
        pbar.update(1)
        pbar.set_description_str(f'Processing: {stock_code}')

    pbar = tqdm(total=total)
    for stock_code in stock_codes:
        start(stock_code)
    multitasking.wait_for_tasks()
    pbar.close()
    return dfs


def get_realtime_quotes() -> pd.DataFrame:
    '''
    获取沪深全市场股票最新交易日最新时刻数据

    Parameters
    ----------
    无

    Return
    ------
    DataFrame
    '''
    # http://quote.eastmoney.com/center/gridlist.html#hs_a_board
    fields = ",".join(EastmoneyQuotes.keys())
    columns = list(EastmoneyQuotes.values())
    params = (

        ('pn', '1'),
        ('pz', '1000000'),
        ('po', '1'),
        ('np', '1'),
        ('fltt', '2'),
        ('invt', '2'),
        ('fid', 'f3'),
        ('fs', 'm:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23'),
        ('fields', fields),

    )

    json_response = requests.get(
        'http://76.push2.eastmoney.com/api/qt/clist/get',
        headers=EastmoneyHeaders,
        params=params).json()
    df = (pd.DataFrame(json_response['data']['diff'])
          .rename(columns=EastmoneyQuotes)
          [columns])
    return df


def get_history_bill(stock_code: str) -> pd.DataFrame:
    '''


    Parameters
    ----------
    code: 6 位股票代码

    Return
    ------
    DataFrame : 包含指定股票的历史单子数据

    '''

    fields = list(EastmoneyBills.keys())
    columns = list(EastmoneyBills.values())
    fields2 = ",".join(fields)
    secid = gen_secid(stock_code)
    params = (
        ('lmt', '100000'),
        ('klt', '101'),
        ('secid', secid),
        ('fields1', 'f1,f2,f3,f7'),
        ('fields2', fields2),

    )

    json_response = requests.get('http://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get',
                                 headers=EastmoneyHeaders, params=params).json()

    data = json_response.get('data')
    if data is None:
        return pd.DataFrame(columns=columns)
    klines: List[str] = data['klines']
    rows = [kline.split(',') for kline in klines]
    df = pd.DataFrame(rows, columns=columns)

    return df


def get_today_bill(stock_code: str) -> pd.DataFrame:
    '''
    获取超大单 大单 主力流入数据
    Parameters
    ----------
    stock_code : 6 位股票代码

    Return
    ------
    DataFrame : 包含指定股票全部日单子数据

    '''
    params = (
        ('lmt', '0'),
        ('klt', '1'),
        ('secid', gen_secid(stock_code)),
        ('fields1', 'f1,f2,f3,f7'),
        ('fields2', 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63'),
        ('ut', 'b2884a393a59ad64002292a3e90d46a5'),
    )

    json_response = requests.get('http://push2.eastmoney.com/api/qt/stock/fflow/kline/get',
                                 headers=EastmoneyHeaders, params=params).json()
    data = json_response['data']

    klines = data['klines']
    columns = ['时间', '主力净流入', '小单净流入', '中单净流入', '大单净流入', '超大单净流入']
    klines: List[str] = data['klines']
    rows = [kline.split(',') for kline in klines]
    df = pd.DataFrame(rows, columns=columns)
    df.insert(0, '股票代码', [stock_code for _ in range(len(df))])
    return df


def get_latest_stock_info(stock_codes: List[str]) -> pd.DataFrame:
    '''
    Parameters
    ----------
    stock_codes 多只股票代码列表

    Return
    ------   
    DataFrame : 多只股票涨跌情况
    '''
    secids = ",".join([gen_secid(code) for code in stock_codes])
    params = (
        ('MobileKey', '3EA024C2-7F22-408B-95E4-383D38160FB3'),
        ('OSVersion', '14.3'),
        ('appVersion', '6.3.8'),
        ('cToken', 'a6hdhrfejje88ruaeduau1rdufna1e--.6'),
        ('deviceid', '3EA024C2-7F22-408B-95E4-383D38160FB3'),
        ('fields', 'f1,f2,f3,f4,f12,f13,f14,f292'),
        ('fltt', '2'),
        ('passportid', '3061335960830820'),
        ('plat', 'Iphone'),
        ('product', 'EFund'),
        ('secids', secids),
        ('serverVersion', '6.3.6'),
        ('uToken', 'a166hhqnrajucnfcjkfkeducanekj1dd1cc2a-e9.6'),
        ('userId', 'f8d95b2330d84d9e804e7f28a802d809'),
        ('ut', '94dd9fba6f4581ffc558a7b1a7c2b8a3'),
        ('version', '6.3.8'),
    )

    response = requests.get(
        'https://push2.eastmoney.com/api/qt/ulist.np/get', headers=EastmoneyHeaders, params=params)
    columns = {
        'f2': '最新价',
        'f3': '最新涨跌幅',
        'f12': '股票代码',
        'f14': '股票简称'
    }
    data = response.json()['data']
    if data is None:

        return pd.DataFrame(columns=columns.values())
    diff = data['diff']
    df = pd.DataFrame(diff)[columns.keys()].rename(columns=columns)
    return df


def get_top10_stock_holder_info(stock_code: str, top: int = 4) -> pd.DataFrame:
    '''
    获取前十大股东信息

    Parameters
    ----------
    stock_code: 6 位股票代码
    top : 最新 top 个前 10 大流通股东公开信息

    Return
    ------
    DataFrame
    '''
    def gen_fc(stock_code: str) -> str:
        '''
        生成东方财富专用的secid

        Parameters
        ----------
        stock_code : 6 位股票代码

        Return
        ------
        str: 指定格式的字符串

        '''
        # 沪市指数
        _type = get_stock_market_type(stock_code)
        _type = int(_type)
        # 深市
        if _type == 0:
            return f'{stock_code}02'
        # 沪市
        return f'{stock_code}01'

    def get_public_dates(stock_code: str, top: int = 4) -> List[str]:
        '''
        获取指定股票公开股东信息的日期
        Parameters
        ----------
        stock_code : 6 位 A 股股票代码
        top : 最新的 top 个日期

        Return
        ------
        公开股东信息的日期列表

        '''
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 color=b eastmoney_ios appversion_9.3 pkg=com.eastmoney.iphone mainBagVersion=9.3 statusBarHeight=20.000000 titleBarHeight=44.000000 density=2.000000 fontsize=3',
            'Content-Type': 'application/json;charset=utf-8',
            'Host': 'emh5.eastmoney.com',
            'Origin': 'null',
            'Cache-Control': 'public',
        }
        fc = gen_fc(stock_code)
        data = {"fc": fc}
        response = requests.post(
            'https://emh5.eastmoney.com/api/GuBenGuDong/GetFirstRequest2Data', headers=headers, json=data)
        items: list[dict] = response.json()[
            'Result']['SDLTGDBGQ']
        items = items.get('ShiDaLiuTongGuDongBaoGaoQiList')

        if items is None:
            return []

        df = pd.DataFrame(items)
        if 'BaoGaoQi' not in df:
            return []
        dates = df['BaoGaoQi'][:top]
        return dates

    fields = {
        'GuDongDaiMa': '股东代码',
        'GuDongMingCheng': '股东名称',
        'ChiGuShu': '持股数',
        'ChiGuBiLi': '持股比例',
        'ZengJian': '增减',
        'BianDongBiLi': '变动率',

    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 color=b eastmoney_ios appversion_9.3 pkg=com.eastmoney.iphone mainBagVersion=9.3 statusBarHeight=20.000000 titleBarHeight=44.000000 density=2.000000 fontsize=3',
        'Content-Type': 'application/json;charset=utf-8',
        'Host': 'emh5.eastmoney.com',
        'Origin': 'null',
        'Cache-Control': 'public',
    }
    fc = gen_fc(stock_code)
    dates = get_public_dates(stock_code)
    dfs: List[pd.DataFrame] = []
    for date in dates[:top]:

        data = {"fc": fc, "BaoGaoQi": date}
        response = requests.post(
            'https://emh5.eastmoney.com/api/GuBenGuDong/GetShiDaLiuTongGuDong',
            headers=headers,
            json=data)
        response.encoding = 'utf-8'

        try:
            items: list[dict] = response.json(
            )['Result']['ShiDaLiuTongGuDongList']

        except:
            df = pd.DataFrame(columns=fields.values())
            df.insert(0, '股票代码', [stock_code for _ in range(len(df))])
            df.insert(1, '更新日期', [date for _ in range(len(df))])
            return df
        df = pd.DataFrame(items)
        df.rename(columns=fields, inplace=True)
        df.insert(0, '股票代码', [stock_code for _ in range(len(df))])
        df.insert(1, '更新日期', [date for _ in range(len(df))])
        del df['IsLink']
        dfs.append(df)

    return pd.concat(dfs, axis=0)