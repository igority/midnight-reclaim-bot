"""
Logger Implementation
=====================
Handles writing of event logs, trade logs, and no-trade logs.
Implements Agent 2's dual-logging architecture with CSV output.
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from .schemas import EventLog, TradeLog, NoTradeLog


class Logger:
    """
    Manages logging for the trading system.
    Writes to CSV files with automatic directory creation.
    """
    
    def __init__(
        self,
        event_log_path: str = "logs/events",
        trade_log_path: str = "logs/trades",
        no_trade_log_path: str = "logs/no_trades"
    ):
        self.event_log_path = Path(event_log_path)
        self.trade_log_path = Path(trade_log_path)
        self.no_trade_log_path = Path(no_trade_log_path)
        
        # Create directories
        self.event_log_path.mkdir(parents=True, exist_ok=True)
        self.trade_log_path.mkdir(parents=True, exist_ok=True)
        self.no_trade_log_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize log files
        self.event_log_file = self._get_log_filename("events")
        self.trade_log_file = self._get_log_filename("trades")
        self.no_trade_log_file = self._get_log_filename("no_trades")
        
        # Track if headers written
        self._event_headers_written = False
        self._trade_headers_written = False
        self._no_trade_headers_written = False
        
        print(f"📋 Logger initialized:")
        print(f"   Events: {self.event_log_file}")
        print(f"   Trades: {self.trade_log_file}")
        print(f"   No-Trades: {self.no_trade_log_file}\n")
    
    def _get_log_filename(self, log_type: str) -> Path:
        """Generate dated log filename."""
        date_str = datetime.now().strftime("%Y%m%d")
        
        if log_type == "events":
            return self.event_log_path / f"events_{date_str}.csv"
        elif log_type == "trades":
            return self.trade_log_path / f"trades_{date_str}.csv"
        elif log_type == "no_trades":
            return self.no_trade_log_path / f"no_trades_{date_str}.csv"
        else:
            raise ValueError(f"Unknown log type: {log_type}")
    
    def log_event(self, event: EventLog) -> None:
        """
        Log an event to the high-frequency event log.
        
        Args:
            event: EventLog instance
        """
        event_dict = event.to_dict()
        
        with open(self.event_log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=event_dict.keys())
            
            # Write headers if first time
            if not self._event_headers_written:
                writer.writeheader()
                self._event_headers_written = True
            
            writer.writerow(event_dict)
    
    def log_trade(self, trade: TradeLog) -> None:
        """
        Log a completed trade (REAL or SHADOW).
        
        Args:
            trade: TradeLog instance
        """
        trade_dict = trade.to_dict()
        
        with open(self.trade_log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=trade_dict.keys())
            
            # Write headers if first time
            if not self._trade_headers_written:
                writer.writeheader()
                self._trade_headers_written = True
            
            writer.writerow(trade_dict)
        
        # Print summary (different for REAL vs SHADOW)
        if trade.trade_type == "REAL":
            win_label = "✅ WIN" if trade.win else "❌ LOSS"
            print(f"\n{win_label} Trade #{trade.trade_id} logged:")
            print(f"   {trade.direction} @ {trade.entry_price} → {trade.exit_price}")
            print(f"   R: {trade.pnl_r:.2f} | P&L: ${trade.pnl_dollars:.2f}")
            print(f"   Exit: {trade.exit_reason}\n")
        
        elif trade.trade_type == "SHADOW":
            win_label = "✅" if trade.win else "❌"
            print(f"\n👻 SHADOW Trade #{trade.trade_id} logged:")
            print(f"   Blocked by: {trade.blocked_by_filter}")
            print(f"   Would have: {win_label} {trade.direction} @ {trade.entry_price} → {trade.exit_price}")
            print(f"   Virtual R: {trade.pnl_r:.2f}")
            print(f"   ⚠️  DO NOT review until 50 REAL trades completed\n")
    
    def log_no_trade(self, no_trade: NoTradeLog) -> None:
        """
        Log a rejected trade setup.
        
        Args:
            no_trade: NoTradeLog instance
        """
        no_trade_dict = no_trade.to_dict()
        
        with open(self.no_trade_log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=no_trade_dict.keys())
            
            # Write headers if first time
            if not self._no_trade_headers_written:
                writer.writeheader()
                self._no_trade_headers_written = True
            
            writer.writerow(no_trade_dict)
    
    def log_session_summary(self, summary: Dict[str, Any]) -> None:
        """
        Log end-of-session summary.
        
        Args:
            summary: Dictionary with session statistics
        """
        print("\n" + "="*60)
        print("SESSION SUMMARY")
        print("="*60)
        
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        print("="*60 + "\n")


class LogReader:
    """
    Reads and analyzes log files.
    Useful for post-session analysis and v1.5 evolution decisions.
    """
    
    def __init__(self, log_directory: str = "logs"):
        self.log_dir = Path(log_directory)
    
    def read_events(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Read event log for a given date.
        
        Args:
            date: Date string in YYYYMMDD format (default: today)
            
        Returns:
            List of event dictionaries
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        
        filepath = self.log_dir / "events" / f"events_{date}.csv"
        
        if not filepath.exists():
            return []
        
        events = []
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            events = list(reader)
        
        return events
    
    def read_trades(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Read trade log for a given date.
        
        Args:
            date: Date string in YYYYMMDD format (default: today)
            
        Returns:
            List of trade dictionaries
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        
        filepath = self.log_dir / "trades" / f"trades_{date}.csv"
        
        if not filepath.exists():
            return []
        
        trades = []
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            trades = list(reader)
        
        return trades
    
    def read_no_trades(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Read no-trade log for a given date.
        
        Args:
            date: Date string in YYYYMMDD format (default: today)
            
        Returns:
            List of no-trade dictionaries
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        
        filepath = self.log_dir / "no_trades" / f"no_trades_{date}.csv"
        
        if not filepath.exists():
            return []
        
        no_trades = []
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            no_trades = list(reader)
        
        return no_trades
    
    def analyze_rejection_reasons(self, days: int = 30) -> Dict[str, int]:
        """
        Analyze frequency of rejection reasons over last N days.
        Critical for v1.5 evolution decisions.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary of rejection_reason -> count
        """
        # TODO: Implement multi-day analysis
        # For now, just today
        no_trades = self.read_no_trades()
        
        reasons = {}
        for nt in no_trades:
            reason = nt.get('rejection_reason', 'UNKNOWN')
            reasons[reason] = reasons.get(reason, 0) + 1
        
        return reasons


# Example usage
if __name__ == "__main__":
    from .schemas import EventLog, TradeLog, TradingState
    
    # Initialize logger
    logger = Logger()
    
    # Log an event
    event = EventLog(
        timestamp=datetime.now(),
        instrument="NQ",
        state=TradingState.AWAITING_RECLAIM,
        open=17500.0,
        high=17520.0,
        low=17495.0,
        close=17510.0,
        volume=1000,
        midnight_open=17550.0
    )
    logger.log_event(event)
    print("✅ Event logged")
    
    # Read back
    reader = LogReader()
    events = reader.read_events()
    print(f"📖 Read {len(events)} events from today's log")
