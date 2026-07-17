#!/usr/bin/env python3
"""
ETF轮动策略 - 每周五信号生成器
运行后直接告诉你：本周该买哪只ETF

用法：每周五收盘后运行 python3 rotation_signal.py
"""

import os
import time

import akshare as ak
import pandas as pd
import requests
from datetime import datetime

# ============ 配置 ============
etfs = {
    '518880': '黄金ETF',
    '159915': '创业板ETF',
    '513100': '纳指ETF',
    '512890': '红利低波ETF',
}

MA_PERIOD = 60    # 均线周期
RET_PERIOD = 20   # 涨幅计算周期（交易日）

MAX_RETRIES = 4        # 数据源偶发限流/断连时的最大重试次数
RETRY_BACKOFF_SEC = 3  # 每次重试的等待时间（秒），逐次递增

# Bark 推送配置：BARK_KEY 从环境变量读取（GitHub Actions 中通过 Secret 注入）
# BARK_SERVER 可选，默认使用官方服务器，如自建 Bark 服务器可通过环境变量覆盖
BARK_KEY = os.environ.get('BARK_KEY', '').strip()
BARK_SERVER = os.environ.get('BARK_SERVER', 'https://api.day.app').rstrip('/')
# ==============================

# 东方财富接口在无浏览器请求头时更容易被限流断连，这里补充常见浏览器头
_UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
requests.utils.default_headers()
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
    注意：新浪接口不支持前复权(qfq)，仅作为应急兜底，均线/涨幅结果可能与前复权口径略有差异。
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


def send_bark_notification(title, body, group="ETF轮动"):
    """
    通过 Bark 推送通知到 iPhone。
    需要设置环境变量 BARK_KEY（可选 BARK_SERVER 自建服务器地址）。
    未配置 BARK_KEY 时静默跳过，不影响脚本主流程。
    """
    if not BARK_KEY:
        print("ℹ️  未配置 BARK_KEY，跳过 Bark 推送（如需推送请设置环境变量 BARK_KEY）")
        return

    url = f"{BARK_SERVER}/push"
    payload = {
        "device_key": BARK_KEY,
        "title": title,
        "body": body,
        "group": group,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 200:
            print("✅ Bark 推送成功")
        else:
            print(f"⚠️  Bark 推送返回异常: {result}")
    except Exception as e:
        print(f"⚠️  Bark 推送失败: {e}")


def get_signal():
    print("=" * 50)
    print("📊 ETF轮动策略 - 信号生成器")
    print(f"📅 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    print()

    results = []
    failed = []
    fallback_used = []

    for code, name in etfs.items():
        try:
            df, is_fallback = fetch_etf_hist(
                code,
                start_date=(datetime.now() - pd.Timedelta(days=200)).strftime('%Y%m%d'),
                end_date=datetime.now().strftime('%Y%m%d'),
                adjust="qfq"
            )
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.set_index('日期').sort_index()

            close = df['收盘']
            latest_price = close.iloc[-1]
            ma60 = close.rolling(MA_PERIOD).mean().iloc[-1]
            price_20d_ago = close.iloc[-RET_PERIOD - 1] if len(close) > RET_PERIOD else None

            above_ma = latest_price > ma60
            ret_20d = (latest_price / price_20d_ago - 1) * 100 if price_20d_ago else None

            results.append({
                'code': code,
                'name': name,
                'price': latest_price,
                'ma60': ma60,
                'above_ma': above_ma,
                'ret_20d': ret_20d,
            })

            if is_fallback:
                fallback_used.append(name)

            status = "✅ 站上均线" if above_ma else "❌ 跌破均线"
            ret_str = f"{ret_20d:+.2f}%" if ret_20d is not None else "N/A"
            src_tag = "（备用数据源）" if is_fallback else ""
            print(f"  {name}({code}){src_tag}: 收盘 {latest_price:.3f} | MA60 {ma60:.3f} | {status} | 近20日 {ret_str}")

        except Exception as e:
            failed.append(name)
            print(f"  {name}({code}): ❌ 获取数据失败（主备数据源均已重试）- {e}")

    print()

    if fallback_used:
        print(f"ℹ️  以下标的因主数据源(东方财富)异常，已使用备用数据源(新浪，不含前复权)：{', '.join(fallback_used)}")

    # 数据源异常：全部或部分标的获取失败时，不能当作"跌破均线"处理，避免误报信号
    if failed:
        print(f"⚠️  以下标的数据获取失败，本次结果不可信，请稍后重试：{', '.join(failed)}")
        if not results:
            send_bark_notification(
                "⚠️ ETF轮动信号获取失败",
                f"全部标的数据获取失败，请检查数据源：{', '.join(failed)}",
            )
            return

    # 筛选：条件1 站在60日均线上
    candidates = [r for r in results if r['above_ma'] and r['ret_20d'] is not None]

    if not candidates:
        print("⚠️  结论：已成功获取数据的ETF全部跌破60日均线，本周应【空仓】")
        body = "已成功获取数据的ETF全部跌破60日均线，本周应【空仓】"
        if failed:
            body += f"\n（数据获取失败标的：{', '.join(failed)}）"
        send_bark_notification("📉 ETF轮动信号：空仓", body)
        return

    # 条件2：近20日涨幅排名第一
    candidates.sort(key=lambda x: x['ret_20d'], reverse=True)
    winner = candidates[0]

    print("-" * 50)
    print(f"🏆 本周信号：全仓买入 【{winner['name']}】({winner['code']})")
    print(f"   近20日涨幅: {winner['ret_20d']:+.2f}%（满足条件的标的中排名第一）")
    print("-" * 50)

    body_lines = [f"全仓买入【{winner['name']}】({winner['code']})"]
    body_lines.append(f"近20日涨幅: {winner['ret_20d']:+.2f}%")

    if len(candidates) > 1:
        print("\n📋 备选排名：")
        body_lines.append("备选排名：")
        for i, c in enumerate(candidates[1:], 2):
            print(f"   第{i}名: {c['name']} ({c['ret_20d']:+.2f}%)")
            body_lines.append(f"第{i}名: {c['name']} ({c['ret_20d']:+.2f}%)")

    if failed:
        body_lines.append(f"（数据获取失败标的：{', '.join(failed)}）")

    send_bark_notification(f"🏆 ETF轮动信号：买入 {winner['name']}", "\n".join(body_lines))


if __name__ == '__main__':
    get_signal()
