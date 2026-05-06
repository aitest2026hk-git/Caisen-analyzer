"""
蔡森 Trail-Loose 月度轮动器 (TrailLoose)
========================================
基于蔡森量价理论，用 Chandelier Exit 趋势跟踪 + Smart 多维过滤，
每月在港股蓝筹中选出最优标的的月度轮动策略。

策略: Trail Analyzer (Chandelier Exit) + Smart Loose Filters
模式: 月末扫描 → 次月第1交易日买入 → 月末最后交易日卖出

Loose 过滤条件:
  - 风险回报比 (R:R) ≥ 2.0
  - 成交量比 ≥ 0.5
  - 仅 UP 趋势 (价格 > 50日均线)
  - ATR% 在 2-8% 区间
  - 止损距离 ≤ 10%

历史回测 (2018-2026):
  - 33 笔交易, 胜率 63.6%, 累计 +508%, Sharpe 1.63
  - 最大回撤 19.0%, 盈亏比 3.82

用法:
  python3 trail_loose_analyzer.py                    # 扫描最新数据
  python3 trail_loose_analyzer.py --date 2026-04-30  # 回放指定日期
  python3 trail_loose_analyzer.py --backtest         # 跑完整回测
  python3 trail_loose_analyzer.py --compare           # 对比所有配置
"""

import json
import sys
import os
from datetime import datetime
import statistics

# === Loose Config ===
LOOSE_CONFIG = {
    'min_est_rr': 2.0,
    'min_vol_ratio': 0.5,
    'require_up_trend': True,
    'atr_range': (2, 8),
    'max_stop_dist': 10.0,
}

DATA_FILE = 'hk_blue_chip_8y_prices.json'
BACKTEST_FILE = 'backtest_trail_8y.json'


def calc_atr(rows, period=14):
    """Average True Range over last `period` days."""
    trs = []
    for i in range(1, len(rows)):
        h, l, pc = rows[i]['High'], rows[i]['Low'], rows[i-1]['Close']
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0
    return sum(trs[-period:]) / period


def calc_chandelier(rows, atr_mult=3.0, period=22):
    """Chandelier Exit = Highest High (period) - ATR * mult."""
    if len(rows) < period:
        return None, None, None
    highest = max(r['High'] for r in rows[-period:])
    atr = calc_atr(rows, 14)
    stop = highest - atr * atr_mult
    return stop, atr, highest


def get_trend(rows, period=50):
    """UP if price > 50-day MA."""
    if len(rows) < period:
        return 'N/A'
    ma = sum(r['Close'] for r in rows[-period:]) / period
    return 'UP' if rows[-1]['Close'] > ma else 'DOWN'


def get_vol_ratio(rows):
    """Current volume / 20-day average volume."""
    if len(rows) < 21:
        return 0
    avg = sum(r['Volume'] for r in rows[-21:-1]) / 20
    return rows[-1]['Volume'] / avg if avg > 0 else 0


def passes_loose(price, stop, atr, highest, vol_ratio, trend):
    """Check if stock passes all Loose filters."""
    cfg = LOOSE_CONFIG
    atr_pct = atr / price * 100
    stop_dist = price - stop
    stop_dist_pct = stop_dist / price * 100
    reward = highest - price
    est_rr = reward / stop_dist if stop_dist > 0 else 0
    
    metrics = {
        'atr_pct': atr_pct,
        'stop_dist_pct': stop_dist_pct,
        'est_rr': est_rr,
        'vol_ratio': vol_ratio,
    }
    
    if trend != 'UP' and cfg['require_up_trend']:
        return False, metrics
    
    if est_rr < cfg['min_est_rr']:
        return False, metrics
    if vol_ratio < cfg['min_vol_ratio']:
        return False, metrics
    lo, hi = cfg['atr_range']
    if not (lo <= atr_pct < hi):
        return False, metrics
    if stop_dist_pct > cfg['max_stop_dist']:
        return False, metrics
    
    return True, metrics


def enrich_trade(t):
    """Add derived fields for backtest filtering."""
    t2 = dict(t)
    t2['atr_pct'] = t2['atr'] / t2['buy_price'] * 100
    stop_dist = t2['buy_price'] - t2['chandelier_stop']
    reward_dist = t2['peak'] - t2['buy_price']
    t2['est_rr'] = reward_dist / stop_dist if stop_dist > 0 else 0
    t2['stop_dist_pct'] = stop_dist / t2['buy_price'] * 100
    return t2


