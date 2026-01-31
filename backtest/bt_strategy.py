"""
Backtrader Strategy Implementation
===================================
Integrates v1.0 strategy with Backtrader framework for backtesting.

This wraps our strategy engine into Backtrader's interface so we can:
- Run on historical data
- Get performance metrics
- Analyze trades
- Validate v1.0 before live trading
"""

import backtrader as bt
from datetime import datetime, time
from typing import Dict, Any, List
import pandas as pd

from core.indicators import (
    MidnightOpenCalculator,
    ADRCalculator,
    ONSFilter,
    ISICalculator,
    SMTDetector
)
from core.state_machine import StateMachine
from core.risk_manager import RiskManager
from strategy_logging.schemas import TradingState
from utils.config_loader import Config
from utils.time_utils import TimeUtils


class MidnightReclaimStrategy(bt.Strategy):
    """
    Backtrader strategy for Multi-Confirmation False Breakout Reversal.
    
    This is a thin wrapper around our v1.0 strategy engine.
    """
    
    params = (
        ('account_size', 100000.0),
        ('risk_per_trade_pct', 0.01),
        ('tp1_r_multiple', 1.0),
        ('partial_exit_pct', 0.50),
        ('debug', False),
    )
    
    def __init__(self):
        """Initialize strategy with all components."""
        # Initialize config
        Config.initialize()
        
        # Get data feeds
        self.nq_data = self.datas[0]  # Primary (NQ)
        self.es_data = self.datas[1] if len(self.datas) > 1 else None  # Secondary (ES)
        
        # Core components
        self.state_machine = StateMachine()
        self.risk_manager = RiskManager(
            account_size=self.params.account_size,
            risk_per_trade_pct=self.params.risk_per_trade_pct,
            tp1_r_multiple=self.params.tp1_r_multiple,
            partial_exit_pct=self.params.partial_exit_pct
        )
        
        # Indicators
        self.mo_calc = MidnightOpenCalculator()
        self.adr_calc = ADRCalculator(lookback_days=20)
        self.ons_filter = ONSFilter(
            min_ratio=Config.get('ons', 'min_adr_ratio'),
            max_ratio=Config.get('ons', 'max_adr_ratio')
        )
        self.isi_calc = ISICalculator(
            threshold_min=Config.get('isi', 'threshold_min'),
            threshold_max=Config.get('isi', 'threshold_max')
        )
        self.smt_detector = SMTDetector()
        
        # Session tracking
        self.current_date: datetime = None
        self.session_started = False
        self.midnight_open: float = None
        self.adr: float = None
        self.bias: str = None
        
        # Deviation tracking
        self.deviation_detected = False
        self.deviation_time: datetime = None
        self.deviation_extreme: float = None
        self.deviation_bars: List[int] = []
        
        # Trade tracking
        self.trade_records: List[Dict[str, Any]] = []
        self.current_order = None
        
        # Instrument spec
        self.instrument_spec = Config.get_instrument_spec('NQ')
        
        # Config
        self.trading_window_start = Config.get('session', 'trading_window_start')
        self.trading_window_end = Config.get('session', 'trading_window_end')
        self.reclaim_time_limit = Config.get('reclaim', 'max_time_minutes')
        self.reclaim_body_ratio = Config.get('reclaim', 'min_body_ratio')
        
        if self.params.debug:
            print("="*70)
            print("BACKTEST STRATEGY INITIALIZED")
            print("="*70)
            print(f"Account size: ${self.params.account_size:,.2f}")
            print(f"Risk per trade: {self.params.risk_per_trade_pct:.1%}")
            print(f"Data feeds: NQ + {'ES' if self.es_data is not None else 'None'}")
            print("="*70)
    
    def next(self):
        """Called on each bar."""
        # Get current bar data
        current_date = self.nq_data.datetime.date()
        current_time = self.nq_data.datetime.datetime()
        current_price = self.nq_data.close[0]
        
        # Check for new session
        if self.current_date != current_date:
            self._new_session(current_date)
        
        # Skip if not in trading window
        if not self._in_trading_window(current_time):
            return
        
        # Start session if not started
        if not self.session_started:
            self._start_session()
        
        # Check if session is locked
        if self.state_machine.current_state == TradingState.SESSION_LOCKED:
            return
        
        # Update position if in trade
        if self.state_machine.current_state == TradingState.IN_TRADE:
            self._update_position(current_price)
            return
        
        # State: AWAITING_DEVIATION
        if self.state_machine.current_state == TradingState.AWAITING_DEVIATION:
            self._check_deviation(current_price, current_time)
        
        # State: AWAITING_SMT
        elif self.state_machine.current_state == TradingState.AWAITING_SMT:
            self._check_smt()
        
        # State: AWAITING_RECLAIM
        elif self.state_machine.current_state == TradingState.AWAITING_RECLAIM:
            self._check_reclaim(current_price, current_time)
    
    def notify_order(self, order):
        """Called when order status changes."""
        if order.status in [order.Completed]:
            if order.isbuy():
                if self.params.debug:
                    print(f"   BUY EXECUTED: {order.executed.price:.2f}")
            else:
                if self.params.debug:
                    print(f"   SELL EXECUTED: {order.executed.price:.2f}")
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if self.params.debug:
                print(f"   Order {order.status}")
        
        self.current_order = None
    
    def _new_session(self, new_date):
        """Handle new trading session."""
        self.current_date = new_date
        self.session_started = False
        self.midnight_open = None
        self.adr = None
        self.bias = None
        self.deviation_detected = False
        self.deviation_time = None
        self.deviation_extreme = None
        self.deviation_bars = []
        
        # Reset state machine
        self.state_machine.reset_for_new_session(datetime.combine(new_date, datetime.min.time()))
        
        if self.params.debug:
            print(f"\n{'='*70}")
            print(f"NEW SESSION: {new_date}")
            print(f"{'='*70}")
    
    def _start_session(self):
        """Start trading session."""
        self.session_started = True
        
        # Calculate midnight open
        try:
            # Convert backtrader data to pandas
            nq_df = self._get_dataframe(self.nq_data)
            
            self.midnight_open = self.mo_calc.calculate(nq_df, datetime.now())
            self.adr = self.adr_calc.calculate(nq_df, datetime.now())
            
            if self.params.debug:
                print(f"\n📍 Midnight Open: {self.midnight_open:.2f}")
                print(f"📊 ADR: {self.adr:.2f}")
            
        except Exception as e:
            if self.params.debug:
                print(f"❌ Session start failed: {e}")
            return
        
        # Validate ONS
        self.state_machine.transition_to(TradingState.SESSION_ACTIVE, "Session opened")
        
        try:
            nq_df = self._get_dataframe(self.nq_data)
            ons_result = self.ons_filter.validate(nq_df, datetime.now())
            
            if not ons_result['valid']:
                if self.params.debug:
                    print(f"❌ ONS Invalid: {ons_result['reason']}")
                
                self.state_machine.transition_to(TradingState.ONS_INVALID, ons_result['reason'])
                self.state_machine.transition_to(TradingState.SESSION_LOCKED, "ONS filter failed")
                return
            
            if self.params.debug:
                print(f"✅ ONS Valid: {ons_result['ratio']:.1%}")
            
        except Exception as e:
            if self.params.debug:
                print(f"❌ ONS validation failed: {e}")
            return
        
        # Determine bias
        current_price = self.nq_data.close[0]
        self.bias = "LONG" if current_price < self.midnight_open else "SHORT"
        
        if self.params.debug:
            print(f"🎯 Bias: {self.bias}")
        
        # Transition to awaiting deviation
        self.state_machine.transition_to(TradingState.AWAITING_DEVIATION, "Monitoring for deviation")
    
    def _check_deviation(self, current_price, current_time):
        """Check for deviation (sweep)."""
        if self.deviation_detected:
            return
        
        if self.bias == "LONG":
            if current_price < self.midnight_open:
                # Find lowest point in recent bars
                lookback = min(20, len(self.nq_data))
                lows = [self.nq_data.low[-i] for i in range(lookback)]
                
                self.deviation_extreme = min(lows)
                self.deviation_time = current_time
                self.deviation_detected = True
                
                if self.params.debug:
                    print(f"\n⚡ Deviation detected: {self.deviation_extreme:.2f}")
                
                self.state_machine.transition_to(TradingState.AWAITING_SMT, "Sweep detected")
        
        elif self.bias == "SHORT":
            if current_price > self.midnight_open:
                lookback = min(20, len(self.nq_data))
                highs = [self.nq_data.high[-i] for i in range(lookback)]
                
                self.deviation_extreme = max(highs)
                self.deviation_time = current_time
                self.deviation_detected = True
                
                if self.params.debug:
                    print(f"\n⚡ Deviation detected: {self.deviation_extreme:.2f}")
                
                self.state_machine.transition_to(TradingState.AWAITING_SMT, "Sweep detected")
    
    def _check_smt(self):
        """Check SMT confirmation."""
        # Simplified for backtesting
        # In production, would use proper SMT detection
        
        if self.params.debug:
            print(f"✅ SMT confirmed (simplified)")
        
        self.state_machine.transition_to(TradingState.AWAITING_RECLAIM, "SMT confirmed")
    
    def _check_reclaim(self, current_price, current_time):
        """Check for reclaim."""
        # Check timeout
        if self.deviation_time:
            elapsed = (current_time - self.deviation_time).total_seconds() / 60
            if elapsed > self.reclaim_time_limit:
                if self.params.debug:
                    print(f"⏰ Reclaim timeout")
                
                self.state_machine.transition_to(TradingState.SESSION_LOCKED, "Reclaim timeout")
                return
        
        # Check for reclaim
        current_bar = self.nq_data
        
        if self.bias == "LONG":
            if current_bar.close[0] > self.midnight_open and current_bar.close[0] > current_bar.open[0]:
                body = abs(current_bar.close[0] - current_bar.open[0])
                range_size = current_bar.high[0] - current_bar.low[0]
                
                if range_size > 0:
                    body_ratio = body / range_size
                    
                    if body_ratio >= self.reclaim_body_ratio:
                        self._enter_trade(current_bar.close[0])
        
        elif self.bias == "SHORT":
            if current_bar.close[0] < self.midnight_open and current_bar.close[0] < current_bar.open[0]:
                body = abs(current_bar.close[0] - current_bar.open[0])
                range_size = current_bar.high[0] - current_bar.low[0]
                
                if range_size > 0:
                    body_ratio = body / range_size
                    
                    if body_ratio >= self.reclaim_body_ratio:
                        self._enter_trade(current_bar.close[0])
    
    def _enter_trade(self, entry_price):
        """Enter trade."""
        if self.params.debug:
            print(f"\n🎯 Entering trade at {entry_price:.2f}")
        
        # Calculate stops
        if self.bias == "LONG":
            stop_loss = self.deviation_extreme - 2.0
        else:
            stop_loss = self.deviation_extreme + 2.0
        
        # Open position with risk manager
        position = self.risk_manager.open_position(
            entry_price=entry_price,
            stop_loss=stop_loss,
            bias=self.bias,
            instrument_spec=self.instrument_spec
        )
        
        # Place order
        if self.bias == "LONG":
            self.current_order = self.buy()
        else:
            self.current_order = self.sell()
        
        self.state_machine.transition_to(TradingState.IN_TRADE, "Trade entered")
    
    def _update_position(self, current_price):
        """Update open position."""
        result = self.risk_manager.update_position(
            current_price=current_price,
            instrument_spec=self.instrument_spec
        )
        
        if result:
            # Exit signal
            if self.bias == "LONG":
                self.current_order = self.sell()
            else:
                self.current_order = self.buy()
            
            if result['type'] == 'FULL_EXIT':
                self.state_machine.transition_to(
                    TradingState.SESSION_LOCKED,
                    f"Trade closed: {result['reason']}"
                )
                
                # Record trade
                self.trade_records.append({
                    'date': self.current_date,
                    'bias': self.bias,
                    'entry': self.risk_manager.current_position.entry_price if self.risk_manager.current_position else 0,
                    'exit': result['exit_price'],
                    'pnl_r': result['pnl_r'],
                    'win': result['win']
                })
    
    def _in_trading_window(self, current_time):
        """Check if in trading window."""
        return TimeUtils.is_in_trading_window(
            current_time,
            self.trading_window_start,
            self.trading_window_end
        )
    
    def _get_dataframe(self, data_feed) -> pd.DataFrame:
        """Convert backtrader data to pandas DataFrame."""
        # Get all available data
        data_list = []
        
        for i in range(len(data_feed)):
            idx = -i if i > 0 else 0
            data_list.append({
                'open': data_feed.open[idx],
                'high': data_feed.high[idx],
                'low': data_feed.low[idx],
                'close': data_feed.close[idx],
                'volume': data_feed.volume[idx],
            })
        
        # Reverse (oldest first)
        data_list.reverse()
        
        # Create DataFrame
        df = pd.DataFrame(data_list)
        
        # Add timestamps (simplified)
        df.index = pd.date_range(
            end=data_feed.datetime.datetime(),
            periods=len(df),
            freq='1min'
        )
        
        return df
    
    def stop(self):
        """Called when backtest ends."""
        if self.params.debug:
            print("\n" + "="*70)
            print("BACKTEST COMPLETE")
            print("="*70)
            
            stats = self.risk_manager.get_performance_summary()
            print(f"Total trades: {stats['total_trades']}")
            print(f"Winners: {stats['winning_trades']}")
            print(f"Losers: {stats['losing_trades']}")
            print(f"Win rate: {stats['win_rate']:.1f}%")
            print(f"Total P&L: ${stats['total_pnl_dollars']:,.2f}")
            print(f"Total R: {stats['total_pnl_r']:.2f}R")
            print(f"Final account: ${stats['account_size']:,.2f}")
            print("="*70)


if __name__ == "__main__":
    print("Backtrader strategy module loaded")
    print("Use with backtest_runner.py to run backtests")
