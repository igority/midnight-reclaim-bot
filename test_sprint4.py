"""
Sprint 4 Test Script
====================
Tests the complete strategy engine with real data.

Run this to verify Sprint 4 completion.
"""

import sys
from datetime import datetime, timedelta
from data.yahoo_loader import YahooFinanceLoader
from core.strategy import StrategyEngine

print("="*70)
print("SPRINT 4: STRATEGY ENGINE TESTING")
print("="*70)
print()

# Test 1: Load Data
print("TEST 1: Loading Market Data")
print("-" * 70)

try:
    loader = YahooFinanceLoader()
    
    print("Fetching NQ data (5 days, 1-minute)...")
    nq_data = loader.fetch_historical_bars('NQ', period='5d', interval='1m')
    
    print("Fetching ES data (5 days, 1-minute)...")
    es_data = loader.fetch_historical_bars('ES', period='5d', interval='1m')
    
    if nq_data.empty or es_data.empty:
        print("❌ No data available (market might be closed)")
        print("   Try running during US market hours or on a weekday")
        sys.exit(1)
    
    print(f"✅ Data loaded successfully")
    print(f"   NQ: {len(nq_data)} bars")
    print(f"   ES: {len(es_data)} bars")
    print(f"   Date range: {nq_data.index[0].date()} to {nq_data.index[-1].date()}")
    
except Exception as e:
    print(f"❌ Data loading FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 2: Strategy Engine Initialization
print("TEST 2: Strategy Engine Initialization")
print("-" * 70)

try:
    engine = StrategyEngine()
    print("\n✅ Strategy engine initialized successfully")
    
except Exception as e:
    print(f"❌ Strategy engine initialization FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 3: Run Strategy on Single Session
print("TEST 3: Running Strategy on Most Recent Session")
print("-" * 70)

try:
    # Get most recent complete trading day
    unique_dates = list(set(nq_data.index.date))
    unique_dates.sort()
    
    # Use second-to-last date (last date might be incomplete)
    if len(unique_dates) >= 2:
        test_date = unique_dates[-2]
    else:
        test_date = unique_dates[-1]
    
    # Convert to datetime
    test_datetime = datetime.combine(test_date, datetime.min.time())
    
    print(f"\nRunning strategy for: {test_date}")
    print("-" * 70)
    
    # Run strategy
    result = engine.run_session(nq_data, es_data, test_datetime)
    
    print("\n" + "="*70)
    print("SESSION RESULTS")
    print("="*70)
    print(f"Date: {result['session_date'].date()}")
    print(f"Trades taken: {result['trades']}")
    print(f"Final state: {result.get('state', 'N/A')}")
    
    if 'midnight_open' in result:
        print(f"Midnight open: {result['midnight_open']:.2f}")
    if 'adr' in result:
        print(f"ADR: {result['adr']:.2f}")
    if 'bias' in result:
        print(f"Bias: {result['bias']}")
    if 'reason' in result:
        print(f"No-trade reason: {result['reason']}")
    
    print("\n✅ Strategy execution completed successfully")
    
except Exception as e:
    print(f"\n❌ Strategy execution FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: Run Strategy on Multiple Sessions
print("TEST 4: Running Strategy on Multiple Sessions")
print("-" * 70)

try:
    # Test on last 3 days
    test_dates = unique_dates[-3:]
    
    print(f"\nTesting {len(test_dates)} sessions...")
    print()
    
    results_summary = []
    
    for date in test_dates:
        print(f"\n{'='*70}")
        print(f"Session: {date}")
        print(f"{'='*70}")
        
        # Reset engine for new session
        engine = StrategyEngine()
        
        test_datetime = datetime.combine(date, datetime.min.time())
        result = engine.run_session(nq_data, es_data, test_datetime)
        
        results_summary.append({
            'date': date,
            'trades': result['trades'],
            'state': result.get('state', 'UNKNOWN')
        })
    
    # Summary
    print("\n" + "="*70)
    print("MULTI-SESSION SUMMARY")
    print("="*70)
    
    total_trades = sum(r['trades'] for r in results_summary)
    
    for r in results_summary:
        print(f"{r['date']}: {r['trades']} trades, final state: {r['state']}")
    
    print(f"\nTotal trades across {len(test_dates)} sessions: {total_trades}")
    
    print("\n✅ Multi-session test completed")
    
except Exception as e:
    print(f"\n❌ Multi-session test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Final Summary
print("="*70)
print("SPRINT 4 SUMMARY")
print("="*70)

tests_status = [
    ("Data Loading", "✅ WORKING"),
    ("Strategy Initialization", "✅ WORKING"),
    ("Single Session Execution", "✅ WORKING"),
    ("Multi-Session Execution", "✅ WORKING"),
]

for test, status in tests_status:
    print(f"  {test:.<40} {status}")

print("\n" + "="*70)
print("✅ SPRINT 4 COMPLETE!")
print("="*70)

print("\nStrategy engine is operational!")
print("\nReady for:")
print("  ✅ Sprint 5: Risk Management & Execution")
print("  ✅ Sprint 6: Backtesting Framework")
print("  ✅ Live trading preparation")

print("\nNext steps:")
print("  1. Review strategy execution flow")
print("  2. Check generated logs")
print("  3. Understand entry/exit logic")
print("  4. Ready for risk management (Sprint 5)")

print("\n" + "="*70)
