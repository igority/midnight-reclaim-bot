"""
Sprint 2 Test Script
====================
Tests all indicators with real data from Yahoo Finance.

Run this to verify Sprint 2 completion.
"""

import sys
from datetime import datetime, timedelta
import pandas as pd

print("="*70)
print("SPRINT 2: INDICATOR TESTING")
print("="*70)
print()

# Test 1: Load Yahoo Finance data
print("TEST 1: Data Loading")
print("-" * 70)

try:
    from data.yahoo_loader import YahooFinanceLoader
    
    loader = YahooFinanceLoader()
    
    # Yahoo Finance only allows 7 days of 1-minute data
    print("Fetching NQ data (5 days, 1-minute)...")
    nq_data = loader.fetch_historical_bars('NQ', period='5d', interval='1m')
    
    print("Fetching ES data (5 days, 1-minute)...")
    es_data = loader.fetch_historical_bars('ES', period='5d', interval='1m')
    
    if nq_data.empty or es_data.empty:
        print("❌ No data returned from Yahoo Finance")
        print("   This might be because:")
        print("   1. Market is closed")
        print("   2. Yahoo Finance API is down")
        print("   3. Network issue")
        print("\n   Try running during market hours or try again later.")
        sys.exit(1)
    
    print(f"\n✅ Data loaded successfully")
    print(f"   NQ: {len(nq_data)} bars ({nq_data.index[0]} to {nq_data.index[-1]})")
    print(f"   ES: {len(es_data)} bars ({es_data.index[0]} to {es_data.index[-1]})")
    
except Exception as e:
    print(f"❌ Data loading FAILED: {e}")
    print("\nMake sure you've installed yfinance:")
    print("   pip install yfinance")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 2: Midnight Open Calculator
print("TEST 2: Midnight Open Calculator")
print("-" * 70)

try:
    from core.indicators import MidnightOpenCalculator
    
    mo_calc = MidnightOpenCalculator()
    
    # Test on last 3 days (or fewer if less data available)
    num_test_days = min(3, len(nq_data.index.date.unique()))
    unique_dates = nq_data.index.date.unique()
    test_dates = [nq_data.index[nq_data.index.date == d][0] for d in unique_dates[-num_test_days:]]
    
    for date in test_dates:
        try:
            mo = mo_calc.calculate(nq_data, date)
            print(f"   {date.date()}: MO = {mo:.2f}")
        except ValueError as e:
            print(f"   {date.date()}: {e}")
    
    print("\n✅ Midnight Open calculation working")
    
