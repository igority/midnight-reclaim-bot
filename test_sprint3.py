"""
Sprint 3 Test Script
====================
Tests the state machine with all transitions and validations.

Run this to verify Sprint 3 completion.
"""

import unittest
from datetime import datetime
from utils.config_loader import Config
from strategy_logging.schemas import TradingState
from core.state_machine import StateMachine


class TestSprint3(unittest.TestCase):
    """Test class for Sprint 3 state machine tests."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        try:
            Config.initialize()
        except:
            pass

    def test_state_machine_creation(self):
        """Test 1: State Machine Creation"""
        try:
            sm = StateMachine()
            self.assertIsNotNone(sm)
            self.assertEqual(sm.current_state, TradingState.IDLE)
            self.assertIsInstance(sm.max_trades_per_session, int)
            self.assertIsInstance(sm.trades_taken_today, int)
            
        except Exception as e:
            self.fail(f"State machine creation FAILED: {e}")

    def test_valid_state_transitions(self):
        """Test 2: Valid State Transitions"""
        try:
            # Create fresh state machine
            sm = StateMachine()
            
            transitions = [
                (TradingState.SESSION_ACTIVE, "Trading window opened"),
                (TradingState.AWAITING_DEVIATION, "ONS valid (45% of ADR)"),
                (TradingState.AWAITING_SMT, "Price swept below midnight open"),
                (TradingState.AWAITING_RECLAIM, "SMT confirmed (NQ swept, ES didn't)"),
                (TradingState.IN_TRADE, "Reclaim candle triggered entry"),
                (TradingState.SESSION_LOCKED, "TP1 hit, trade complete"),
            ]
            
            all_passed = True
            for target_state, reason in transitions:
                result = sm.transition_to(target_state, reason)
                if not result:
                    all_passed = False
                    break
            
            self.assertTrue(all_passed, "All valid transitions should succeed")
            self.assertEqual(sm.current_state, TradingState.SESSION_LOCKED)
            self.assertGreater(len(sm.state_history), 0)
            
        except Exception as e:
            self.fail(f"Valid transitions test FAILED: {e}")

    def test_invalid_state_transitions(self):
        """Test 3: Invalid State Transition (Should Fail)"""
        try:
            # Create state machine and go to SESSION_LOCKED
            sm = StateMachine()
            sm.transition_to(TradingState.SESSION_ACTIVE, "Test")
            sm.transition_to(TradingState.SESSION_LOCKED, "Test")
            
            # Try to go from SESSION_LOCKED back to IN_TRADE (invalid)
            result = sm.transition_to(TradingState.IN_TRADE, "Trying invalid transition")
            
            self.assertFalse(result, "Invalid transition should be rejected")
            
        except Exception as e:
            self.fail(f"Invalid transition test FAILED: {e}")

    def test_ons_invalid_path(self):
        """Test 4: ONS Invalid Path (Early Session Lock)"""
        try:
            sm2 = StateMachine()
            
            # Session starts
            sm2.transition_to(TradingState.SESSION_ACTIVE, "Session opened")
            
            # ONS invalid - should lock session
            sm2.transition_to(TradingState.ONS_INVALID, "ONS range too tight (20% of ADR)")
            
            # Check can_trade
            can_trade, reason = sm2.can_trade()
            
            self.assertEqual(sm2.current_state, TradingState.ONS_INVALID)
            self.assertFalse(can_trade, "Should not be able to trade when ONS invalid")
            self.assertIsNotNone(reason)
            
        except Exception as e:
            self.fail(f"ONS invalid test FAILED: {e}")

    def test_trade_eligibility_checks(self):
        """Test 5: Trade Eligibility Checks"""
        try:
            # Test at different states
            test_cases = [
                (TradingState.IDLE, False),
                (TradingState.SESSION_ACTIVE, False),
                (TradingState.AWAITING_DEVIATION, True),
                (TradingState.AWAITING_SMT, True),
                (TradingState.AWAITING_RECLAIM, True),
                (TradingState.IN_TRADE, False),
                (TradingState.SESSION_LOCKED, False),
                (TradingState.ONS_INVALID, False),
            ]
            
            all_correct = True
            for state, expected_can_trade in test_cases:
                sm_test = StateMachine()
                sm_test.current_state = state
                can_trade, reason = sm_test.can_trade()
                
                if can_trade != expected_can_trade:
                    all_correct = False
                    break
            
            self.assertTrue(all_correct, "All eligibility checks should be correct")
            
        except Exception as e:
            self.fail(f"Eligibility test FAILED: {e}")

    def test_session_reset(self):
        """Test 6: Session Reset"""
        try:
            # Create state machine with some history
            sm = StateMachine()
            sm.transition_to(TradingState.SESSION_ACTIVE, "Test")
            sm.transition_to(TradingState.AWAITING_DEVIATION, "Test")
            sm.trades_taken_today = 2
            
            # Store before values
            before_state = sm.current_state
            before_trades = sm.trades_taken_today
            before_history_len = len(sm.state_history)
            
            # Reset
            sm.reset_for_new_session(datetime.now())
            
            # Check after values
            self.assertEqual(sm.current_state, TradingState.IDLE)
            self.assertEqual(sm.trades_taken_today, 0)
            # Note: History is preserved, not reset to 1
            self.assertGreaterEqual(len(sm.state_history), before_history_len)
            
        except Exception as e:
            self.fail(f"Session reset test FAILED: {e}")

    def test_state_summary(self):
        """Test 7: State Summary"""
        try:
            # Create a fresh state machine with some transitions
            sm3 = StateMachine()
            sm3.transition_to(TradingState.SESSION_ACTIVE, "Test")
            sm3.transition_to(TradingState.AWAITING_DEVIATION, "Test")
            
            summary = sm3.get_state_summary()
            
            self.assertIsInstance(summary, dict)
            self.assertIn('current_state', summary)
            self.assertIn('trades_taken', summary)  # Changed from 'trades_taken_today'
            self.assertIn('max_trades', summary)    # Changed from 'max_trades_per_session'
            self.assertIn('can_trade', summary)
            
        except Exception as e:
            self.fail(f"State summary test FAILED: {e}")

    def test_transition_history(self):
        """Test 8: Transition History"""
        try:
            # Create state machine with transitions
            sm3 = StateMachine()
            sm3.transition_to(TradingState.SESSION_ACTIVE, "Test")
            sm3.transition_to(TradingState.AWAITING_DEVIATION, "Test")
            
            history = sm3.get_transition_history()
            
            self.assertIsInstance(history, list)
            self.assertGreater(len(history), 0)
            
            if history:
                last = history[-1]
                self.assertIn('from', last)
                self.assertIn('to', last)
                self.assertIn('reason', last)
                self.assertIn('timestamp', last)
            
        except Exception as e:
            self.fail(f"Transition history test FAILED: {e}")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)