"""
Risk Management Module
======================
Handles position sizing, stop loss, take profit, and trailing stop logic.

Key concepts:
- Fixed R per trade (1R = initial risk)
- Position sizing based on account size and risk per trade
- Partial exits (50% at TP1, trail remainder)
- Trailing stops (move to breakeven after TP1)
- Account tracking

All risk calculations are in R-multiples for consistency.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from utils.config_loader import Config


@dataclass
class Position:
    """
    Represents an open trading position.
    """
    entry_price: float
    stop_loss: float
    initial_position_size: float  # In contracts
    current_position_size: float  # After partials
    
    tp1_price: float
    tp1_hit: bool = False
    
    # Risk tracking
    initial_risk_dollars: float = 0.0
    initial_risk_r: float = 1.0
    
    # Trailing stop
    trailing_stop: Optional[float] = None
    breakeven_active: bool = False
    
    # P&L tracking
    unrealized_pnl_dollars: float = 0.0
    unrealized_pnl_r: float = 0.0
    realized_pnl_dollars: float = 0.0
    realized_pnl_r: float = 0.0


class RiskManager:
    """
    Manages position sizing, stops, and profit targets.
    """
    
    def __init__(
        self,
        account_size: float = 100000.0,
        risk_per_trade_pct: float = 0.01,
        tp1_r_multiple: float = 1.0,
        partial_exit_pct: float = 0.50
    ):
        """
        Initialize risk manager.
        
        Args:
            account_size: Total account size in dollars
            risk_per_trade_pct: Risk per trade as % of account (e.g., 0.01 = 1%)
            tp1_r_multiple: First target in R-multiples (1.0 = 1R)
            partial_exit_pct: % of position to exit at TP1 (0.50 = 50%)
        """
        self.account_size = account_size
        self.risk_per_trade_pct = risk_per_trade_pct
        self.tp1_r_multiple = tp1_r_multiple
        self.partial_exit_pct = partial_exit_pct
        
        # Risk limits
        self.risk_per_trade_dollars = account_size * risk_per_trade_pct
        
        # Position tracking
        self.current_position: Optional[Position] = None
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl_dollars = 0.0
        self.total_pnl_r = 0.0
        
        print(f"💰 Risk Manager initialized")
        print(f"   Account size: ${account_size:,.2f}")
        print(f"   Risk per trade: {risk_per_trade_pct:.1%} (${self.risk_per_trade_dollars:,.2f})")
        print(f"   TP1 target: {tp1_r_multiple}R")
        print(f"   Partial exit: {partial_exit_pct:.0%}")
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        instrument_spec: Dict[str, Any]
    ) -> int:
        """
        Calculate position size based on risk.
        
        Formula:
        Position Size = Risk $ / (Entry - Stop) / Point Value
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            instrument_spec: Instrument specifications (point_value, tick_size, etc.)
        
        Returns:
            Number of contracts to trade
        """
        point_value = instrument_spec['point_value']
        tick_size = instrument_spec['tick_size']
        
        # Calculate risk per contract
        risk_per_point = abs(entry_price - stop_loss)
        risk_per_contract = risk_per_point * point_value
        
        if risk_per_contract == 0:
            return 0
        
        # Calculate position size
        position_size = self.risk_per_trade_dollars / risk_per_contract
        
        # Round down to whole contracts
        position_size = int(position_size)
        
        # Ensure at least 1 contract
        if position_size < 1:
            position_size = 1
        
        return position_size
    
    def open_position(
        self,
        entry_price: float,
        stop_loss: float,
        bias: str,
        instrument_spec: Dict[str, Any]
    ) -> Position:
        """
        Open a new position.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            bias: "LONG" or "SHORT"
            instrument_spec: Instrument specifications
        
        Returns:
            Position object
        """
        # Calculate position size
        position_size = self.calculate_position_size(
            entry_price,
            stop_loss,
            instrument_spec
        )
        
        # Calculate TP1
        risk_points = abs(entry_price - stop_loss)
        
        if bias == "LONG":
            tp1_price = entry_price + (risk_points * self.tp1_r_multiple)
        else:  # SHORT
            tp1_price = entry_price - (risk_points * self.tp1_r_multiple)
        
        # Calculate initial risk
        initial_risk_dollars = position_size * risk_points * instrument_spec['point_value']
        
        # Create position
        position = Position(
            entry_price=entry_price,
            stop_loss=stop_loss,
            initial_position_size=position_size,
            current_position_size=position_size,
            tp1_price=tp1_price,
            initial_risk_dollars=initial_risk_dollars,
            initial_risk_r=1.0
        )
        
        self.current_position = position
        
        print(f"\n📈 Position opened:")
        print(f"   Entry: {entry_price:.2f}")
        print(f"   Stop: {stop_loss:.2f}")
        print(f"   TP1: {tp1_price:.2f}")
        print(f"   Size: {position_size} contracts")
        print(f"   Risk: ${initial_risk_dollars:,.2f} ({self.risk_per_trade_pct:.1%})")
        
        return position
    
    def update_position(
        self,
        current_price: float,
        instrument_spec: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update position with current price and check for exits.
        
        Args:
            current_price: Current market price
            instrument_spec: Instrument specifications
        
        Returns:
            Exit signal dict if position should close, None otherwise
        """
        if self.current_position is None:
            return None
        
        pos = self.current_position
        point_value = instrument_spec['point_value']
        
        # Determine if LONG or SHORT
        is_long = pos.tp1_price > pos.entry_price
        
        # Check stop loss
        if is_long:
            if current_price <= pos.stop_loss:
                return self._close_position(
                    exit_price=pos.stop_loss,
                    reason='STOP_LOSS',
                    instrument_spec=instrument_spec
                )
        else:  # SHORT
            if current_price >= pos.stop_loss:
                return self._close_position(
                    exit_price=pos.stop_loss,
                    reason='STOP_LOSS',
                    instrument_spec=instrument_spec
                )
        
        # Check TP1 (partial exit)
        if not pos.tp1_hit:
            if is_long:
                if current_price >= pos.tp1_price:
                    return self._partial_exit_tp1(
                        exit_price=pos.tp1_price,
                        instrument_spec=instrument_spec
                    )
            else:  # SHORT
                if current_price <= pos.tp1_price:
                    return self._partial_exit_tp1(
                        exit_price=pos.tp1_price,
                        instrument_spec=instrument_spec
                    )
        
        # Check trailing stop (if TP1 hit)
        if pos.tp1_hit and pos.trailing_stop is not None:
            if is_long:
                if current_price <= pos.trailing_stop:
                    return self._close_position(
                        exit_price=pos.trailing_stop,
                        reason='TRAILING_STOP',
                        instrument_spec=instrument_spec
                    )
            else:  # SHORT
                if current_price >= pos.trailing_stop:
                    return self._close_position(
                        exit_price=pos.trailing_stop,
                        reason='TRAILING_STOP',
                        instrument_spec=instrument_spec
                    )
        
        # Update unrealized P&L
        self._update_unrealized_pnl(current_price, instrument_spec)
        
        return None
    
    def _partial_exit_tp1(
        self,
        exit_price: float,
        instrument_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute partial exit at TP1.
        
        Args:
            exit_price: Exit price (TP1)
            instrument_spec: Instrument specifications
        
        Returns:
            Partial exit signal dict
        """
        pos = self.current_position
        point_value = instrument_spec['point_value']
        
        # Calculate partial size
        partial_size = int(pos.initial_position_size * self.partial_exit_pct)
        
        if partial_size == 0:
            partial_size = 1  # At least 1 contract
        
        # Calculate P&L for partial
        is_long = pos.tp1_price > pos.entry_price
        
        if is_long:
            pnl_points = exit_price - pos.entry_price
        else:
            pnl_points = pos.entry_price - exit_price
        
        pnl_dollars = partial_size * pnl_points * point_value
        pnl_r = pnl_dollars / pos.initial_risk_dollars
        
        # Update position
        pos.tp1_hit = True
        pos.current_position_size = pos.initial_position_size - partial_size
        pos.realized_pnl_dollars += pnl_dollars
        pos.realized_pnl_r += pnl_r
        
        # Move stop to breakeven
        pos.trailing_stop = pos.entry_price
        pos.breakeven_active = True
        
        print(f"\n📊 Partial exit at TP1:")
        print(f"   Exit: {exit_price:.2f}")
        print(f"   Size: {partial_size} contracts ({self.partial_exit_pct:.0%})")
        print(f"   P&L: ${pnl_dollars:,.2f} ({pnl_r:.2f}R)")
        print(f"   Remaining: {pos.current_position_size} contracts")
        print(f"   Stop moved to breakeven: {pos.trailing_stop:.2f}")
        
        return {
            'type': 'PARTIAL_EXIT',
            'reason': 'TP1',
            'exit_price': exit_price,
            'contracts_closed': partial_size,
            'pnl_dollars': pnl_dollars,
            'pnl_r': pnl_r,
            'position_remains': True
        }
    
    def _close_position(
        self,
        exit_price: float,
        reason: str,
        instrument_spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Close entire position.
        
        Args:
            exit_price: Exit price
            reason: Exit reason
            instrument_spec: Instrument specifications
        
        Returns:
            Exit signal dict
        """
        pos = self.current_position
        point_value = instrument_spec['point_value']
        
        # Calculate P&L for remaining position
        is_long = pos.tp1_price > pos.entry_price
        
        if is_long:
            pnl_points = exit_price - pos.entry_price
        else:
            pnl_points = pos.entry_price - exit_price
        
        pnl_dollars = pos.current_position_size * pnl_points * point_value
        pnl_r = pnl_dollars / pos.initial_risk_dollars
        
        # Total P&L (including partials)
        total_pnl_dollars = pos.realized_pnl_dollars + pnl_dollars
        total_pnl_r = pos.realized_pnl_r + pnl_r
        
        # Update statistics
        self.total_trades += 1
        if total_pnl_r > 0:
            self.winning_trades += 1
        
        self.total_pnl_dollars += total_pnl_dollars
        self.total_pnl_r += total_pnl_r
        
        # Update account size
        self.account_size += total_pnl_dollars
        self.risk_per_trade_dollars = self.account_size * self.risk_per_trade_pct
        
        print(f"\n🔚 Position closed:")
        print(f"   Reason: {reason}")
        print(f"   Exit: {exit_price:.2f}")
        print(f"   Total P&L: ${total_pnl_dollars:,.2f} ({total_pnl_r:.2f}R)")
        print(f"   New account size: ${self.account_size:,.2f}")
        
        # Clear position
        self.current_position = None
        
        return {
            'type': 'FULL_EXIT',
            'reason': reason,
            'exit_price': exit_price,
            'pnl_dollars': total_pnl_dollars,
            'pnl_r': total_pnl_r,
            'win': total_pnl_r > 0,
            'position_remains': False
        }
    
    def _update_unrealized_pnl(
        self,
        current_price: float,
        instrument_spec: Dict[str, Any]
    ) -> None:
        """Update unrealized P&L."""
        pos = self.current_position
        point_value = instrument_spec['point_value']
        
        is_long = pos.tp1_price > pos.entry_price
        
        if is_long:
            pnl_points = current_price - pos.entry_price
        else:
            pnl_points = pos.entry_price - current_price
        
        pnl_dollars = pos.current_position_size * pnl_points * point_value
        pnl_r = pnl_dollars / pos.initial_risk_dollars
        
        pos.unrealized_pnl_dollars = pnl_dollars
        pos.unrealized_pnl_r = pnl_r
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance statistics.
        
        Returns:
            Dict with performance metrics
        """
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0
        avg_pnl_r = self.total_pnl_r / self.total_trades if self.total_trades > 0 else 0.0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.total_trades - self.winning_trades,
            'win_rate': win_rate,
            'total_pnl_dollars': self.total_pnl_dollars,
            'total_pnl_r': self.total_pnl_r,
            'avg_pnl_r': avg_pnl_r,
            'account_size': self.account_size,
            'account_growth_pct': (self.total_pnl_dollars / (self.account_size - self.total_pnl_dollars)) * 100
        }


# Example usage
if __name__ == "__main__":
    print("Risk Management module loaded successfully")
    print("Use RiskManager() to create an instance")
