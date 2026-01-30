"""
Trading State Machine
=====================
Manages the state flow of the trading strategy.

States represent where we are in the trading logic:
- IDLE: Before session starts
- SESSION_ACTIVE: Session started, conditions being checked  
- ONS_INVALID: Overnight range failed (locked for session)
- AWAITING_DEVIATION: Waiting for price to sweep key levels
- AWAITING_SMT: Deviation detected, checking for SMT
- AWAITING_RECLAIM: SMT confirmed, waiting for reclaim
- IN_TRADE: Position is open
- SESSION_LOCKED: Trade complete or failed, no more trades today

State transitions are one-way and irreversible (except IDLE reset).
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from strategy_logging.schemas import TradingState
from utils.config_loader import Config


@dataclass
class StateTransition:
    """Records a state transition for logging and debugging."""
    timestamp: datetime
    from_state: TradingState
    to_state: TradingState
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)


class StateMachine:
    """
    Trading state machine.
    
    Manages state transitions and enforces trading rules.
    """
    
    def __init__(self):
        """Initialize state machine."""
        self.current_state = TradingState.IDLE
        self.previous_state: Optional[TradingState] = None
        
        # State history
        self.state_history: List[StateTransition] = []
        
        # Session tracking
        self.trades_taken_today = 0
        self.max_trades_per_session = Config.get('session', 'max_trades_per_session')
        
        # Session date tracking
        self.current_session_date: Optional[datetime] = None
        
        # Context data
        self.context: Dict[str, Any] = {}
        
    def transition_to(
        self, 
        new_state: TradingState, 
        reason: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            new_state: Target state
            reason: Why this transition is happening
            context: Additional context data
        
        Returns:
            True if transition successful, False if invalid
        """
        # Validate transition
        if not self._is_valid_transition(self.current_state, new_state):
            print(f"⚠️  Invalid transition: {self.current_state.value} → {new_state.value}")
            return False
        
        # Record transition
        transition = StateTransition(
            timestamp=datetime.now(),
            from_state=self.current_state,
            to_state=new_state,
            reason=reason,
            context=context or {}
        )
        
        self.state_history.append(transition)
        
        # Update context
        if context:
            self.context.update(context)
        
        # Log transition
        print(f"🔄 State: {self.current_state.value} → {new_state.value}")
        print(f"   Reason: {reason}")
        
        # Update state
        self.previous_state = self.current_state
        self.current_state = new_state
        
        # Handle special state actions
        self._on_state_entered(new_state, reason)
        
        return True
    
    def _is_valid_transition(self, from_state: TradingState, to_state: TradingState) -> bool:
        """
        Check if a state transition is valid.
        
        Valid transitions follow the strategy flow:
        IDLE → SESSION_ACTIVE
        SESSION_ACTIVE → ONS_INVALID | AWAITING_DEVIATION
        AWAITING_DEVIATION → AWAITING_SMT | SESSION_LOCKED
        AWAITING_SMT → AWAITING_RECLAIM | SESSION_LOCKED
        AWAITING_RECLAIM → IN_TRADE | SESSION_LOCKED
        IN_TRADE → SESSION_LOCKED
        SESSION_LOCKED → IDLE (next session)
        ONS_INVALID → IDLE (next session)
        
        Args:
            from_state: Current state
            to_state: Target state
        
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            TradingState.IDLE: [
                TradingState.SESSION_ACTIVE
            ],
            TradingState.SESSION_ACTIVE: [
                TradingState.ONS_INVALID,
                TradingState.AWAITING_DEVIATION
            ],
            TradingState.ONS_INVALID: [
                TradingState.IDLE  # Reset for next session
            ],
            TradingState.AWAITING_DEVIATION: [
                TradingState.AWAITING_SMT,
                TradingState.SESSION_LOCKED
            ],
            TradingState.AWAITING_SMT: [
                TradingState.AWAITING_RECLAIM,
                TradingState.SESSION_LOCKED
            ],
            TradingState.AWAITING_RECLAIM: [
                TradingState.IN_TRADE,
                TradingState.SESSION_LOCKED
            ],
            TradingState.IN_TRADE: [
                TradingState.SESSION_LOCKED
            ],
            TradingState.SESSION_LOCKED: [
                TradingState.IDLE  # Reset for next session
            ]
        }
        
        # Check if transition is in valid list
        allowed = valid_transitions.get(from_state, [])
        return to_state in allowed
    
    def _on_state_entered(self, state: TradingState, reason: str) -> None:
        """
        Handle actions when entering a new state.
        
        Args:
            state: The state we just entered
            reason: Why we entered it
        """
        if state == TradingState.IN_TRADE:
            self.trades_taken_today += 1
            print(f"   📊 Trades today: {self.trades_taken_today}/{self.max_trades_per_session}")
        
        elif state == TradingState.SESSION_LOCKED:
            print(f"   🔒 Session locked (no more trades today)")
        
        elif state == TradingState.ONS_INVALID:
            print(f"   ❌ ONS filter failed - session locked")
    
    def can_trade(self) -> tuple[bool, Optional[str]]:
        """
        Check if we can take a trade right now.
        
        Returns:
            Tuple of (can_trade, reason_if_not)
        """
        # Already in trade
        if self.current_state == TradingState.IN_TRADE:
            return False, "Already in trade"
        
        # Session locked
        if self.current_state == TradingState.SESSION_LOCKED:
            return False, "Session locked"
        
        # ONS invalid
        if self.current_state == TradingState.ONS_INVALID:
            return False, "ONS filter failed"
        
        # Max trades reached
        if self.trades_taken_today >= self.max_trades_per_session:
            return False, f"Max trades reached ({self.max_trades_per_session})"
        
        # Not in a tradeable state
        if self.current_state not in [
            TradingState.AWAITING_DEVIATION,
            TradingState.AWAITING_SMT,
            TradingState.AWAITING_RECLAIM
        ]:
            return False, f"Not in tradeable state (current: {self.current_state.value})"
        
        return True, None
    
    def reset_for_new_session(self, session_date: datetime) -> None:
        """
        Reset state machine for a new trading session.
        
        Args:
            session_date: The date of the new session
        """
        self.current_state = TradingState.IDLE
        self.previous_state = None
        self.trades_taken_today = 0
        self.current_session_date = session_date
        self.context = {}
        
        print(f"\n🔄 State machine reset for session: {session_date.date()}")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get current state summary for logging.
        
        Returns:
            Dictionary with current state info
        """
        return {
            'current_state': self.current_state.value,
            'previous_state': self.previous_state.value if self.previous_state else None,
            'trades_taken': self.trades_taken_today,
            'max_trades': self.max_trades_per_session,
            'can_trade': self.can_trade()[0],
            'session_date': self.current_session_date,
            'total_transitions': len(self.state_history)
        }
    
    def get_transition_history(self) -> List[Dict[str, Any]]:
        """
        Get full history of state transitions.
        
        Returns:
            List of transition dictionaries
        """
        return [
            {
                'timestamp': t.timestamp.isoformat(),
                'from': t.from_state.value,
                'to': t.to_state.value,
                'reason': t.reason,
                'context': t.context
            }
            for t in self.state_history
        ]


