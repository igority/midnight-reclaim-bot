"""
Logging Schemas
===============
Data structures for event logs and trade logs.
Implements Agent 2's dual-logging architecture.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class TradingState(Enum):
    """Trading state machine states."""
    IDLE = "IDLE"
    SESSION_ACTIVE = "SESSION_ACTIVE"
    ONS_INVALID = "ONS_INVALID"
    AWAITING_DEVIATION = "AWAITING_DEVIATION"
    AWAITING_SMT = "AWAITING_SMT"
    AWAITING_RECLAIM = "AWAITING_RECLAIM"
    IN_TRADE = "IN_TRADE"
    SESSION_LOCKED = "SESSION_LOCKED"


class NoTradeReason(Enum):
    """Reasons for not taking a trade."""
    NONE = "NONE"  # Trade was taken
    ONS_INVALID = "ONS_INVALID"
    NO_DEVIATION = "NO_DEVIATION"
    NO_SMT = "NO_SMT"
    SMT_INVALIDATED = "SMT_INVALIDATED"
    NO_DISPLACEMENT = "NO_DISPLACEMENT"
    DISPLACEMENT_TOO_STRONG = "DISPLACEMENT_TOO_STRONG"
    NO_RECLAIM = "NO_RECLAIM"
    RECLAIM_TIMEOUT = "RECLAIM_TIMEOUT"
    RECLAIM_WEAK_BODY = "RECLAIM_WEAK_BODY"
    SESSION_LOCKED = "SESSION_LOCKED"
    OUTSIDE_TRADING_WINDOW = "OUTSIDE_TRADING_WINDOW"


@dataclass
class EventLog:
    """
    High-frequency event log.
    Logged at every state transition or significant market event.
    """
    # Timestamp
    timestamp: datetime
    
    # Instrument
    instrument: str
    
    # State
    state: TradingState
    
    # Price data
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    # Session context
    midnight_open: Optional[float] = None
    overnight_range: Optional[float] = None
    adr: Optional[float] = None
    ons_valid: Optional[bool] = None
    
    # Directional bias
    bias: Optional[str] = None  # "LONG", "SHORT", or None
    
    # SMT data (always logged, even if not using degree in v1.0)
    nq_sweep_depth: Optional[float] = None
    es_sweep_depth: Optional[float] = None
    nq_sweep_depth_norm: Optional[float] = None  # Normalized by ATR
    es_sweep_depth_norm: Optional[float] = None  # Normalized by ATR
    smt_binary: Optional[bool] = None
    smt_degree: Optional[float] = None  # Difference in normalized sweeps
    
    # Displacement (ISI)
    isi_value: Optional[float] = None
    displacement_detected: Optional[bool] = None
    
    # Reclaim tracking
    reclaim_active: Optional[bool] = None
    minutes_since_deviation: Optional[int] = None
    reclaim_body_ratio: Optional[float] = None
    
    # Regime tags (logged, not filtered in v1.0)
    regime_high_vol: Optional[bool] = None
    regime_trend_day: Optional[bool] = None
    regime_gap_day: Optional[bool] = None
    regime_news_day: Optional[bool] = None
    
    # Context
    vix_value: Optional[float] = None  # If available
    gap_size: Optional[float] = None  # Overnight gap %
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV writing."""
        d = asdict(self)
        # Convert enums to strings
        d['state'] = self.state.value if isinstance(self.state, TradingState) else self.state
        d['timestamp'] = self.timestamp.isoformat()
        return d


