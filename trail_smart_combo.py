"""
Trail Analyzer + Smart Filters (Combined Strategy)
===================================================
Combines Trail Analyzer's monthly rotation selection with
Smart Top 2's confidence/R:R/volume/trend filtering.

Best of both worlds: Trail's opportunity set + Smart's risk control.
"""

import json
import sys
from datetime import datetime

def load_trail_data(path='backtest_trail_8y.json'):
    with open(path) as f:
        return json.load(f)

def load_trail_stoploss_data(path='backtest_trail_8y_stoploss.json'):
    with open(path) as f:
        return json.load(f)

def enrich_trade(trade):
    """Add derived fields for filtering."""
    t = dict(trade)
    t['atr_pct'] = t['atr'] / t['buy_price'] * 100
    stop_dist = t['buy_price'] - t['chandelier_stop']
    reward_dist = t['peak'] - t['buy_price']
    t['est_rr'] = reward_dist / stop_dist if stop_dist > 0 else 0
    t['stop_dist_pct'] = stop_dist / t['buy_price'] * 100
    return t

def apply_smart_filters(trades, config):
    """
    Apply Smart Top 2 style filters to Trail Analyzer trades.
    
    Config keys:
        min_est_rr:        Minimum estimated risk/reward ratio (default: 3.0)
        min_vol_ratio:     Minimum volume ratio (default: 0.3)
        require_up_trend:  Only take UP-trend stocks (default: True)
        atr_range:         (min, max) ATR% range (default: (3, 6))
        max_stop_dist:     Max stop distance % (default: 8.0)
    """
    min_rr = config.get('min_est_rr', 3.0)
    min_vol = config.get('min_vol_ratio', 0.3)
    require_up = config.get('require_up_trend', True)
    atr_lo, atr_hi = config.get('atr_range', (3, 6))
    max_stop = config.get('max_stop_dist', 8.0)
    
    filtered = []
    for t in trades:
        if t['est_rr'] < min_rr:
            continue
        if t['vol_ratio'] < min_vol:
            continue
        if require_up and t['trend'] != 'UP':
            continue
        if not (atr_lo <= t['atr_pct'] < atr_hi):
            continue
        if t['stop_dist_pct'] > max_stop:
            continue
        filtered.append(t)
    
    return filtered

