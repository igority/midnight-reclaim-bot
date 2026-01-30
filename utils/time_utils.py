"""
Time Utilities
==============
Handles timezone conversions and session time detection.
All strategy logic operates in US/Eastern (EST/EDT).
"""

import pytz
from datetime import datetime, time, timedelta
from typing import Optional


class TimeUtils:
    """Utilities for time handling in trading strategy."""
    
    # Timezone constants
    EST = pytz.timezone('America/New_York')
    UTC = pytz.UTC
    
    def __init__(self):
        pass
    
    @classmethod
    def to_est(cls, dt: datetime) -> datetime:
        """
        Convert any datetime to US/Eastern timezone.
        
        Args:
            dt: DateTime to convert (can be naive or aware)
            
        Returns:
            DateTime in US/Eastern timezone
        """
        if dt.tzinfo is None:
            # Assume UTC if naive
            dt = cls.UTC.localize(dt)
        
        return dt.astimezone(cls.EST)
    
    @classmethod
    def get_midnight_open(cls, dt: datetime) -> datetime:
        """
        Get the midnight open (00:00 EST) for a given date.
        
        Args:
            dt: Any datetime on the target day
            
        Returns:
            Datetime at 00:00 EST on that day
        """
        dt_est = cls.to_est(dt)
        midnight = dt_est.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight
    
    @classmethod
    def is_in_trading_window(
        cls, 
        dt: datetime,
        start_time: str = "09:30",
        end_time: str = "10:30"
    ) -> bool:
        """
        Check if datetime is within the trading window.
        
        Args:
            dt: DateTime to check
            start_time: Window start (HH:MM format)
            end_time: Window end (HH:MM format)
            
        Returns:
            True if within trading window
        """
        dt_est = cls.to_est(dt)
        current_time = dt_est.time()
        
        start_h, start_m = map(int, start_time.split(':'))
        end_h, end_m = map(int, end_time.split(':'))
        
        window_start = time(start_h, start_m)
        window_end = time(end_h, end_m)
        
        return window_start <= current_time <= window_end
    
    @classmethod
    def get_session_date(cls, dt: datetime) -> datetime:
        """
        Get the "session date" for a datetime.
        
        Futures sessions run overnight, so times after midnight
        but before official close (16:00) belong to previous session.
        
        Args:
            dt: DateTime to check
            
        Returns:
            The session date
        """
        dt_est = cls.to_est(dt)
        
        # If before 16:00 (4 PM), still part of previous session
        if dt_est.hour < 16:
            return dt_est.date()
        else:
            # After 16:00, belongs to next session
            return (dt_est + timedelta(days=1)).date()
    
    @classmethod
    def get_overnight_range_period(
        cls,
        reference_dt: datetime
    ) -> tuple[datetime, datetime]:
        """
        Get the start and end times for overnight range calculation.
        
        Overnight range: Previous day close (16:00) → Current midnight (00:00)
        
        Args:
            reference_dt: The reference datetime (usually current bar)
            
        Returns:
            Tuple of (start_dt, end_dt) for overnight range
        """
        dt_est = cls.to_est(reference_dt)
        
        # Get midnight of current day
        midnight = cls.get_midnight_open(dt_est)
        
        # Previous day close is 16:00 on previous day
        prev_day = midnight - timedelta(days=1)
        prev_close = prev_day.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return prev_close, midnight
    
    @classmethod
    def minutes_between(cls, dt1: datetime, dt2: datetime) -> float:
        """
        Calculate minutes between two datetimes.
        
        Args:
            dt1: Earlier datetime
            dt2: Later datetime
            
        Returns:
            Minutes elapsed (can be negative if dt2 < dt1)
        """
        delta = dt2 - dt1
        return delta.total_seconds() / 60.0
    
    @classmethod
    def format_est(cls, dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
        """
        Format datetime in EST with timezone label.
        
        Args:
            dt: DateTime to format
            fmt: strftime format string
            
        Returns:
            Formatted string
        """
        dt_est = cls.to_est(dt)
        return dt_est.strftime(fmt)


# Example usage and tests
if __name__ == "__main__":
    # Create a test datetime
    test_dt = datetime(2025, 1, 30, 14, 30, 0, tzinfo=pytz.UTC)
    
    print("Original (UTC):", test_dt)
    print("Converted to EST:", TimeUtils.to_est(test_dt))
    print()
    
    # Get midnight open
    midnight = TimeUtils.get_midnight_open(test_dt)
    print("Midnight Open:", midnight)
    print()
    
    # Check trading window
    trading_time = datetime(2025, 1, 30, 14, 45, 0, tzinfo=pytz.UTC)  # 09:45 EST
    print("Is 09:45 EST in trading window?", TimeUtils.is_in_trading_window(trading_time))
    
    early_time = datetime(2025, 1, 30, 13, 0, 0, tzinfo=pytz.UTC)  # 08:00 EST
    print("Is 08:00 EST in trading window?", TimeUtils.is_in_trading_window(early_time))
    print()
    
    # Overnight range period
    start, end = TimeUtils.get_overnight_range_period(test_dt)
    print("Overnight Range Period:")
    print(f"  Start: {TimeUtils.format_est(start)}")
    print(f"  End: {TimeUtils.format_est(end)}")
