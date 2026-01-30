"""
Shadow Trade Workflow Example
==============================
Demonstrates how shadow trades are logged and analyzed.

This is a REFERENCE implementation showing the complete workflow.
"""

from datetime import datetime
from core.shadow_trades import ShadowTradeManager, FilterCheck
from logging.logger import Logger
from logging.schemas import TradeLog

# ============================================================================
# SCENARIO 1: Setup passes all filters → REAL TRADE
# ============================================================================

print("="*70)
print("SCENARIO 1: All filters passed → REAL TRADE")
print("="*70)

filter_results_scenario1 = [
    # Core filters
    FilterCheck('TIME_WINDOW', passed=True),
    FilterCheck('ONS_VALID', passed=True),
    FilterCheck('DEVIATION_DETECTED', passed=True),
    FilterCheck('RECLAIM_DETECTED', passed=True),
    
    # Gating filters (all passed)
    FilterCheck('SMT_BINARY', passed=True, value=True, threshold=True),
    FilterCheck('ISI_DISPLACEMENT', passed=True, value=1.1, threshold=1.2),
    FilterCheck('RECLAIM_TIMEOUT', passed=True, value=35, threshold=45),
    FilterCheck('RECLAIM_BODY_RATIO', passed=True, value=0.72, threshold=0.60),
]

manager = ShadowTradeManager()
result1 = manager.evaluate_for_shadow_trade(filter_results_scenario1)

print(f"Is shadow trade: {result1['is_shadow_trade']}")
print(f"Reason: {result1['reason']}")
print("\n→ This becomes a REAL trade (sent to MT5)")

# ============================================================================
# SCENARIO 2: One filter failed → SHADOW TRADE
# ============================================================================

print("\n" + "="*70)
print("SCENARIO 2: SMT failed, all else passed → SHADOW TRADE")
print("="*70)

filter_results_scenario2 = [
    # Core filters (all passed)
    FilterCheck('TIME_WINDOW', passed=True),
    FilterCheck('ONS_VALID', passed=True),
    FilterCheck('DEVIATION_DETECTED', passed=True),
    FilterCheck('RECLAIM_DETECTED', passed=True),
    
    # Gating filters
    FilterCheck('SMT_BINARY', passed=False, value=False, threshold=True),  # ← FAILED
    FilterCheck('ISI_DISPLACEMENT', passed=True, value=1.1, threshold=1.2),
    FilterCheck('RECLAIM_TIMEOUT', passed=True, value=35, threshold=45),
    FilterCheck('RECLAIM_BODY_RATIO', passed=True, value=0.72, threshold=0.60),
]

result2 = manager.evaluate_for_shadow_trade(filter_results_scenario2)

print(f"Is shadow trade: {result2['is_shadow_trade']}")
print(f"Blocked by: {result2.get('blocked_by')}")
print(f"Reason: {result2['reason']}")
print(f"Filters passed: {result2.get('filters_passed')}")
print("\n→ This becomes a SHADOW trade (logged but not executed)")

# Log this as a shadow trade
logger = Logger()

shadow_trade = TradeLog(
    trade_id=999,  # Shadow trades get different ID series
    timestamp_entry=datetime.now(),
    timestamp_exit=datetime.now(),
    instrument="NQ",
    trade_type="SHADOW",  # ← CRITICAL
    direction="LONG",
    midnight_open=17550.0,
    deviation_extreme=17500.0,
    entry_price=17552.0,  # Virtual entry
    smt_binary=False,  # What it actually was
    smt_degree=0.15,  # Below threshold
    nq_sweep_depth_norm=0.8,
    es_sweep_depth_norm=0.75,  # ES swept too (that's why SMT failed)
    isi_value=1.1,
    minutes_to_reclaim=35,
    reclaim_body_ratio=0.72,
    stop_loss=17495.0,
    tp1_price=17607.0,
    initial_risk_r=1.0,
    exit_price=17607.0,  # Virtual exit (same logic as real trades)
    exit_reason="TP1",
    pnl_points=55.0,
    pnl_r=1.0,  # Virtual R-multiple
    pnl_dollars=0.0,  # No actual P&L
    win=True,  # Virtual win
    overnight_range=45.0,
    adr=80.0,
    ons_ratio=0.56,
    regime_high_vol=False,
    regime_trend_day=False,
    regime_gap_day=True,
    regime_news_day=False,
    
    # Shadow trade specific fields
    blocked_by_filter="SMT_BINARY",
    filters_passed=result2.get('filters_passed'),
    filters_failed=result2.get('filters_failed'),
    
    # Execution reality (None for shadow trades)
    broker_time=None,
    server_time=None,
    spread_at_entry=None,
    slippage_ticks=None
)