def scan_latest(cutoff_date=None):
    """Scan all stocks and return Loose matches."""
    prices_data = json.load(open(DATA_FILE))
    candidates = []
    
    for ticker, stock in prices_data['stocks'].items():
        rows_all = stock['data']
        rows = [r for r in rows_all if r['Date'] <= cutoff_date] if cutoff_date else rows_all
        if len(rows) < 60:
            continue
        
        last = rows[-1]
        price = last['Close']
        
        stop, atr, highest = calc_chandelier(rows)
        if stop is None or price <= stop:
            continue
        
        trend = get_trend(rows)
        vol_ratio = get_vol_ratio(rows)
        
        passed, metrics = passes_loose(price, stop, atr, highest, vol_ratio, trend)
        
        candidates.append({
            'ticker': ticker,
            'name': stock['name'],
            'date': last['Date'],
            'price': price,
            'stop': round(stop, 2),
            'highest_22': highest,
            'upside_pct': (highest - price) / price * 100,
            'trend': trend,
            'passed': passed,
            **metrics,
        })
    
    passed_list = [c for c in candidates if c['passed']]
    passed_list.sort(key=lambda x: x['est_rr'], reverse=True)
    return passed_list, candidates


def print_scan_results(passed, all_candidates, cutoff_date=None):
    """Pretty-print scan results."""
    label = f" (as of {cutoff_date})" if cutoff_date else ""
    print("=" * 100)
    print(f"🔍 蔡森 Trail-Loose 月度轮动器 (TrailLoose){label}")
    print(f"   Data source: {DATA_FILE}")
    print(f"   Strategy: Loose (R:R≥2, Vol≥0.5, ATR 2-8%, Stop≤10%, UP trend)")
    print("=" * 100)
    
    if passed:
        print(f"\n✅ RECOMMENDED STOCKS ({len(passed)}):")
        print(f"\n   {'#':<4} {'Ticker':<10} {'Name':<22} {'Price':>8} {'Stop':>8} {'22D峰':>8} {'距峰%':>7} {'ATR%':>6} {'VolR':>6} {'R:R':>6} {'StopD%':>7}")
        print(f"   {'-'*95}")
        for i, c in enumerate(passed, 1):
            print(f"   {i:<4} {c['ticker']:<10} {c['name']:<22} {c['price']:>8.2f} {c['stop']:>8.2f} {c['highest_22']:>8.2f} {c['upside_pct']:>+6.1f}% {c['atr_pct']:>5.1f}% {c['vol_ratio']:>5.2f} {c['est_rr']:>5.1f} {c['stop_dist_pct']:>6.1f}%")
        
        print(f"\n   📌 Action: Buy on 1st trading day of next month, sell on last trading day")
    else:
        print(f"\n❌ NO STOCKS pass Loose filters this month.")
        print(f"   This is normal — the strategy is selective (avg ~3 trades/year)")
    
    # Near-miss
    near_miss = []
    for c in all_candidates:
        if c['passed']:
            continue
        fails = []
        if c['est_rr'] < 2.0: fails.append(f"R:R={c['est_rr']:.1f}")
        if c['vol_ratio'] < 0.5: fails.append(f"Vol={c['vol_ratio']:.2f}")
        lo, hi = LOOSE_CONFIG['atr_range']
        if not (lo <= c['atr_pct'] < hi): fails.append(f"ATR={c['atr_pct']:.1f}%")
        if c['stop_dist_pct'] > 10.0: fails.append(f"Stop={c['stop_dist_pct']:.1f}%")
        if len(fails) == 1:
            near_miss.append((c, fails[0]))
    
    if near_miss:
        near_miss.sort(key=lambda x: x[0]['est_rr'], reverse=True)
        print(f"\n📋 NEAR-MISS (missing 1 filter):")
        print(f"\n   {'Ticker':<10} {'Name':<22} {'Price':>8} {'R:R':>6} {'VolR':>6} {'ATR%':>6} {'Reason':>18}")
        print(f"   {'-'*75}")
        for c, reason in near_miss[:8]:
            print(f"   {c['ticker']:<10} {c['name']:<22} {c['price']:>8.2f} {c['est_rr']:>5.1f} {c['vol_ratio']:>5.2f} {c['atr_pct']:>5.1f}% {reason:>18}")
    
    up_count = sum(1 for c in all_candidates if c['trend'] == 'UP')
    print(f"\n   Scanned: {len(all_candidates)} stocks | UP trend: {up_count}")