@dataclass
class TradeLog:
    """
    Trade log - one row per trade.
    Logged for both REAL trades and SHADOW trades (one-filter-failed).
    
    CRITICAL: Shadow trades are logged but NEVER affect live decisions.
    Shadow trades are analyzed ONLY after 50 real trades are completed.
    """
    # Trade identification
    trade_id: int
    timestamp_entry: datetime
    timestamp_exit: datetime
    
    # Instrument
    instrument: str
    
    # Trade type (CRITICAL DISTINCTION)
    trade_type: str  # "REAL" or "SHADOW"
    
    # Setup classification
    direction: str  # "LONG" or "SHORT"
    
    # Entry context
    midnight_open: float
    deviation_extreme: float  # The sweep low/high
    entry_price: float
    
    # SMT at entry
    smt_binary: bool
    smt_degree: float
    nq_sweep_depth_norm: float
    es_sweep_depth_norm: float
    
    # ISI at entry
    isi_value: float
    
    # Reclaim timing
    minutes_to_reclaim: int  # Minutes from deviation to reclaim
    reclaim_body_ratio: float
    
    # Risk parameters
    stop_loss: float
    tp1_price: float
    initial_risk_r: float
    
    # Exit details
    exit_price: float
    exit_reason: str  # "TP1", "TP2", "STOP", "BE", "TRAIL", "SESSION_CLOSE"
    
    # Performance
    pnl_points: float
    pnl_r: float  # R-multiples
    pnl_dollars: float
    win: bool
    
    # Session context
    overnight_range: float
    adr: float
    ons_ratio: float  # Overnight range / ADR
    
    # Regime tags
    regime_high_vol: bool
    regime_trend_day: bool
    regime_gap_day: bool
    regime_news_day: bool
    
    # Filter Analysis (for shadow trades)
    blocked_by_filter: Optional[str] = None  # Which filter blocked (if shadow)
    filters_passed: Optional[List[str]] = None  # List of filter names that passed
    filters_failed: Optional[List[str]] = None  # List of filter names that failed
    
    # Filter proximity (how close to passing?)
    smt_degree_threshold: Optional[float] = None  # What threshold was used
    isi_threshold_min: Optional[float] = None
    isi_threshold_max: Optional[float] = None
    reclaim_time_limit: Optional[int] = None
    
    # Execution reality (for REAL trades only)
    broker_time: Optional[datetime] = None  # MT5 server time
    server_time: Optional[datetime] = None  # VPS time
    spread_at_entry: Optional[float] = None  # Spread in points/ticks
    slippage_ticks: Optional[float] = None  # Actual vs intended fill
    
    # Version tracking
    strategy_version: str = "1.0"
    config_hash: Optional[str] = None  # Hash of config at trade time
    
    # Additional context
    vix_value: Optional[float] = None
    gap_size: Optional[float] = None
    
    # Trade notes
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV writing."""
        d = asdict(self)
        d['timestamp_entry'] = self.timestamp_entry.isoformat()
        d['timestamp_exit'] = self.timestamp_exit.isoformat()
        return d


@dataclass
class NoTradeLog:
    """
    No-trade log - tracks when conditions were evaluated but no trade taken.
    Critical for understanding filter effectiveness.
    """
    # Timestamp
    timestamp: datetime
    
    # Instrument
    instrument: str
    
    # Reason for rejection
    rejection_reason: NoTradeReason
    
    # Context at rejection
    state_at_rejection: TradingState
    midnight_open: float
    current_price: float
    
    # What was present/missing
    ons_valid: Optional[bool] = None
    smt_present: Optional[bool] = None
    displacement_ok: Optional[bool] = None
    reclaim_detected: Optional[bool] = None
    
    # Detailed reason data
    isi_value: Optional[float] = None
    minutes_elapsed: Optional[int] = None
    body_ratio: Optional[float] = None
    
    # Session context
    overnight_range: Optional[float] = None
    adr: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV writing."""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        d['rejection_reason'] = self.rejection_reason.value
        d['state_at_rejection'] = self.state_at_rejection.value
        return d


# Example usage
if __name__ == "__main__":
    from datetime import datetime
    
    # Create an event log entry
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
    
    print("Event Log:")
    print(event.to_dict())
    print()
    
    # Create a trade log entry
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
    
    print("Trade Log:")
    print(trade.to_dict())
