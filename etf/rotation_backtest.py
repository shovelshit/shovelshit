#!/usr/bin/env python3
"""
ETF轮动策略回测 (使用akshare获取A股ETF数据)
- 标的：黄金ETF(518880)、创业板ETF(159915)、纳指ETF(513100)、红利低波ETF(512890)
- 条件1：收盘价站在60日均线上
- 条件2：满足条件1的标的中，近20日涨幅排名第一
- 操作：每周五收盘全仓买入排名第一的ETF，持有至下周五再判断
- 回测区间：2019-01-18 至今
"""

import sys
import time

import akshare as ak
import pandas as pd
import numpy as np
import requests
from datetime import datetime

etfs = {
    '518880': '黄金ETF',
    '159915': '创业板ETF',
    '513100': '纳指ETF',
    '512890': '红利低波ETF',
}

start_date = '20180901'
end_date = datetime.now().strftime('%Y%m%d')

MAX_RETRIES = 4        # 数据源偶发限流/断连时的最大重试次数
RETRY_BACKOFF_SEC = 3  # 每次重试的等待时间（秒），逐次递增

# 东方财富接口在无浏览器请求头时更容易被限流断连，这里补充常见浏览器头
_UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
_orig_request = requests.Session.request


def _patched_request(self, method, url, *args, **kwargs):
    headers = kwargs.pop("headers", None) or {}
    merged = {**_UA_HEADERS, **headers}
    kwargs["headers"] = merged
    return _orig_request(self, method, url, *args, **kwargs)


requests.Session.request = _patched_request


def _sina_symbol(code):
    """将ETF代码转换为新浪接口需要的 sh/sz 前缀格式"""
    prefix = "sh" if code.startswith(("5", "6")) else "sz"
    return f"{prefix}{code}"


def fetch_etf_hist_fallback(code, start_date, end_date):
    """
    备用数据源：东方财富接口持续失败时，从新浪财经获取ETF历史行情。
    注意：新浪接口不支持前复权(qfq)，仅作为应急兜底，均线/涨幅/回测结果可能与前复权口径存在偏差。
    """
    df = ak.fund_etf_hist_sina(symbol=_sina_symbol(code))
    if df is None or df.empty:
        raise ValueError("备用数据源(新浪)也返回空数据")
    df = df.rename(columns={"date": "日期", "close": "收盘"})
    df["日期"] = pd.to_datetime(df["日期"])
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)
    df = df[(df["日期"] >= start_ts) & (df["日期"] <= end_ts)]
    if df.empty:
        raise ValueError("备用数据源(新浪)在指定日期范围内无数据")
    return df[["日期", "收盘"]]


def fetch_etf_hist(code, start_date, end_date, adjust="qfq"):
    """带重试的ETF历史数据获取；主数据源(东方财富)多次失败后自动降级到备用数据源(新浪)"""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date,
                adjust=adjust,
            )
            if df is None or df.empty:
                raise ValueError("接口返回空数据")
            return df, False
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * attempt)

    # 主数据源多次重试仍失败，尝试备用数据源兜底
    try:
        df = fetch_etf_hist_fallback(code, start_date, end_date)
        return df, True
    except Exception:
        pass
    raise last_err


print("正在下载ETF数据...")
data = {}
fallback_used = []
for code, name in etfs.items():
    print(f"  下载 {name} ({code})...")
    try:
        df, is_fallback = fetch_etf_hist(code, start_date=start_date, end_date=end_date, adjust="qfq")
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.set_index('日期').sort_index()
        data[code] = df
        if is_fallback:
            fallback_used.append(name)
            print(f"  ✅ {name}（备用数据源-新浪，不含前复权）: {len(df)} 条数据")
        else:
            print(f"  ✅ {name}: {len(df)} 条数据")
    except Exception as e:
        print(f"  ❌ {name} 下载失败（主备数据源均已重试）: {e}")

if not data:
    print("\n❌ 所有ETF数据均下载失败，可能是数据源接口限流或网络异常，请稍后重试。")
    sys.exit(1)