def run_backtest():
    """Run full backtest using Loose config."""
    data = json.load(open(BACKTEST_FILE))
    
    all_trades = []
    for month in data['monthly']:
        for t in month['trades']:
            all_trades.append(enrich_trade(t))
    
    cfg = LOOSE_CONFIG
    filtered = []
    for t in all_trades:
        if t['est_rr'] < cfg['min_est_rr']: continue
        if t['vol_ratio'] < cfg['min_vol_ratio']: continue
        if cfg['require_up_trend'] and t['trend'] != 'UP': continue
        lo, hi = cfg['atr_range']
        if not (lo <= t['atr_pct'] < hi): continue
        if t['stop_dist_pct'] > cfg['max_stop_dist']: continue
        filtered.append(t)
    
    n = len(filtered)
    wins = [t for t in filtered if t['pnl'] > 0]
    losses = [t for t in filtered if t['pnl'] <= 0]
    
    equity = 100
    peak = 100
    max_dd = 0
    for t in filtered:
        equity *= (1 + t['pnl'] / 100)
        if equity > peak: peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd: max_dd = dd
    
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else 99
    
    monthly_rets = [t['pnl'] for t in filtered]
    avg_ret = statistics.mean(monthly_rets)
    std_ret = statistics.stdev(monthly_rets) if len(monthly_rets) > 1 else 1
    sharpe = (avg_ret / std_ret) * (12 ** 0.5) if std_ret > 0 else 0
    
    years = n / 12
    cagr = ((equity / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    print("=" * 70)
    print("TRAIL + SMART LOOSE — BACKTEST (2018-2026)")
    print("=" * 70)
    print(f"  Total trades:    {n}")
    print(f"  Win rate:        {len(wins)/n*100:.1f}%")
    print(f"  Avg win:         +{sum(t['pnl'] for t in wins)/len(wins):.2f}%")
    print(f"  Avg loss:        {sum(t['pnl'] for t in losses)/len(losses):.2f}%")
    print(f"  Total return:    {equity - 100:+.1f}%")
    print(f"  CAGR:            {cagr:.1f}%")
    print(f"  Max drawdown:    {max_dd:.1f}%")
    print(f"  Profit factor:   {pf:.2f}")
    print(f"  Sharpe ratio:    {sharpe:.2f}")
    
    # Yearly
    yearly = {}
    for t in filtered:
        yr = t['month'][:4]
        if yr not in yearly: yearly[yr] = []
        yearly[yr].append(t)
    
    print(f"\n  {'Year':<6} {'Trades':>6} {'WR%':>6} {'Return':>10} {'MaxDD':>7}")
    print(f"  {'-'*38}")
    for yr in sorted(yearly.keys()):
        yt = yearly[yr]
        eq = 100; pk = 100; mdd = 0
        for t in yt:
            eq *= (1 + t['pnl'] / 100)
            if eq > pk: pk = eq
            dd = (pk - eq) / pk * 100
            if dd > mdd: mdd = dd
        wr = sum(1 for t in yt if t['pnl'] > 0) / len(yt) * 100
        print(f"  {yr:<6} {len(yt):>6} {wr:>5.0f}% {eq-100:>+9.1f}% {mdd:>6.1f}%")


def main():
    args = sys.argv[1:]
    
    if '--backtest' in args:
        run_backtest()
        return
    
    if '--compare' in args:
        # Import and run comparison
        os.system(f'python3 {os.path.dirname(__file__)}/trail_smart_combo.py --compare')
        return
    
    cutoff = None
    if '--date' in args:
        idx = args.index('--date')
        cutoff = args[idx + 1]
    
    passed, all_candidates = scan_latest(cutoff)
    print_scan_results(passed, all_candidates, cutoff)


if __name__ == '__main__':
    main()