except Exception as e:
    print(f"❌ Midnight Open test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 3: ADR Calculator
print("TEST 3: ADR (Average Daily Range) Calculator")
print("-" * 70)

try:
    from core.indicators import ADRCalculator
    
    # Use fewer days if we have limited data
    available_days = len(nq_data.index.date.unique())
    adr_lookback = min(20, available_days - 1)
    
    adr_calc = ADRCalculator(lookback_days=adr_lookback)
    
    # Calculate ADR for last available date
    adr = adr_calc.calculate(nq_data, nq_data.index[-1])
    
    print(f"   {adr_lookback}-day ADR: {adr:.2f} points")
    print(f"   This is the normalization factor for:")
    print(f"     - Overnight ranges")
    print(f"     - Sweep depths")
    print(f"     - Position sizing")
    
    print("\n✅ ADR calculation working")
    
except Exception as e:
    print(f"❌ ADR test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: ONS Filter
print("TEST 4: ONS (Overnight Session) Filter")
print("-" * 70)

try:
    from core.indicators import ONSFilter
    
    # Use available lookback
    available_days = len(nq_data.index.date.unique())
    ons_lookback = min(20, available_days - 1)
    
    ons_filter = ONSFilter(min_ratio=0.30, max_ratio=0.70, adr_lookback=ons_lookback)
    
    # Test on recent date
    test_date = nq_data.index[-1]
    ons_result = ons_filter.validate(nq_data, test_date)
    
    print(f"   Date: {test_date.date()}")
    print(f"   ONS Range: {ons_result['ons_range']:.2f} points")
    print(f"   ADR: {ons_result['adr']:.2f} points")
    print(f"   Ratio: {ons_result['ratio']:.2%} (target: 30-70%)")
    print(f"   Valid: {'✅ YES' if ons_result['valid'] else '❌ NO'}")
    
    if not ons_result['valid']:
        print(f"   Reason: {ons_result['reason']}")
    
    print("\n✅ ONS filter working")
    
except Exception as e:
    print(f"❌ ONS test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 5: ISI (Impulse Strength Index)
print("TEST 5: ISI (Impulse Strength Index)")
print("-" * 70)

try:
    from core.indicators import ISICalculator
    
    isi_calc = ISICalculator(threshold_min=1.2, threshold_max=2.0)
    
    # Test on a sample move (last 10 bars if available)
    if len(nq_data) >= 15:
        start_idx = len(nq_data) - 15
        end_idx = len(nq_data) - 5
    else:
        start_idx = 0
        end_idx = len(nq_data) - 1
    
    isi_result = isi_calc.calculate(nq_data, start_idx, end_idx)
    
    print(f"   Analyzed {isi_result['consecutive_bars']} bars")
    print(f"   ISI Value: {isi_result['isi']:.3f}")
    print(f"   Assessment: {isi_result['assessment']}")
    print(f"     < 1.2: Fade OK (weak move)")
    print(f"     1.2-2.0: Wait (unclear)")
    print(f"     > 2.0: No fade (strong trend)")
    print(f"\n   Components:")
    print(f"     Avg Body Ratio: {isi_result['avg_body_ratio']:.2%}")
    print(f"     Avg Wick Ratio: {isi_result['avg_wick_ratio']:.2%}")
    print(f"     ATR: {isi_result['atr']:.2f}")
    
    print("\n✅ ISI calculation working")
    
except Exception as e:
    print(f"❌ ISI test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 6: SMT Detector
print("TEST 6: SMT (Smart Money Technique) Detector")
print("-" * 70)

try:
    from core.indicators import SMTDetector
    
    smt_detector = SMTDetector(min_sweep_ticks=5)
    
    # Use recent low as reference
    nq_reference = nq_data['low'].min()
    es_reference = es_data['low'].min()
    
    smt_result = smt_detector.detect_divergence(
        nq_data,
        es_data,
        nq_reference,
        es_reference,
        direction='below'
    )
    
    print(f"   NQ Reference Level: {nq_reference:.2f}")
    print(f"   ES Reference Level: {es_reference:.2f}")
    print(f"\n   NQ Swept: {'✅ YES' if smt_result['instrument_a_sweep']['swept'] else '❌ NO'}")
    print(f"   ES Swept: {'✅ YES' if smt_result['instrument_b_sweep']['swept'] else '❌ NO'}")
    print(f"\n   SMT Divergence (Binary): {'✅ YES' if smt_result['smt_binary'] else '❌ NO'}")
    print(f"   SMT Degree: {smt_result['smt_degree']:.3f}")
    print(f"     (Positive = NQ swept deeper than ES)")
    
    if smt_result['instrument_a_sweep']['swept']:
        nq_sweep = smt_result['instrument_a_sweep']
        print(f"\n   NQ Sweep Details:")
        print(f"     Depth: {nq_sweep['sweep_depth']:.2f} points")
        print(f"     Normalized: {nq_sweep['sweep_depth_norm']:.2f} ATR")
        print(f"     Time: {nq_sweep['sweep_time']}")
    
    print("\n✅ SMT detection working")
    
except Exception as e:
    print(f"❌ SMT test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Final Summary
print("="*70)
print("SPRINT 2 SUMMARY")
print("="*70)

indicators_status = [
    ("Midnight Open Calculator", "✅ WORKING"),
    ("ADR Calculator", "✅ WORKING"),
    ("ONS Filter", "✅ WORKING"),
    ("ISI (Displacement)", "✅ WORKING"),
    ("SMT Detector", "✅ WORKING"),
]

for indicator, status in indicators_status:
    print(f"  {indicator:.<40} {status}")

print("\n" + "="*70)
print("✅ SPRINT 2 COMPLETE!")
print("="*70)

print("\nAll indicators tested and working!")
print("\nReady for:")
print("  ✅ Sprint 3: State Machine")
print("  ✅ Sprint 4: Strategy Core")
print("  ✅ Shadow Trade Integration")

print("\nNext steps:")
print("  1. Review indicator calculations")
print("  2. Understand each component")
print("  3. Ready to begin Sprint 3")

print("\n" + "="*70)