def calc_stats(trades, label=""):
    """Calculate performance statistics."""
    n = len(trades)
    if n == 0:
        return None
    
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    
    wr = len(wins) / n * 100
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    
    # Compound return
    cumulative = 100
    peak = 100
    max_dd = 0
    monthly_returns = []
    for t in trades:
        cumulative *= (1 + t['pnl'] / 100)
        monthly_returns.append(t['pnl'])
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    total_return = cumulative - 100
    
    # Profit factor
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    
    # Sharpe (annualized, assuming monthly)
    import statistics
    if len(monthly_returns) > 1:
        avg_ret = statistics.mean(monthly_returns)
        std_ret = statistics.stdev(monthly_returns)
        sharpe = (avg_ret / std_ret) * (12 ** 0.5) if std_ret > 0 else 0
    else:
        sharpe = 0
    
    # CAGR (approximate)
    years = len(trades) / 12
    cagr = ((cumulative / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    return {
        'label': label,
        'trades': n,
        'win_rate': wr,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_return': total_return,
        'max_drawdown': max_dd,
        'profit_factor': pf,
        'sharpe': sharpe,
        'cagr': cagr,
        'winning_trades': len(wins),
        'losing_trades': len(losses),
    }

def yearly_breakdown(trades):
    """Group trades by year and calculate per-year stats."""
    years = {}
    for t in trades:
        yr = t['month'][:4]
        if yr not in years:
            years[yr] = []
        years[yr].append(t)
    
    results = {}
    for yr in sorted(years.keys()):
        yt = years[yr]
        s = calc_stats(yt)
        if s:
            results[yr] = s
    return results

def run_backtest(config, data_path='backtest_trail_8y.json', verbose=True):
    """Run the combined strategy backtest."""
    data = load_trail_data(data_path)
    
    # Enrich all trades
    all_trades = []
    for month in data['monthly']:
        for t in month['trades']:
            all_trades.append(enrich_trade(t))
    
    # Apply smart filters
    filtered = apply_smart_filters(all_trades, config)
    
    # Calculate stats
    stats = calc_stats(filtered, "Trail + Smart Filters")
    
    if verbose:
        print("=" * 70)
        print("TRAIL + SMART FILTERS — COMBINED STRATEGY")
        print("=" * 70)
        print(f"\nConfig:")
        for k, v in config.items():
            print(f"  {k}: {v}")
        print(f"\nResults:")
        if stats:
            print(f"  Total trades:    {stats['trades']}")
            print(f"  Win rate:        {stats['win_rate']:.1f}%")
            print(f"  Avg win:         {stats['avg_win']:+.2f}%")
            print(f"  Avg loss:        {stats['avg_loss']:+.2f}%")
            print(f"  Total return:    {stats['total_return']:+.1f}%")
            print(f"  CAGR:            {stats['cagr']:.1f}%")
            print(f"  Max drawdown:    {stats['max_drawdown']:.1f}%")
            print(f"  Profit factor:   {stats['profit_factor']:.2f}")
            print(f"  Sharpe ratio:    {stats['sharpe']:.2f}")
            
            print(f"\nYearly Breakdown:")
            print(f"  {'Year':<6} {'Trades':>6} {'WR%':>6} {'Return':>10} {'MaxDD':>7}")
            print(f"  {'-'*38}")
            yb = yearly_breakdown(filtered)
            for yr, s in yb.items():
                print(f"  {yr:<6} {s['trades']:>6} {s['win_rate']:>5.1f}% {s['total_return']:>+9.1f}% {s['max_drawdown']:>6.1f}%")
        else:
            print("  No trades matched filters!")
    
    return stats, filtered

def compare_strategies(data_path='backtest_trail_8y.json'):
    """Compare multiple configurations."""
    data = load_trail_data(data_path)
    
    all_trades = []
    for month in data['monthly']:
        for t in month['trades']:
            all_trades.append(enrich_trade(t))
    
    configs = {
        'Baseline (no filter)': {
            'min_est_rr': 0, 'min_vol_ratio': 0,
            'require_up_trend': False, 'atr_range': (0, 100), 'max_stop_dist': 100
        },
        'Conservative (R:R≥3, UP, ATR 3-6%)': {
            'min_est_rr': 3.0, 'min_vol_ratio': 0.3,
            'require_up_trend': True, 'atr_range': (3, 6), 'max_stop_dist': 8.0
        },
        'Aggressive (R:R≥5, UP, ATR 3-6%)': {
            'min_est_rr': 5.0, 'min_vol_ratio': 0.5,
            'require_up_trend': True, 'atr_range': (3, 6), 'max_stop_dist': 8.0
        },
        'Balanced (R:R≥3, ATR 2-7%)': {
            'min_est_rr': 3.0, 'min_vol_ratio': 0.3,
            'require_up_trend': True, 'atr_range': (2, 7), 'max_stop_dist': 10.0
        },
        'Loose (R:R≥2, vol≥0.5)': {
            'min_est_rr': 2.0, 'min_vol_ratio': 0.5,
            'require_up_trend': True, 'atr_range': (2, 8), 'max_stop_dist': 10.0
        },
    }
    
    print("=" * 110)
    print("STRATEGY COMPARISON")
    print("=" * 110)
    print(f"\n{'Config':<42} {'Trades':>6} {'WR%':>6} {'AvgW':>7} {'AvgL':>7} {'Return':>9} {'DD%':>6} {'PF':>5} {'Sharpe':>7}")
    print("-" * 110)
    
    for name, config in configs.items():
        filtered = apply_smart_filters(all_trades, config)
        stats = calc_stats(filtered, name)
        if stats:
            print(f"{name:<42} {stats['trades']:>6} {stats['win_rate']:>5.1f}% {stats['avg_win']:>+6.1f}% {stats['avg_loss']:>+6.1f}% {stats['total_return']:>+8.1f}% {stats['max_drawdown']:>5.1f}% {stats['profit_factor']:>5.2f} {stats['sharpe']:>6.2f}")
    
    # Also show actual Smart Top 2 for reference
    print("-" * 110)
    print(f"{'Smart Top 2 (actual, ref)':<42} {'38':>6} {'42.1':>5}% {'+11.3':>6}% {'-4.7':>6}% {'+80.5':>8}% {'27.8':>5}% {'1.75':>5} {'0.43':>6}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--compare':
        compare_strategies()
        return
    
    # Default recommended config
    config = {
        'min_est_rr': 3.0,
        'min_vol_ratio': 0.3,
        'require_up_trend': True,
        'atr_range': (3, 6),
        'max_stop_dist': 8.0,
    }
    
    run_backtest(config)

if __name__ == '__main__':
    main()
