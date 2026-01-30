"""
MT5 Communication Interface
============================
File-based IPC between Python strategy engine and MT5 EA.

Architecture:
- Python writes trade signals to files
- MT5 EA reads files and executes
- MT5 EA writes execution reports back
- Python reads reports and logs

Simple, robust, debuggable. Perfect for v1.0.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
import time


@dataclass
class TradeSignal:
    """
    Trade signal from Python to MT5.
    """
    signal_id: str  # Unique ID for this signal
    timestamp: datetime
    
    # Trade parameters
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: Optional[float]  # None = market order
    stop_loss: float
    take_profit_1: float  # TP1
    take_profit_2: Optional[float] = None  # TP2 (runner target)
    
    # Position sizing
    risk_r: float = 1.0
    position_percent_tp1: float = 50  # % to close at TP1
    
    # Metadata
    strategy_version: str = "1.0"
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d


@dataclass
class ExecutionReport:
    """
    Execution report from MT5 to Python.
    """
    signal_id: str  # Links back to TradeSignal
    execution_id: str  # MT5 order ticket
    timestamp: datetime
    
    # Execution details
    symbol: str
    direction: str
    entry_price: float  # Actual fill price
    stop_loss: float
    take_profit: float
    
    # Execution quality
    requested_price: Optional[float]
    slippage_ticks: float
    spread_at_entry: float  # Points/ticks
    broker_time: datetime  # MT5 server time
    
    # Status
    status: str  # "FILLED", "REJECTED", "PARTIAL"
    rejection_reason: Optional[str] = None
    
    # Metadata
    notes: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ExecutionReport':
        """Create from dictionary."""
        d['timestamp'] = datetime.fromisoformat(d['timestamp'])
        d['broker_time'] = datetime.fromisoformat(d['broker_time'])
        return cls(**d)


class MT5Interface:
    """
    Manages file-based communication with MT5.
    """
    
    def __init__(
        self,
        signals_dir: str = "mt5_comm/signals",
        reports_dir: str = "mt5_comm/reports",
        archive_dir: str = "mt5_comm/archive"
    ):
        """
        Initialize MT5 interface.
        
        Args:
            signals_dir: Directory where Python writes signals
            reports_dir: Directory where MT5 writes reports
            archive_dir: Directory for processed files
        """
        self.signals_dir = Path(signals_dir)
        self.reports_dir = Path(reports_dir)
        self.archive_dir = Path(archive_dir)
        
        # Create directories
        self.signals_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📡 MT5 Interface initialized:")
        print(f"   Signals: {self.signals_dir}")
        print(f"   Reports: {self.reports_dir}")
        print(f"   Archive: {self.archive_dir}")
    
    def send_signal(self, signal: TradeSignal) -> None:
        """
        Send trade signal to MT5.
        
        Args:
            signal: TradeSignal to send
        """
        filename = f"signal_{signal.signal_id}.json"
        filepath = self.signals_dir / filename
        
        # Write signal to file
        with open(filepath, 'w') as f:
            json.dump(signal.to_dict(), f, indent=2)
        
        print(f"📤 Signal sent: {signal.signal_id}")
        print(f"   {signal.direction} {signal.symbol} @ {signal.entry_price}")
    
    def check_for_reports(self) -> list[ExecutionReport]:
        """
        Check for execution reports from MT5.
        
        Returns:
            List of new ExecutionReport objects
        """
        reports = []
        
        # Look for JSON files in reports directory
        for filepath in self.reports_dir.glob("report_*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                report = ExecutionReport.from_dict(data)
                reports.append(report)
                
                # Move to archive
                archive_path = self.archive_dir / filepath.name
                filepath.rename(archive_path)
                
                print(f"📥 Report received: {report.signal_id}")
                print(f"   Status: {report.status}")
                
            except Exception as e:
                print(f"⚠️  Error reading report {filepath}: {e}")
        
        return reports
    
    def wait_for_execution(
        self,
        signal_id: str,
        timeout: int = 30
    ) -> Optional[ExecutionReport]:
        """
        Wait for execution report for a specific signal.
        
        Args:
            signal_id: Signal ID to wait for
            timeout: Timeout in seconds
        
        Returns:
            ExecutionReport if received, None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            reports = self.check_for_reports()
            
            for report in reports:
                if report.signal_id == signal_id:
                    return report
            
            # Check every 0.5 seconds
            time.sleep(0.5)
        
        print(f"⏱️  Timeout waiting for execution of {signal_id}")
        return None
    
    def cleanup_old_files(self, days: int = 7) -> None:
        """
        Clean up old archived files.
        
        Args:
            days: Delete files older than this many days
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        
        for filepath in self.archive_dir.glob("*.json"):
            if filepath.stat().st_mtime < cutoff:
                filepath.unlink()
                print(f"🗑️  Deleted old file: {filepath.name}")


# MT5 EA pseudo-code (for reference)
"""
// MT5 EA reads signals and executes trades
// Place this in MT5/MQL5/Experts/

void OnTimer()
{
    // Check for new signals
    string signals_dir = "mt5_comm/signals/";
    
    // Look for signal_*.json files
    // Parse JSON
    // Execute trade
    // Write execution report to mt5_comm/reports/
    // Move processed signal to archive
}
"""


# Example usage
if __name__ == "__main__":
    from datetime import datetime
    
    # Initialize interface
    mt5 = MT5Interface()
    
    # Create a signal
    signal = TradeSignal(
        signal_id="SIGNAL_20250130_001",
        timestamp=datetime.now(),
        symbol="NQ",
        direction="LONG",
        entry_price=None,  # Market order
        stop_loss=17500.0,
        take_profit_1=17600.0,
        risk_r=1.0
    )
    
    # Send signal
    mt5.send_signal(signal)
    
    # Wait for execution (in real system)
    # report = mt5.wait_for_execution(signal.signal_id, timeout=30)
    
    print("\n✅ MT5 interface ready for production")
