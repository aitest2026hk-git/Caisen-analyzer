# 蔡森 Trail-Loose 月度轮动器 (TrailLoose)

> 基于蔡森量价理论，用 Chandelier Exit 趋势跟踪 + Smart 多维过滤，每月在港股蓝筹中选出最优标的的月度轮动策略。

## 策略逻辑

```
月末最后交易日收盘 → 跑 TrailLoose → 次月第1交易日买入 → 持有整月 → 月末卖出 → 重复
```

**Loose 过滤条件：**
| 过滤器 | 阈值 | 作用 |
|---|---|---|
| 风险回报比 (R:R) | ≥ 2.0 | 只做向上空间大的 |
| 成交量比 | ≥ 0.5 | 确认活跃度 |
| ATR% | 2-8% | 波动适中，不做死水也不做过山车 |
| 止损距离 | ≤ 10% | 风险可控 |
| 趋势 | UP (价格 > 50日均线) | 只做上升趋势 |

## 回测表现 (2018-2026)

| 指标 | 数值 |
|---|---|
| 交易次数 | 33 笔 |
| 胜率 | 63.6% |
| 累计收益 | +508% |
| CAGR | 92.8% |
| 最大回撤 | 19.0% |
| 盈亏比 (PF) | 3.82 |
| Sharpe | 1.63 |

## 使用方法

```bash
# 月末收盘后跑一下，看下个月买什么
python3 trail_loose_analyzer.py

# 回放历史某天的信号
python3 trail_loose_analyzer.py --date 2026-04-30

# 跑完整回测
python3 trail_loose_analyzer.py --backtest

# 对比所有配置 (Conservative / Aggressive / Balanced / Loose)
python3 trail_loose_analyzer.py --compare
```

## 文件说明

| 文件 | 用途 |
|---|---|
| `trail_loose_analyzer.py` | ⭐ **月度选股工具** — 跑 Loose 策略扫描 |
| `trail_smart_combo.py` | 多配置对比工具（5 种策略 + Smart Top 2 基准） |
| `backtest_conservative_vs_loose.html` | 8 年回测可视化报告（Conservative vs Loose） |
| `hk_blue_chip_8y_prices.json` | 港股蓝筹 75 只 8 年日线数据 |

## 当前信号 (2026-05-04 数据)

| # | 股票 | 名称 | 价格 | 止损 | R:R |
|---|---|---|---|---|---|
| 1 | 1211.HK | BYD 比亚迪 | 103.00 | 101.03 | 5.3 |
| 2 | 9618.HK | JD.com 京东 | 116.80 | 115.06 | 4.3 |

## 数据更新

数据文件 `hk_blue_chip_8y_prices.json` 需要定期更新。数据来源：港股蓝筹 75 只日线（开高低收量）。