if len(data) < len(etfs):
    missing = [name for code, name in etfs.items() if code not in data]
    print(f"\n⚠️  以下标的数据下载失败，将从本次回测中剔除：{', '.join(missing)}")

if fallback_used:
    print(f"ℹ️  以下标的因主数据源(东方财富)异常，已使用备用数据源(新浪，不含前复权)：{', '.join(fallback_used)}")

# 构建收盘价DataFrame
close_prices = pd.DataFrame()
for code in data:
    close_prices[code] = data[code]['收盘']

# 计算指标
ma60 = close_prices.rolling(60).mean()
ret20 = close_prices.pct_change(20, fill_method=None)

# 回测
backtest_start = '2019-01-18'
all_dates = close_prices.loc[backtest_start:].index

if len(all_dates) == 0:
    print(f"\n❌ 没有可用于回测的数据（回测起点 {backtest_start} 之后无行情），请检查数据下载是否完整。")
    sys.exit(1)

fridays = [d for d in all_dates if d.weekday() == 4]

print(f"\n回测区间: {backtest_start} ~ {all_dates[-1].strftime('%Y-%m-%d')}")
print(f"共 {len(fridays)} 个周五调仓日")

initial_capital = 1000000.0
capital = initial_capital
holdings = None
buy_price = 0.0
trade_log = []

for friday in fridays:
    candidates = []
    for code in data:
        if friday not in close_prices.index:
            continue
        price = close_prices.loc[friday, code]
        ma_val = ma60.loc[friday, code]
        ret_val = ret20.loc[friday, code]
        
        if pd.isna(price) or pd.isna(ma_val) or pd.isna(ret_val):
            continue
        
        # 条件1：站在60日均线上
        if price > ma_val:
            candidates.append((code, ret_val))
    
    # 条件2：近20日涨幅排名第一
    target = None
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        target = candidates[0][0]
    
    # 执行交易
    if target != holdings:
        # 先卖出
        if holdings is not None and buy_price > 0:
            sell_price = close_prices.loc[friday, holdings]
            if not pd.isna(sell_price):
                capital = capital * (sell_price / buy_price)
        
        # 再买入
        if target is not None:
            buy_price = close_prices.loc[friday, target]
            trade_log.append({
                'date': friday,
                'action': '买入' if holdings is None else '换仓',
                'from': etfs.get(holdings, '空仓') if holdings else '空仓',
                'to': etfs[target],
                'capital': capital
            })
        else:
            trade_log.append({
                'date': friday,
                'action': '清仓',
                'from': etfs.get(holdings, '空仓') if holdings else '空仓',
                'to': '空仓',
                'capital': capital
            })
            buy_price = 0.0
        
        holdings = target

# 最终结算（用最后一个交易日价格）
last_date = all_dates[-1]
if holdings is not None and buy_price > 0:
    last_price = close_prices.loc[last_date, holdings]
    if not pd.isna(last_price):
        capital = capital * (last_price / buy_price)

total_return = (capital / initial_capital - 1) * 100
annual_years = (all_dates[-1] - pd.Timestamp(backtest_start)).days / 365.25
annual_return = ((capital / initial_capital) ** (1 / annual_years) - 1) * 100

# 构建每日净值曲线用于计算最大回撤
nav_series = []
cap_nav = initial_capital
hold_nav = None
bp_nav = 0.0
friday_set = set(fridays)

for date in all_dates:
    if date in friday_set:
        # 周五调仓逻辑
        candidates = []
        for code in data:
            if date not in close_prices.index:
                continue
            price = close_prices.loc[date, code]
            ma_val = ma60.loc[date, code]
            ret_val = ret20.loc[date, code]
            if pd.isna(price) or pd.isna(ma_val) or pd.isna(ret_val):
                continue
            if price > ma_val:
                candidates.append((code, ret_val))
        
        tgt = None
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            tgt = candidates[0][0]
        
        if tgt != hold_nav:
            if hold_nav is not None and bp_nav > 0:
                sp = close_prices.loc[date, hold_nav]
                if not pd.isna(sp):
                    cap_nav = cap_nav * (sp / bp_nav)
            if tgt is not None:
                bp_nav = close_prices.loc[date, tgt]
                hold_nav = tgt
            else:
                hold_nav = None
                bp_nav = 0.0
    
    # 记录当日净值
    if hold_nav is not None and bp_nav > 0:
        cur_p = close_prices.loc[date, hold_nav] if date in close_prices.index else np.nan
        if not pd.isna(cur_p):
            nav_series.append(cap_nav * (cur_p / bp_nav))
        else:
            nav_series.append(nav_series[-1] if nav_series else cap_nav)
    else:
        nav_series.append(cap_nav)