# Example usage and testing
if __name__ == "__main__":
    from utils.config_loader import Config
    
    print("="*70)
    print("STATE MACHINE TESTING")
    print("="*70)
    print()
    
    # Initialize config
    Config.initialize()
    
    # Create state machine
    sm = StateMachine()
    
    print("Initial state:", sm.current_state.value)
    print()
    
    # Test valid transitions
    print("TEST 1: Valid Transition Flow")
    print("-" * 70)
    
    # Start session
    sm.transition_to(TradingState.SESSION_ACTIVE, "Session opened at 09:30 EST")
    
    # Start waiting for deviation
    sm.transition_to(TradingState.AWAITING_DEVIATION, "ONS valid, price below midnight")
    
    # Deviation detected
    sm.transition_to(TradingState.AWAITING_SMT, "Price swept below midnight open")
    
    # SMT confirmed
    sm.transition_to(TradingState.AWAITING_RECLAIM, "NQ swept, ES did not (SMT confirmed)")
    
    # Trade entered
    sm.transition_to(TradingState.IN_TRADE, "Reclaim candle triggered entry")
    
    # Trade exited
    sm.transition_to(TradingState.SESSION_LOCKED, "TP1 hit, session complete")
    
    print()
    
    # Test invalid transition
    print("TEST 2: Invalid Transition (should fail)")
    print("-" * 70)
    
    # Try to go from SESSION_LOCKED to IN_TRADE (invalid)
    result = sm.transition_to(TradingState.IN_TRADE, "Trying invalid transition")
    print(f"Transition result: {result}")
    print()
    
    # Test can_trade checks
    print("TEST 3: Trade Eligibility Checks")
    print("-" * 70)
    
    can_trade, reason = sm.can_trade()
    print(f"Can trade: {can_trade}")
    if not can_trade:
        print(f"Reason: {reason}")
    print()
    
    # Test session reset
    print("TEST 4: Session Reset")
    print("-" * 70)
    
    sm.reset_for_new_session(datetime.now())
    print(f"State after reset: {sm.current_state.value}")
    print(f"Trades taken: {sm.trades_taken_today}")
    print()
    
    # Show summary
    print("TEST 5: State Summary")
    print("-" * 70)
    
    summary = sm.get_state_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print()
    print("="*70)
    print("✅ STATE MACHINE TESTS COMPLETE")
    print("="*70)
