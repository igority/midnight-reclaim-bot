"""
Sprint 5 Test Script
====================
Tests the risk management module with position sizing and P&L tracking.

Run this to verify Sprint 5 completion.
"""

import unittest
from core.risk_manager import RiskManager, Position


class TestSprint5(unittest.TestCase):
    """Test class for Sprint 5 risk management tests."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize risk manager with test parameters
        self.risk_manager = RiskManager(
            account_size=100000.0,
            risk_per_trade_pct=0.01,
            tp1_r_multiple=1.0,
            partial_exit_pct=0.50
        )
        
        # NQ instrument specs
        self.nq_spec = {
            'point_value': 20.0,
            'tick_size': 0.25,
            'tick_value': 5.0
        }

    def test_risk_manager_initialization(self):
        """Test 1: Risk Manager Initialization"""
        self.assertIsNotNone(self.risk_manager)
        self.assertEqual(self.risk_manager.account_size, 100000.0)
        self.assertEqual(self.risk_manager.risk_per_trade_pct, 0.01)
        self.assertEqual(self.risk_manager.risk_per_trade_dollars, 1000.0)
        self.assertEqual(self.risk_manager.tp1_r_multiple, 1.0)
        self.assertEqual(self.risk_manager.partial_exit_pct, 0.50)

    def test_position_size_calculation(self):
        """Test 2: Position Size Calculation"""
        # Test scenario: Entry at 20000, Stop at 19950 (50 point risk)
        entry = 20000.0
        stop = 19950.0
        
        position_size = self.risk_manager.calculate_position_size(
            entry_price=entry,
            stop_loss=stop,
            instrument_spec=self.nq_spec
        )
        
        # Expected: $1000 risk / (50 points * $20/point) = 1 contract
        self.assertEqual(position_size, 1)
        
        # Test with smaller risk (25 point stop)
        entry2 = 20000.0
        stop2 = 19975.0
        
        position_size2 = self.risk_manager.calculate_position_size(
            entry_price=entry2,
            stop_loss=stop2,
            instrument_spec=self.nq_spec
        )
        
        # Expected: $1000 / (25 points * $20/point) = 2 contracts
        self.assertEqual(position_size2, 2)

    def test_open_long_position(self):
        """Test 3: Opening LONG Position"""
        entry = 20000.0
        stop = 19950.0
        bias = "LONG"
        
        position = self.risk_manager.open_position(
            entry_price=entry,
            stop_loss=stop,
            bias=bias,
            instrument_spec=self.nq_spec
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.entry_price, entry)
        self.assertEqual(position.stop_loss, stop)
        self.assertEqual(position.initial_position_size, 1)
        self.assertEqual(position.current_position_size, 1)
        
        # TP1 should be entry + 50 points (1R)
        self.assertEqual(position.tp1_price, 20050.0)
        
        self.assertFalse(position.tp1_hit)
        self.assertIsNone(position.trailing_stop)
        self.assertEqual(position.initial_risk_r, 1.0)

    def test_open_short_position(self):
        """Test 4: Opening SHORT Position"""
        entry = 20000.0
        stop = 20050.0
        bias = "SHORT"
        
        position = self.risk_manager.open_position(
            entry_price=entry,
            stop_loss=stop,
            bias=bias,
            instrument_spec=self.nq_spec
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.entry_price, entry)
        self.assertEqual(position.stop_loss, stop)
        
        # TP1 should be entry - 50 points (1R)
        self.assertEqual(position.tp1_price, 19950.0)

    def test_stop_loss_hit(self):
        """Test 5: Stop Loss Hit"""
        # Open LONG position
        self.risk_manager.open_position(
            entry_price=20000.0,
            stop_loss=19950.0,
            bias="LONG",
            instrument_spec=self.nq_spec
        )
        
        # Price drops to stop
        result = self.risk_manager.update_position(
            current_price=19950.0,
            instrument_spec=self.nq_spec
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'FULL_EXIT')
        self.assertEqual(result['reason'], 'STOP_LOSS')
        self.assertEqual(result['pnl_r'], -1.0)
        self.assertFalse(result['win'])
        self.assertFalse(result['position_remains'])
        
        # Position should be closed
        self.assertIsNone(self.risk_manager.current_position)

    def test_tp1_partial_exit(self):
        """Test 6: TP1 Partial Exit"""
        # Open LONG position
        self.risk_manager.open_position(
            entry_price=20000.0,
            stop_loss=19950.0,
            bias="LONG",
            instrument_spec=self.nq_spec
        )
        
        # Price reaches TP1
        result = self.risk_manager.update_position(
            current_price=20050.0,
            instrument_spec=self.nq_spec
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'PARTIAL_EXIT')
        self.assertEqual(result['reason'], 'TP1')
        self.assertEqual(result['pnl_r'], 1.0)
        self.assertTrue(result['position_remains'])
        
        # Position should still exist but reduced
        pos = self.risk_manager.current_position
        self.assertIsNotNone(pos)
        self.assertTrue(pos.tp1_hit)
        self.assertEqual(pos.trailing_stop, 20000.0)  # Moved to breakeven
        self.assertTrue(pos.breakeven_active)

    def test_trailing_stop_after_tp1(self):
        """Test 7: Trailing Stop After TP1"""
        # Open LONG position
        self.risk_manager.open_position(
            entry_price=20000.0,
            stop_loss=19950.0,
            bias="LONG",
            instrument_spec=self.nq_spec
        )
        
        # Hit TP1 (partial exit)
        self.risk_manager.update_position(
            current_price=20050.0,
            instrument_spec=self.nq_spec
        )
        
        # Price continues up
        result = self.risk_manager.update_position(
            current_price=20100.0,
            instrument_spec=self.nq_spec
        )
        
        # Should not exit yet (above breakeven)
        self.assertIsNone(result)
        
        # Price drops back to breakeven
        result = self.risk_manager.update_position(
            current_price=20000.0,
            instrument_spec=self.nq_spec
        )
        
        # Should exit at trailing stop (breakeven)
        self.assertIsNotNone(result)
        self.assertEqual(result['type'], 'FULL_EXIT')
        self.assertEqual(result['reason'], 'TRAILING_STOP')
        
        # Total P&L should be +1.0R (from TP1 partial) + 0R (remainder at BE)
        self.assertAlmostEqual(result['pnl_r'], 1.0, places=1)

    def test_full_winner_trade(self):
        """Test 8: Full Winner Trade (TP1 + Trailing)"""
        # Open LONG position
        self.risk_manager.open_position(
            entry_price=20000.0,
            stop_loss=19950.0,
            bias="LONG",
            instrument_spec=self.nq_spec
        )
        
        # Hit TP1
        self.risk_manager.update_position(
            current_price=20050.0,
            instrument_spec=self.nq_spec
        )
        
        # Price continues to 20100 and exits
        result = self.risk_manager.update_position(
            current_price=20000.0,
            instrument_spec=self.nq_spec
        )
        
        self.assertTrue(result['win'])
        self.assertGreater(result['pnl_r'], 0)

    def test_performance_tracking(self):
        """Test 9: Performance Tracking"""
        initial_account = self.risk_manager.account_size
        
        # Simulate a winning trade
        self.risk_manager.open_position(
            entry_price=20000.0,
            stop_loss=19950.0,
            bias="LONG",
            instrument_spec=self.nq_spec
        )
        
        # Hit TP1 and exit
        self.risk_manager.update_position(20050.0, self.nq_spec)
        self.risk_manager.update_position(20000.0, self.nq_spec)
        
        # Check statistics
        stats = self.risk_manager.get_performance_summary()
        
        self.assertEqual(stats['total_trades'], 1)
        self.assertEqual(stats['winning_trades'], 1)
        self.assertGreater(stats['total_pnl_dollars'], 0)
        self.assertGreater(stats['account_size'], initial_account)
        self.assertEqual(stats['win_rate'], 100.0)

    def test_multiple_trades(self):
        """Test 10: Multiple Trades"""
        # Trade 1: Winner
        self.risk_manager.open_position(20000.0, 19950.0, "LONG", self.nq_spec)
        self.risk_manager.update_position(20050.0, self.nq_spec)
        self.risk_manager.update_position(20000.0, self.nq_spec)
        
        # Trade 2: Loser
        self.risk_manager.open_position(20000.0, 19950.0, "LONG", self.nq_spec)
        self.risk_manager.update_position(19950.0, self.nq_spec)
        
        # Check statistics
        stats = self.risk_manager.get_performance_summary()
        
        self.assertEqual(stats['total_trades'], 2)
        self.assertEqual(stats['winning_trades'], 1)
        self.assertEqual(stats['losing_trades'], 1)
        self.assertEqual(stats['win_rate'], 50.0)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