nav = pd.Series(nav_series, index=all_dates)
peak = nav.expanding().max()
drawdown = (nav - peak) / peak
max_drawdown = drawdown.min() * 100
max_dd_date = drawdown.idxmin()

# 输出结果
print("\n" + "=" * 60)
print("📊 ETF轮动策略回测结果")
print("=" * 60)
print(f"回测区间: {backtest_start} ~ {all_dates[-1].strftime('%Y-%m-%d')}")
print(f"初始资金: ¥{initial_capital:,.0f}")
print(f"最终资金: ¥{capital:,.0f}")
print(f"总收益率: {total_return:.2f}%")
print(f"年化收益率: {annual_return:.2f}%")
print(f"回测年数: {annual_years:.1f} 年")
print(f"交易次数: {len(trade_log)} 次")
print(f"最大回撤: {max_drawdown:.2f}%")
print(f"最大回撤日期: {max_dd_date.strftime('%Y-%m-%d')}")
print(f"收益回撤比: {abs(total_return / max_drawdown):.2f}")
print("=" * 60)

# 分年度收益
print("\n📅 分年度收益:")
for year in range(2019, datetime.now().year + 1):
    year_start = nav.loc[str(year)].iloc[0] if str(year) in nav.index.strftime('%Y') else None
    year_end = nav.loc[str(year)].iloc[-1] if str(year) in nav.index.strftime('%Y') else None
    if year_start and year_end:
        yr_ret = (year_end / year_start - 1) * 100
        print(f"  {year}年: {yr_ret:+.2f}%")

# 各ETF持仓占比统计
print("\n📊 各ETF持仓时间占比:")
hold_counts = {}
cap_track = initial_capital
hold_track = None
bp_track = 0.0

for i, friday in enumerate(fridays):
    candidates = []
    for code in data:
        if friday not in close_prices.index:
            continue
        price = close_prices.loc[friday, code]
        ma_val = ma60.loc[friday, code]
        ret_val = ret20.loc[friday, code]
        if pd.isna(price) or pd.isna(ma_val) or pd.isna(ret_val):
            continue
        if price > ma_val:
            candidates.append((code, ret_val))
    
    tgt = None
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        tgt = candidates[0][0]
    
    label = etfs.get(tgt, '空仓') if tgt else '空仓'
    hold_counts[label] = hold_counts.get(label, 0) + 1

total_weeks = sum(hold_counts.values())
for name, count in sorted(hold_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {name}: {count} 周 ({count/total_weeks*100:.1f}%)")

# 最近10次换仓
print("\n📋 最近10次换仓记录:")
for t in trade_log[-10:]:
    print(f"  {t['date'].strftime('%Y-%m-%d')} | {t['action']} | {t['from']} → {t['to']} | 资金: ¥{t['capital']:,.0f}")

# 对比各ETF同期买入持有收益
print("\n📈 对比：同期买入持有收益 (2019-01-18 ~ 今):")
for code, name in etfs.items():
    if backtest_start in close_prices.index.strftime('%Y-%m-%d'):
        start_p = close_prices.loc[backtest_start:].iloc[0][code]
        end_p = close_prices.loc[:last_date.strftime('%Y-%m-%d')].iloc[-1][code]
        if not pd.isna(start_p) and not pd.isna(end_p):
            bh_ret = (end_p / start_p - 1) * 100
            print(f"  {name}: {bh_ret:+.2f}%")