logger.log_trade(shadow_trade)

# ============================================================================
# SCENARIO 3: Multiple filters failed → NOT a shadow trade
# ============================================================================

print("\n" + "="*70)
print("SCENARIO 3: SMT AND ISI failed → NOT LOGGED")
print("="*70)

filter_results_scenario3 = [
    # Core filters (all passed)
    FilterCheck('TIME_WINDOW', passed=True),
    FilterCheck('ONS_VALID', passed=True),
    FilterCheck('DEVIATION_DETECTED', passed=True),
    FilterCheck('RECLAIM_DETECTED', passed=True),
    
    # Gating filters
    FilterCheck('SMT_BINARY', passed=False, value=False, threshold=True),  # ← FAILED
    FilterCheck('ISI_DISPLACEMENT', passed=False, value=2.5, threshold=2.0),  # ← FAILED
    FilterCheck('RECLAIM_TIMEOUT', passed=True, value=35, threshold=45),
    FilterCheck('RECLAIM_BODY_RATIO', passed=True, value=0.72, threshold=0.60),
]

result3 = manager.evaluate_for_shadow_trade(filter_results_scenario3)

print(f"Is shadow trade: {result3['is_shadow_trade']}")
print(f"Reason: {result3['reason']}")
print(f"Blocked by: {result3.get('blocked_by')}")
print("\n→ NOT a shadow trade (multiple failures = not a near miss)")

# ============================================================================
# SCENARIO 4: Core filter failed → NOT a shadow trade
# ============================================================================

print("\n" + "="*70)
print("SCENARIO 4: ONS invalid → NOT LOGGED")
print("="*70)

filter_results_scenario4 = [
    # Core filters
    FilterCheck('TIME_WINDOW', passed=True),
    FilterCheck('ONS_VALID', passed=False),  # ← FAILED
    FilterCheck('DEVIATION_DETECTED', passed=True),
    FilterCheck('RECLAIM_DETECTED', passed=True),
    
    # Gating filters don't matter if core failed
    FilterCheck('SMT_BINARY', passed=True),
    FilterCheck('ISI_DISPLACEMENT', passed=True),
    FilterCheck('RECLAIM_TIMEOUT', passed=True),
    FilterCheck('RECLAIM_BODY_RATIO', passed=True),
]

result4 = manager.evaluate_for_shadow_trade(filter_results_scenario4)

print(f"Is shadow trade: {result4['is_shadow_trade']}")
print(f"Reason: {result4['reason']}")
print("\n→ NOT a shadow trade (structural conditions not met)")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "="*70)
print("SHADOW TRADE SUMMARY")
print("="*70)
print(f"Total shadow trades logged: {manager.shadow_trade_count}")
print("\nShadow trades are logged when:")
print("  ✅ All core structural filters pass")
print("  ✅ Exactly ONE gating filter fails")
print("  ✅ Setup was a 'near miss'")
print("\nShadow trades are NOT logged when:")
print("  ❌ Core structural conditions not met")
print("  ❌ Multiple gating filters fail")
print("  ❌ No filters failed (should be real trade)")
print("\n⚠️  REMEMBER: Do not review shadow performance until 50 REAL trades!")
print("="*70)
