"""
Sprint 1 Verification Test
===========================
Tests that all Sprint 1 components are working:
1. Configuration loading
2. Time utilities
3. Logging system
4. IBKR connection (optional - requires TWS running)
"""

import sys
from datetime import datetime
import pytz

print("="*70)
print("SPRINT 1 VERIFICATION TEST")
print("="*70)
print()

# Test 1: Configuration Loading
print("TEST 1: Configuration Loading")
print("-" * 70)

try:
    from utils.config_loader import Config
    
    Config.initialize()
    
    # Test parameter access
    timezone = Config.get('session', 'timezone')
    max_trades = Config.get('session', 'max_trades_per_session')
    tp1_r = Config.get('risk', 'tp1_r')
    
    print(f"✅ Config loaded successfully")
    print(f"   Timezone: {timezone}")
    print(f"   Max trades/session: {max_trades}")
    print(f"   TP1 R-multiple: {tp1_r}")
    
    # Test instrument specs
    nq_spec = Config.get_instrument_spec('NQ')
    print(f"   NQ tick size: {nq_spec['tick_size']}")
    print(f"   NQ tick value: ${nq_spec['tick_value']}")
    
except Exception as e:
    print(f"❌ Config test FAILED: {e}")
    sys.exit(1)

print()

# Test 2: Time Utilities
print("TEST 2: Time Utilities")
print("-" * 70)

try:
    from utils.time_utils import TimeUtils
    
    # Create test datetime in UTC
    test_dt = datetime(2025, 1, 30, 14, 30, 0, tzinfo=pytz.UTC)
    
    # Convert to EST
    est_dt = TimeUtils.to_est(test_dt)
    print(f"✅ Time conversion working")
    print(f"   UTC: {test_dt}")
    print(f"   EST: {est_dt}")
    
    # Get midnight open
    midnight = TimeUtils.get_midnight_open(est_dt)
    print(f"   Midnight Open: {midnight}")
    
    # Test trading window
    trading_time = datetime(2025, 1, 30, 14, 45, 0, tzinfo=pytz.UTC)  # 09:45 EST
    in_window = TimeUtils.is_in_trading_window(trading_time)
    print(f"   09:45 EST in trading window? {in_window}")
    
    # Test overnight range period
    start, end = TimeUtils.get_overnight_range_period(est_dt)
    print(f"   ONS period: {TimeUtils.format_est(start, '%H:%M')} → {TimeUtils.format_est(end, '%H:%M')}")
    
except Exception as e:
    print(f"❌ Time utils test FAILED: {e}")
    sys.exit(1)

print()

# Test 3: Logging System
print("TEST 3: Logging System")
print("-" * 70)

try:
    from logging.logger import Logger
    from logging.schemas import EventLog, TradeLog, TradingState
    
    # Initialize logger
    logger = Logger()
    
    # Create and log an event
    event = EventLog(
        timestamp=datetime.now(),
        instrument="NQ",
        state=TradingState.AWAITING_RECLAIM,
        open=17500.0,
        high=17520.0,
        low=17495.0,
        close=17510.0,
        volume=1000,
        midnight_open=17550.0,
        smt_binary=True,
        smt_degree=0.45
    )
    
    logger.log_event(event)
    print("✅ Event logging working")
    
    # Create and log a trade
    trade = TradeLog(
        trade_id=1,
        timestamp_entry=datetime.now(),
        timestamp_exit=datetime.now(),
        instrument="NQ",
        direction="LONG",
        midnight_open=17550.0,
        deviation_extreme=17500.0,
        entry_price=17552.0,
        smt_binary=True,
        smt_degree=0.45,
        nq_sweep_depth_norm=0.8,
        es_sweep_depth_norm=0.35,
        isi_value=1.1,
        minutes_to_reclaim=32,
        reclaim_body_ratio=0.72,
        stop_loss=17495.0,
        tp1_price=17607.0,
        initial_risk_r=1.0,
        exit_price=17607.0,
        exit_reason="TP1",
        pnl_points=55.0,
        pnl_r=1.0,
        pnl_dollars=1100.0,
        win=True,
        overnight_range=45.0,
        adr=80.0,
        ons_ratio=0.56,
        regime_high_vol=False,
        regime_trend_day=False,
        regime_gap_day=True,
        regime_news_day=False
    )
    
    logger.log_trade(trade)
    print("✅ Trade logging working")
    
    # Read back logs
    from logging.logger import LogReader
    reader = LogReader()
    
    events = reader.read_events()
    trades = reader.read_trades()
    
    print(f"✅ Log reading working")
    print(f"   Events in today's log: {len(events)}")
    print(f"   Trades in today's log: {len(trades)}")
    
except Exception as e:
    print(f"❌ Logging test FAILED: {e}")
    sys.exit(1)

print()

# Test 4: IBKR Connection (Optional - only if TWS is running)
print("TEST 4: IBKR Connection (Optional)")
print("-" * 70)
print("⚠️  This test requires TWS/Gateway to be running")
print("   If you don't have it running, this test will be skipped")
print()

try:
    from data.ibkr_loader import IBKRLoader
    
    # Try to connect with a short timeout
    loader = IBKRLoader(port=7497)
    
    try:
        loader.connect()
        print("✅ IBKR connection successful!")
        
        # Try to fetch just a few bars as a quick test
        print("   Attempting to fetch sample data...")
        
        nq_data = loader.fetch_historical_bars(
            symbol="NQ",
            duration="1 D",
            bar_size="1 min"
        )
        
        if not nq_data.empty:
            print(f"✅ Data fetch successful!")
            print(f"   Fetched {len(nq_data)} bars")
            print(f"   Sample data:")
            print(nq_data.head(3))
        else:
            print("⚠️  Data fetch returned empty (this might be OK if market is closed)")
        
        loader.disconnect()
        
    except Exception as e:
        print(f"⚠️  IBKR connection failed (this is OK if TWS isn't running)")
        print(f"   Error: {e}")
        print(f"   To fix: Start TWS/Gateway and enable API access")
        
except ImportError as e:
    print(f"⚠️  ib_insync not installed: {e}")
except Exception as e:
    print(f"⚠️  IBKR test skipped: {e}")

print()

# Final Summary
print("="*70)
print("SPRINT 1 VERIFICATION SUMMARY")
print("="*70)
print()
print("✅ Configuration system: WORKING")
print("✅ Time utilities: WORKING")
print("✅ Logging system: WORKING")
print("⚠️  IBKR connection: OPTIONAL (start TWS to test)")
print()
print("="*70)
print("SPRINT 1: COMPLETE ✅")
print("="*70)
print()
print("Next steps:")
print("1. Review generated log files in logs/events/ and logs/trades/")
print("2. Start TWS/Gateway and run test again to verify IBKR connection")
print("3. Ready to begin Sprint 2: Indicators")
print()
