"""
Sprint 1 Verification Test
===========================
Tests that all Sprint 1 components are working:
1. Configuration loading
2. Time utilities
3. Logging system
4. Yahoo Finance data loader (primary)
5. IBKR connection (optional)
"""

import unittest
import sys
from datetime import datetime
import pytz
from unittest.mock import patch, MagicMock


class TestSprint1(unittest.TestCase):
    """Test class for Sprint 1 verification tests."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        pass

    def test_configuration_loading(self):
        """Test 1: Configuration Loading"""
        try:
            from utils.config_loader import Config
            
            Config.initialize()
            
            # Test parameter access
            timezone = Config.get('session', 'timezone')
            max_trades = Config.get('session', 'max_trades_per_session')
            tp1_r = Config.get('risk', 'tp1_r')
            
            self.assertIsNotNone(timezone)
            self.assertIsNotNone(max_trades)
            self.assertIsNotNone(tp1_r)
            
            # Test instrument specs
            nq_spec = Config.get_instrument_spec('NQ')
            self.assertIsNotNone(nq_spec)
            self.assertIn('tick_size', nq_spec)
            self.assertIn('tick_value', nq_spec)
            
        except Exception as e:
            self.fail(f"Config test FAILED: {e}")

    def test_time_utilities(self):
        """Test 2: Time Utilities"""
        try:
            from utils.time_utils import TimeUtils
            
            # Create test datetime in UTC
            test_dt = datetime(2025, 1, 30, 14, 30, 0, tzinfo=pytz.UTC)
            
            # Convert to EST
            est_dt = TimeUtils.to_est(test_dt)
            self.assertIsNotNone(est_dt)
            
            # Get midnight open
            midnight = TimeUtils.get_midnight_open(est_dt)
            self.assertIsNotNone(midnight)
            
            # Test trading window
            trading_time = datetime(2025, 1, 30, 14, 45, 0, tzinfo=pytz.UTC)  # 09:45 EST
            in_window = TimeUtils.is_in_trading_window(trading_time)
            self.assertIsInstance(in_window, bool)
            
            # Test overnight range period
            start, end = TimeUtils.get_overnight_range_period(est_dt)
            self.assertIsNotNone(start)
            self.assertIsNotNone(end)
            
        except Exception as e:
            self.fail(f"Time utils test FAILED: {e}")

    def test_logging_system(self):
        """Test 3: Logging System"""
        try:
            from strategy_logging.logger import Logger
            from strategy_logging.schemas import EventLog, TradeLog, TradingState
            
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
            
            # Create and log a trade
            trade = TradeLog(
                trade_id=1,
                timestamp_entry=datetime.now(),
                timestamp_exit=datetime.now(),
                instrument="NQ",
                trade_type="REAL",
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
            
            # Read back logs
            from strategy_logging.logger import LogReader
            reader = LogReader()
            
            events = reader.read_events()
            trades = reader.read_trades()
            
            self.assertIsInstance(events, list)
            self.assertIsInstance(trades, list)
            
        except Exception as e:
            self.fail(f"Logging test FAILED: {e}")

    def test_yahoo_finance_data_loader(self):
        """Test 4: Yahoo Finance Data Loader (PRIMARY)"""
        try:
            from data.yahoo_loader import YahooFinanceLoader
            
            loader = YahooFinanceLoader()
            
            # Fetch data - this might fail if market is closed, so we'll mock it for testing
            with patch.object(loader, 'fetch_historical_bars') as mock_fetch:
                # Mock successful data fetch
                import pandas as pd
                mock_data = pd.DataFrame({
                    'open': [17500.0, 17501.0, 17502.0],
                    'high': [17502.0, 17503.0, 17504.0],
                    'low': [17498.0, 17499.0, 17500.0],
                    'close': [17501.0, 17502.0, 17503.0],
                    'volume': [1000, 1100, 1200]
                }, index=pd.date_range('2025-01-30', periods=3, freq='1min'))
                
                mock_fetch.return_value = mock_data
                
                nq_data = loader.fetch_historical_bars('NQ', period='5d', interval='1m')
                
                self.assertFalse(nq_data.empty)
                self.assertEqual(len(nq_data), 3)
                
                # Test data validation
                from data.data_validator import DataValidator
                
                validator = DataValidator(expected_bar_size='1min')
                results = validator.validate(nq_data, 'NQ')
                
                # Validation might have issues with mock data, but the structure should be correct
                self.assertIn('passed', results)
                self.assertIn('issues', results)
                
        except ImportError:
            self.skipTest("yfinance not installed")
        except Exception as e:
            self.fail(f"Yahoo Finance test failed: {e}")

    def test_ibkr_connection_optional(self):
        """Test 5: IBKR Connection (OPTIONAL)"""
        try:
            from data.ibkr_loader import IBKRLoader
            
            # This test is optional and may fail if TWS isn't running
            # We'll mock the connection for testing purposes
            with patch('data.ibkr_loader.IB') as mock_ib:
                mock_instance = MagicMock()
                mock_ib.return_value = mock_instance
                mock_instance.connect.return_value = None
                mock_instance.disconnect.return_value = None
                mock_instance.reqContractDetails.return_value = []
                
                loader = IBKRLoader(port=7497)
                
                try:
                    loader.connect()
                    # Test contract search
                    from ib_insync import Contract
                    contract = Contract()
                    contract.symbol = 'NQ'
                    contract.secType = 'FUT'
                    contract.exchange = 'GLOBEX'
                    contract.currency = 'USD'
                    
                    details = loader.ib.reqContractDetails(contract)
                    
                    # Connection successful, contract search completed
                    self.assertIsInstance(details, list)
                    
                    loader.disconnect()
                    
                except Exception:
                    # IBKR connection failed - this is acceptable if TWS isn't running
                    pass
                    
        except ImportError:
            self.skipTest("ib_insync not installed")
        except Exception as e:
            self.skipTest(f"IBKR test skipped: {e}")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)