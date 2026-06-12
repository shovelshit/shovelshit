#!/usr/bin/env python3
"""
ETF轮动策略 - 每周五信号生成器
运行后直接告诉你：本周该买哪只ETF

用法：每周五收盘后运行 python3 rotation_signal.py
"""

import akshare as ak
import pandas as pd
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
# ==============================


def get_signal():
    print("=" * 50)
    print("📊 ETF轮动策略 - 信号生成器")
    print(f"📅 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    print()

    results = []

    for code, name in etfs.items():
        try:
            df = ak.fund_etf_hist_em(
                symbol=code, period="daily",
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

            status = "✅ 站上均线" if above_ma else "❌ 跌破均线"
            ret_str = f"{ret_20d:+.2f}%" if ret_20d is not None else "N/A"
            print(f"  {name}({code}): 收盘 {latest_price:.3f} | MA60 {ma60:.3f} | {status} | 近20日 {ret_str}")

        except Exception as e:
            print(f"  {name}({code}): ❌ 获取数据失败 - {e}")

    print()

    # 筛选：条件1 站在60日均线上
    candidates = [r for r in results if r['above_ma'] and r['ret_20d'] is not None]

    if not candidates:
        print("⚠️  结论：4只ETF全部跌破60日均线，本周应【空仓】")
        return

    # 条件2：近20日涨幅排名第一
    candidates.sort(key=lambda x: x['ret_20d'], reverse=True)
    winner = candidates[0]

    print("-" * 50)
    print(f"🏆 本周信号：全仓买入 【{winner['name']}】({winner['code']})")
    print(f"   近20日涨幅: {winner['ret_20d']:+.2f}%（满足条件的标的中排名第一）")
    print("-" * 50)

    if len(candidates) > 1:
        print("\n📋 备选排名：")
        for i, c in enumerate(candidates[1:], 2):
            print(f"   第{i}名: {c['name']} ({c['ret_20d']:+.2f}%)")


if __name__ == '__main__':
    get_signal()
