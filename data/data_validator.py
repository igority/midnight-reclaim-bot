"""
Data Validator
===============
Validates historical data quality before backtesting.
Detects gaps, duplicates, missing bars, and timezone issues.

Critical for production backtesting - bad data = false confidence.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pytz


class DataValidator:
    """
    Validates OHLCV data quality.
    """
    
    def __init__(self, expected_bar_size: str = "1min"):
        """
        Initialize validator.
        
        Args:
            expected_bar_size: Expected bar size ("1min", "5min", etc.)
        """
        self.expected_bar_size = expected_bar_size
        self.bar_size_seconds = self._parse_bar_size(expected_bar_size)
    
    def _parse_bar_size(self, bar_size: str) -> int:
        """Convert bar size string to seconds."""
        if bar_size == "1min":
            return 60
        elif bar_size == "5min":
            return 300
        elif bar_size == "15min":
            return 900
        elif bar_size == "1hour":
            return 3600
        else:
            raise ValueError(f"Unsupported bar size: {bar_size}")
    
    def validate(self, df: pd.DataFrame, symbol: str) -> Dict[str, any]:
        """
        Run all validation checks.
        
        Args:
            df: DataFrame with OHLCV data (index = timestamp)
            symbol: Instrument symbol for reporting
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'symbol': symbol,
            'total_bars': len(df),
            'date_range': (df.index[0], df.index[-1]),
            'issues': [],
            'warnings': [],
            'passed': True
        }
        
        # Check 1: Duplicates
        duplicates = self._check_duplicates(df)
        if duplicates:
            results['issues'].append(f"Found {len(duplicates)} duplicate timestamps")
            results['passed'] = False
        
        # Check 2: Missing bars (gaps)
        gaps = self._check_gaps(df)
        if gaps:
            results['warnings'].append(f"Found {len(gaps)} time gaps")
            results['gap_details'] = gaps[:10]  # First 10 gaps
        
        # Check 3: OHLC logic
        ohlc_errors = self._check_ohlc_logic(df)
        if ohlc_errors:
            results['issues'].append(f"Found {len(ohlc_errors)} OHLC logic errors")
            results['passed'] = False
        
        # Check 4: Zero volume bars
        zero_volume = self._check_zero_volume(df)
        if zero_volume > 0:
            results['warnings'].append(f"Found {zero_volume} bars with zero volume")
        
        # Check 5: Timezone consistency
        tz_check = self._check_timezone(df)
        if not tz_check['consistent']:
            results['issues'].append(f"Timezone inconsistency: {tz_check['message']}")
            results['passed'] = False
        
        # Check 6: Price anomalies
        anomalies = self._check_price_anomalies(df)
        if anomalies:
            results['warnings'].append(f"Found {len(anomalies)} potential price anomalies")
            results['anomaly_details'] = anomalies[:5]  # First 5
        
        return results
    
    def _check_duplicates(self, df: pd.DataFrame) -> List[datetime]:
        """Check for duplicate timestamps."""
        duplicates = df.index[df.index.duplicated()].tolist()
        return duplicates
    
    def _check_gaps(self, df: pd.DataFrame) -> List[Tuple[datetime, datetime, int]]:
        """
        Check for missing bars (time gaps).
        
        Returns:
            List of (gap_start, gap_end, missing_bars)
        """
        gaps = []
        
        for i in range(1, len(df)):
            prev_time = df.index[i-1]
            curr_time = df.index[i]
            
            expected_diff = timedelta(seconds=self.bar_size_seconds)
            actual_diff = curr_time - prev_time
            
            # Allow small tolerance (1 second)
            if actual_diff > expected_diff + timedelta(seconds=1):
                missing_bars = int(actual_diff.total_seconds() / self.bar_size_seconds) - 1
                
                # Only report gaps during regular trading hours
                # (futures trade 23+ hours, so overnight gaps are normal)
                if missing_bars >= 1 and missing_bars < 100:  # Ignore weekend gaps
                    gaps.append((prev_time, curr_time, missing_bars))
        
        return gaps
    
    def _check_ohlc_logic(self, df: pd.DataFrame) -> List[Tuple[datetime, str]]:
        """
        Check that OHLC values make sense.
        
        Rules:
        - high >= open, close, low
        - low <= open, close, high
        - All prices > 0
        """
        errors = []
        
        # Check high is highest
        invalid_high = df[
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['high'] < df['low'])
        ]
        
        for idx in invalid_high.index:
            errors.append((idx, "High is not highest price"))
        
        # Check low is lowest
        invalid_low = df[
            (df['low'] > df['open']) |
            (df['low'] > df['close']) |
            (df['low'] > df['high'])
        ]
        
        for idx in invalid_low.index:
            errors.append((idx, "Low is not lowest price"))
        
        # Check positive prices
        invalid_prices = df[
            (df['open'] <= 0) |
            (df['high'] <= 0) |
            (df['low'] <= 0) |
            (df['close'] <= 0)
        ]
        
        for idx in invalid_prices.index:
            errors.append((idx, "Non-positive price detected"))
        
        return errors
    
    def _check_zero_volume(self, df: pd.DataFrame) -> int:
        """Count bars with zero volume."""
        return len(df[df['volume'] == 0])
    
    def _check_timezone(self, df: pd.DataFrame) -> Dict[str, any]:
        """Check timezone consistency."""
        if not isinstance(df.index, pd.DatetimeIndex):
            return {'consistent': False, 'message': 'Index is not DatetimeIndex'}
        
        if df.index.tz is None:
            return {'consistent': False, 'message': 'Timestamps are timezone-naive'}
        
        # Check all timestamps have same timezone
        tz_set = set([t.tzinfo for t in df.index])
        if len(tz_set) > 1:
            return {'consistent': False, 'message': f'Multiple timezones detected: {tz_set}'}
        
        return {'consistent': True, 'message': f'All timestamps in {df.index.tz}'}
    
    def _check_price_anomalies(self, df: pd.DataFrame) -> List[Tuple[datetime, str, float]]:
        """
        Detect potential price anomalies (spikes, flash crashes).
        
        Uses simple statistical outlier detection.
        """
        anomalies = []
        
        # Calculate returns
        df = df.copy()
        df['return'] = df['close'].pct_change()
        
        # Find extreme returns (beyond 3 standard deviations)
        mean_return = df['return'].mean()
        std_return = df['return'].std()
        
        extreme = df[abs(df['return'] - mean_return) > 3 * std_return]
        
        for idx, row in extreme.iterrows():
            anomalies.append((idx, "Extreme return", row['return']))
        
        return anomalies
    
    def print_report(self, results: Dict[str, any]) -> None:
        """Print validation report."""
        print("\n" + "="*70)
        print(f"DATA VALIDATION REPORT: {results['symbol']}")
        print("="*70)
        
        print(f"\nTotal bars: {results['total_bars']}")
        print(f"Date range: {results['date_range'][0]} → {results['date_range'][1]}")
        
        if results['passed']:
            print("\n✅ VALIDATION PASSED")
        else:
            print("\n❌ VALIDATION FAILED")
        
        if results['issues']:
            print("\n🔴 CRITICAL ISSUES:")
            for issue in results['issues']:
                print(f"   - {issue}")
        
        if results['warnings']:
            print("\n⚠️  WARNINGS:")
            for warning in results['warnings']:
                print(f"   - {warning}")
        
        if 'gap_details' in results:
            print("\n📊 Gap Details (first 10):")
            for gap_start, gap_end, missing in results['gap_details']:
                print(f"   {gap_start} → {gap_end}: {missing} missing bars")
        
        if 'anomaly_details' in results:
            print("\n📈 Price Anomalies (first 5):")
            for ts, msg, value in results['anomaly_details']:
                print(f"   {ts}: {msg} ({value:.4f})")
        
        print("="*70 + "\n")


# Example usage
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range('2025-01-20', '2025-01-25', freq='1min', tz='America/New_York')
    
    df = pd.DataFrame({
        'open': 17500 + pd.Series(range(len(dates))) * 0.01,
        'high': 17505 + pd.Series(range(len(dates))) * 0.01,
        'low': 17495 + pd.Series(range(len(dates))) * 0.01,
        'close': 17500 + pd.Series(range(len(dates))) * 0.01,
        'volume': 1000
    }, index=dates)
    
    # Validate
    validator = DataValidator(expected_bar_size="1min")
    results = validator.validate(df, "NQ")
    validator.print_report(results)
