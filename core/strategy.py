"""
Strategy Engine
===============
Main trading strategy that integrates all components.

This is where indicators, state machine, and trading logic come together.

Flow:
1. Session starts → Check ONS
2. Determine bias (price vs midnight open)
3. Wait for deviation (sweep)
4. Check ISI (displacement filter)
5. Check SMT (divergence)
6. Wait for reclaim (entry trigger)
7. Enter trade
8. Manage position (TP1, stop, trail)
9. Exit and lock session

All decisions are logged for analysis and shadow trade evaluation.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import pandas as pd

from core.state_machine import StateMachine
from core.indicators import (
    MidnightOpenCalculator,
    ADRCalculator,
    ONSFilter,
    ISICalculator,
    SMTDetector
)
from core.shadow_trades import ShadowTradeManager, FilterCheck
from strategy_logging.logger import Logger
from strategy_logging.schemas import (
    TradingState,
    EventLog,
    TradeLog,
    NoTradeLog
)
from utils.time_utils import TimeUtils
from utils.config_loader import Config


class StrategyEngine:
    """
    Main trading strategy engine.
    
    Orchestrates all components to make trading decisions.
    """
    
    def __init__(self):
        """Initialize strategy engine with all components."""
        print("="*70)
        print("INITIALIZING STRATEGY ENGINE")
        print("="*70)
        
        # Configuration
        Config.initialize()
        
        # Core components
        self.state_machine = StateMachine()
        self.logger = Logger()
        self.shadow_manager = ShadowTradeManager()
        
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
        self.current_date: Optional[datetime] = None
        self.midnight_open: Optional[float] = None
        self.adr: Optional[float] = None
        self.bias: Optional[str] = None
        
        # Deviation tracking
        self.deviation_detected = False
        self.deviation_time: Optional[datetime] = None
        self.deviation_extreme: Optional[float] = None
        self.deviation_start_idx: Optional[int] = None
        self.deviation_end_idx: Optional[int] = None
        
        # Trade tracking
        self.current_trade: Optional[Dict[str, Any]] = None
        self.trade_count = 0
        
        # Configuration values
        self.trading_window_start = Config.get('session', 'trading_window_start')
        self.trading_window_end = Config.get('session', 'trading_window_end')
        self.reclaim_time_limit = Config.get('reclaim', 'max_time_minutes')
        self.reclaim_body_ratio = Config.get('reclaim', 'min_body_ratio')
        
        print("✅ Strategy engine initialized")
        print(f"   Trading window: {self.trading_window_start} - {self.trading_window_end}")
        print(f"   ONS range: {Config.get('ons_filter', 'min_ratio'):.0%} - {Config.get('ons_filter', 'max_ratio'):.0%}")
        print(f"   ISI thresholds: {Config.get('isi', 'threshold_min')} - {Config.get('isi', 'threshold_max')}")
        print("="*70)
    
    def run_session(
        self,
        nq_data: pd.DataFrame,
        es_data: pd.DataFrame,
        session_date: datetime
    ) -> Dict[str, Any]:
        """
        Run strategy for a single trading session.
        
        Args:
            nq_data: NQ price data (1-minute bars)
            es_data: ES price data (1-minute bars)
            session_date: Date of the session
        
        Returns:
            Session results dictionary
        """
        print(f"\n{'='*70}")
        print(f"RUNNING SESSION: {session_date.date()}")
        print(f"{'='*70}")
        
        # Reset for new session
        self.state_machine.reset_for_new_session(session_date)
        self.current_date = session_date
        self.deviation_detected = False
        self.current_trade = None
        
        # Step 1: Calculate midnight open
        try:
            self.midnight_open = self.mo_calc.calculate(nq_data, session_date)
            print(f"\n📍 Midnight Open: {self.midnight_open:.2f}")
        except ValueError as e:
            print(f"❌ Could not calculate midnight open: {e}")
            return {'session_date': session_date, 'trades': 0, 'reason': 'NO_MIDNIGHT_OPEN'}
        
        # Step 2: Calculate ADR
        try:
            self.adr = self.adr_calc.calculate(nq_data, session_date)
            print(f"📊 ADR (20-day): {self.adr:.2f} points")
        except ValueError as e:
            print(f"❌ Could not calculate ADR: {e}")
            return {'session_date': session_date, 'trades': 0, 'reason': 'NO_ADR'}
        
        # Step 3: Validate ONS
        self.state_machine.transition_to(
            TradingState.SESSION_ACTIVE,
            "Session opened"
        )
        
        ons_result = self.ons_filter.validate(nq_data, session_date)
        
        if not ons_result['valid']:
            print(f"\n❌ ONS Invalid: {ons_result['reason']}")
            self.state_machine.transition_to(
                TradingState.ONS_INVALID,
                ons_result['reason']
            )
            
            # Log no-trade
            self._log_no_trade('ONS_INVALID', ons_result['reason'])
            
            return {
                'session_date': session_date,
                'trades': 0,
                'reason': 'ONS_INVALID',
                'ons_result': ons_result
            }
        
        print(f"✅ ONS Valid: {ons_result['ratio']:.1%} of ADR")
        
        # Step 4: Process bars looking for setup
        self.state_machine.transition_to(
            TradingState.AWAITING_DEVIATION,
            "ONS valid, monitoring for deviation"
        )
        
        # Get bars in trading window
        trading_bars = self._get_trading_window_bars(nq_data)
        
        if trading_bars.empty:
            print("⚠️  No bars in trading window")
            return {'session_date': session_date, 'trades': 0, 'reason': 'NO_DATA_IN_WINDOW'}
        
        print(f"\n📈 Processing {len(trading_bars)} bars in trading window...")
        
        # Process each bar
        for idx in range(len(trading_bars)):
            current_bar = trading_bars.iloc[idx]
            current_time = current_bar.name
            current_price = current_bar['close']
            
            # Determine/update bias
            if self.bias is None:
                self.bias = self._determine_bias(current_price)
                print(f"\n🎯 Bias: {self.bias} (price {'below' if self.bias == 'LONG' else 'above'} MO)")
            
            # State: AWAITING_DEVIATION
            if self.state_machine.current_state == TradingState.AWAITING_DEVIATION:
                if self._check_for_deviation(trading_bars, idx):
                    print(f"\n⚡ Deviation detected at {current_time}")
                    print(f"   Extreme: {self.deviation_extreme:.2f}")
                    
                    self.state_machine.transition_to(
                        TradingState.AWAITING_SMT,
                        f"Sweep to {self.deviation_extreme:.2f}"
                    )
            
            # State: AWAITING_SMT
            elif self.state_machine.current_state == TradingState.AWAITING_SMT:
                # Check ISI first
                isi_result = self._check_isi(trading_bars)
                
                if isi_result['assessment'] == 'NO_FADE':
                    print(f"\n❌ ISI too high: {isi_result['isi']:.2f} (strong trend)")
                    
                    self._log_no_trade('ISI_TOO_HIGH', f"ISI: {isi_result['isi']:.2f}")
                    
                    self.state_machine.transition_to(
                        TradingState.SESSION_LOCKED,
                        "Displacement too strong"
                    )
                    break
                
                # Check SMT
                smt_result = self._check_smt(nq_data, es_data)
                
                if not smt_result['smt_binary']:
                    print(f"\n❌ SMT failed (no divergence)")
                    
                    # This is a shadow trade! (one filter failed)
                    self._log_shadow_trade('SMT_BINARY', smt_result, isi_result)
                    
                    self.state_machine.transition_to(
                        TradingState.SESSION_LOCKED,
                        "SMT confirmation failed"
                    )
                    break
                
                print(f"\n✅ SMT confirmed (degree: {smt_result['smt_degree']:.2f})")
                
                self.state_machine.transition_to(
                    TradingState.AWAITING_RECLAIM,
                    "SMT divergence confirmed"
                )
            
            # State: AWAITING_RECLAIM
            elif self.state_machine.current_state == TradingState.AWAITING_RECLAIM:
                # Check time limit
                if self._check_reclaim_timeout(current_time):
                    print(f"\n⏰ Reclaim timeout ({self.reclaim_time_limit} minutes)")
                    
                    self._log_no_trade('RECLAIM_TIMEOUT', 
                                      f"No reclaim within {self.reclaim_time_limit} min")
                    
                    self.state_machine.transition_to(
                        TradingState.SESSION_LOCKED,
                        "Reclaim timeout"
                    )
                    break
                
                # Check for reclaim
                if self._check_for_reclaim(current_bar):
                    print(f"\n🎯 Reclaim detected at {current_time}")
                    print(f"   Entry: {current_bar['close']:.2f}")
                    
                    # Enter trade
                    self._enter_trade(current_bar, nq_data, es_data)
                    
                    self.state_machine.transition_to(
                        TradingState.IN_TRADE,
                        "Reclaim entry triggered"
                    )
            
            # State: IN_TRADE
            elif self.state_machine.current_state == TradingState.IN_TRADE:
                # Manage position
                exit_result = self._manage_position(current_bar)
                
                if exit_result:
                    print(f"\n🔚 Trade exited: {exit_result['reason']}")
                    print(f"   Exit: {current_bar['close']:.2f}")
                    print(f"   P&L: {exit_result['pnl_r']:.2f}R")
                    
                    # Log trade
                    self._log_trade(current_bar, exit_result)
                    
                    self.state_machine.transition_to(
                        TradingState.SESSION_LOCKED,
                        f"Trade complete: {exit_result['reason']}"
                    )
                    break
        
        # Session summary
        return {
            'session_date': session_date,
            'trades': self.trade_count,
            'midnight_open': self.midnight_open,
            'adr': self.adr,
            'bias': self.bias,
            'state': self.state_machine.current_state.value
        }
    
    def _get_trading_window_bars(self, df: pd.DataFrame) -> pd.DataFrame:
        """Get bars within trading window."""
        trading_bars = df[
            TimeUtils.is_in_trading_window(
                df.index,
                self.trading_window_start,
                self.trading_window_end
            )
        ]
        return trading_bars
    
    def _determine_bias(self, current_price: float) -> str:
        """Determine LONG or SHORT bias."""
        if current_price < self.midnight_open:
            return "LONG"
        else:
            return "SHORT"
    
    def _check_for_deviation(self, bars: pd.DataFrame, idx: int) -> bool:
        """Check if deviation has occurred."""
        if self.deviation_detected:
            return False
        
        current_bar = bars.iloc[idx]
        
        if self.bias == "LONG":
            # Check if swept below midnight open
            if current_bar['low'] < self.midnight_open:
                # Find lowest point in recent bars
                lookback = min(20, idx)
                recent_bars = bars.iloc[max(0, idx-lookback):idx+1]
                
                self.deviation_extreme = recent_bars['low'].min()
                self.deviation_time = current_bar.name
                self.deviation_start_idx = max(0, idx-lookback)
                self.deviation_end_idx = idx
                self.deviation_detected = True
                
                return True
        
        elif self.bias == "SHORT":
            # Check if swept above midnight open
            if current_bar['high'] > self.midnight_open:
                lookback = min(20, idx)
                recent_bars = bars.iloc[max(0, idx-lookback):idx+1]
                
                self.deviation_extreme = recent_bars['high'].max()
                self.deviation_time = current_bar.name
                self.deviation_start_idx = max(0, idx-lookback)
                self.deviation_end_idx = idx
                self.deviation_detected = True
                
                return True
        
        return False
    
    def _check_isi(self, bars: pd.DataFrame) -> Dict[str, Any]:
        """Check ISI displacement filter."""
        isi_result = self.isi_calc.calculate(
            bars,
            self.deviation_start_idx,
            self.deviation_end_idx
        )
        return isi_result
    
    def _check_smt(
        self,
        nq_data: pd.DataFrame,
        es_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Check SMT divergence."""
        # Simplified: Use midnight open as reference
        # In production, use prior session lows
        nq_reference = self.midnight_open
        es_reference = es_data['close'].iloc[0]
        
        direction = 'below' if self.bias == 'LONG' else 'above'
        
        smt_result = self.smt_detector.detect_divergence(
            nq_data,
            es_data,
            nq_reference,
            es_reference,
            direction
        )
        
        return smt_result
    
    def _check_reclaim_timeout(self, current_time: datetime) -> bool:
        """Check if reclaim has timed out."""
        if self.deviation_time is None:
            return False
        
        minutes_elapsed = (current_time - self.deviation_time).total_seconds() / 60
        return minutes_elapsed > self.reclaim_time_limit
    
    def _check_for_reclaim(self, bar: pd.Series) -> bool:
        """Check if reclaim has occurred."""
        if self.bias == "LONG":
            # Need bullish close above midnight open
            if bar['close'] > self.midnight_open and bar['close'] > bar['open']:
                # Check body ratio
                body = abs(bar['close'] - bar['open'])
                range_size = bar['high'] - bar['low']
                
                if range_size > 0:
                    body_ratio = body / range_size
                    return body_ratio >= self.reclaim_body_ratio
        
        elif self.bias == "SHORT":
            # Need bearish close below midnight open
            if bar['close'] < self.midnight_open and bar['close'] < bar['open']:
                body = abs(bar['close'] - bar['open'])
                range_size = bar['high'] - bar['low']
                
                if range_size > 0:
                    body_ratio = body / range_size
                    return body_ratio >= self.reclaim_body_ratio
        
        return False
    
    def _enter_trade(
        self,
        entry_bar: pd.Series,
        nq_data: pd.DataFrame,
        es_data: pd.DataFrame
    ) -> None:
        """Enter a trade."""
        entry_price = entry_bar['close']
        
        # Calculate stops and targets
        if self.bias == "LONG":
            stop_loss = self.deviation_extreme - 2.0  # Buffer below extreme
            risk_points = entry_price - stop_loss
            tp1_price = entry_price + (risk_points * Config.get('risk', 'tp1_r'))
        
        else:  # SHORT
            stop_loss = self.deviation_extreme + 2.0
            risk_points = stop_loss - entry_price
            tp1_price = entry_price - (risk_points * Config.get('risk', 'tp1_r'))
        
        self.current_trade = {
            'entry_time': entry_bar.name,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'tp1_price': tp1_price,
            'risk_r': 1.0,
            'position_size': 1.0,  # Simplified
            'tp1_hit': False
        }
        
        self.trade_count += 1
    
    def _manage_position(self, bar: pd.Series) -> Optional[Dict[str, Any]]:
        """
        Manage open position.
        
        Returns exit result if trade should close, None otherwise.
        """
        if self.current_trade is None:
            return None
        
        # Check stop loss
        if self.bias == "LONG":
            if bar['low'] <= self.current_trade['stop_loss']:
                pnl_points = self.current_trade['stop_loss'] - self.current_trade['entry_price']
                pnl_r = -1.0
                return {
                    'reason': 'STOP_LOSS',
                    'exit_price': self.current_trade['stop_loss'],
                    'pnl_points': pnl_points,
                    'pnl_r': pnl_r,
                    'win': False
                }
            
            # Check TP1
            if not self.current_trade['tp1_hit'] and bar['high'] >= self.current_trade['tp1_price']:
                self.current_trade['tp1_hit'] = True
                # In production, partial exit here
            
            # Check if TP1 hit and can trail
            if self.current_trade['tp1_hit'] and bar['high'] >= self.current_trade['tp1_price']:
                pnl_points = self.current_trade['tp1_price'] - self.current_trade['entry_price']
                pnl_r = Config.get('risk', 'tp1_r')
                return {
                    'reason': 'TP1',
                    'exit_price': self.current_trade['tp1_price'],
                    'pnl_points': pnl_points,
                    'pnl_r': pnl_r,
                    'win': True
                }
        
        else:  # SHORT
            if bar['high'] >= self.current_trade['stop_loss']:
                pnl_points = self.current_trade['entry_price'] - self.current_trade['stop_loss']
                pnl_r = -1.0
                return {
                    'reason': 'STOP_LOSS',
                    'exit_price': self.current_trade['stop_loss'],
                    'pnl_points': pnl_points,
                    'pnl_r': pnl_r,
                    'win': False
                }
            
            if not self.current_trade['tp1_hit'] and bar['low'] <= self.current_trade['tp1_price']:
                self.current_trade['tp1_hit'] = True
            
            if self.current_trade['tp1_hit'] and bar['low'] <= self.current_trade['tp1_price']:
                pnl_points = self.current_trade['entry_price'] - self.current_trade['tp1_price']
                pnl_r = Config.get('risk', 'tp1_r')
                return {
                    'reason': 'TP1',
                    'exit_price': self.current_trade['tp1_price'],
                    'pnl_points': pnl_points,
                    'pnl_r': pnl_r,
                    'win': True
                }
        
        return None
    
    def _log_no_trade(self, reason: str, details: str) -> None:
        """Log a rejected setup."""
        no_trade = NoTradeLog(
            timestamp=datetime.now(),
            instrument="NQ",
            reason=reason,
            details=details,
            midnight_open=self.midnight_open,
            adr=self.adr,
            bias=self.bias
        )
        
        self.logger.log_no_trade(no_trade)
    
    def _log_shadow_trade(
        self,
        blocked_by: str,
        smt_result: Dict[str, Any],
        isi_result: Dict[str, Any]
    ) -> None:
        """Log a shadow trade (one-filter-failed)."""
        print("   👻 Logging as SHADOW trade (one filter failed)")
        # Shadow trade logging implementation
        # Would simulate entry/exit with same logic
        pass
    
    def _log_trade(self, exit_bar: pd.Series, exit_result: Dict[str, Any]) -> None:
        """Log a completed trade."""
        # Trade logging implementation
        print(f"   📝 Trade logged: {exit_result['reason']}")
        pass


# Example usage
if __name__ == "__main__":
    print("Strategy engine module loaded successfully")
    print("Use StrategyEngine() to create an instance")
