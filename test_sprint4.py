"""
Sprint 4 Test Script
====================
Tests the complete strategy engine with real data.

Run this to verify Sprint 4 completion.
"""

import unittest
from datetime import datetime, timedelta
import pandas as pd


class TestSprint4(unittest.TestCase):
    """Test class for Sprint 4 strategy engine tests."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before all test methods."""
        try:
            from data.yahoo_loader import YahooFinanceLoader
            
            loader = YahooFinanceLoader()
            
            # Load real data from Yahoo Finance (same as test_sprint4_file.py)
            print("Loading NQ data from Yahoo Finance...")
            cls.nq_data = loader.fetch_historical_bars('NQ', period='5d', interval='1m')
            
            print("Loading ES data from Yahoo Finance...")
            cls.es_data = loader.fetch_historical_bars('ES', period='5d', interval='1m')
            
            if cls.nq_data.empty or cls.es_data.empty:
                cls.skip_tests = True
                cls.skip_reason = "No data available (market might be closed)"
            else:
                cls.skip_tests = False
                cls.skip_reason = None
                
        except Exception as e:
            cls.skip_tests = True
            cls.skip_reason = f"Data loading failed: {e}"

    def setUp(self):
        """Set up test fixtures before each test method."""
        if self.skip_tests:
            self.skipTest(self.skip_reason)

    def test_data_loading(self):
        """Test 1: Loading Market Data"""
        # Data is already loaded in setUpClass, just verify it
        self.assertFalse(self.nq_data.empty, "NQ data should not be empty")
        self.assertFalse(self.es_data.empty, "ES data should not be empty")
        print(f"   NQ: {len(self.nq_data)} bars")
        print(f"   ES: {len(self.es_data)} bars")
        print(f"   Date range: {self.nq_data.index[0].date()} to {self.nq_data.index[-1].date()}")

    def test_strategy_engine_initialization(self):
        """Test 2: Strategy Engine Initialization"""
        try:
            from core.strategy import StrategyEngine
            
            engine = StrategyEngine()
            self.assertIsNotNone(engine)
            self.assertIsNotNone(engine.state_machine)
            # Note: StrategyEngine doesn't have an 'indicators' attribute
            # It has individual indicator calculators instead
            
        except Exception as e:
            self.fail(f"Strategy engine initialization FAILED: {e}")

    def test_single_session_execution(self):
        """Test 3: Running Strategy on Most Recent Session"""
        try:
            from core.strategy import StrategyEngine
            
            engine = StrategyEngine()
            
            # Get most recent complete trading day
            unique_dates = list(set(self.nq_data.index.date))
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
            result = engine.run_session(self.nq_data, self.es_data, test_datetime)
            
            # Verify result structure
            self.assertIn('session_date', result)
            self.assertIn('trades', result)
            self.assertIsInstance(result['trades'], int)
            
            print(f"\nSession Results:")
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
            
        except Exception as e:
            self.fail(f"Strategy execution FAILED: {e}")

    def test_multi_session_execution(self):
        """Test 4: Running Strategy on Multiple Sessions"""
        try:
            from core.strategy import StrategyEngine
            
            # Test on last 3 days
            unique_dates = list(set(self.nq_data.index.date))
            unique_dates.sort()
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
                result = engine.run_session(self.nq_data, self.es_data, test_datetime)
                
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
            
        except Exception as e:
            self.fail(f"Multi-session test FAILED: {e}")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)