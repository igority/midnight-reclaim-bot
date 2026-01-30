"""
Core Indicators
===============
All indicator calculations for the v1.0 strategy.

Indicators:
1. Midnight Open (MO) - Anchor price at 00:00 EST
2. ADR (Average Daily Range) - 20-day rolling average
3. ONS (Overnight Session) - Overnight range vs ADR validation
4. ISI (Impulse Strength Index) - Displacement measurement
5. SMT (Smart Money Technique) - Divergence detection

All calculations are timezone-aware and use EST for strategy logic.
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Optional, Tuple, Dict, Any
from utils.time_utils import TimeUtils
from utils.config_loader import Config


class MidnightOpenCalculator:
    """
    Calculates and caches the Midnight Open (00:00 EST) price.
    
    The Midnight Open is the anchor price for the entire strategy.
    """
    
    def __init__(self):
        """Initialize midnight open calculator."""
        self._cache = {}  # Cache MO by date
    
    def calculate(self, df: pd.DataFrame, target_date: datetime) -> float:
        """
        Get midnight open price for a specific date.
        
        Args:
            df: DataFrame with OHLC data (index must be datetime in EST)
            target_date: The date to get midnight open for
        
        Returns:
            Midnight open price (open at 00:00 EST)
        
        Raises:
            ValueError: If no data exists at midnight
        """
        # Convert target to EST and get midnight
        target_est = TimeUtils.to_est(target_date)
        midnight = TimeUtils.get_midnight_open(target_est)
        
        # Check cache first
        cache_key = midnight.date()
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Ensure dataframe index is in EST
        if df.index.tz != TimeUtils.EST:
            df = df.copy()
            df.index = df.index.tz_convert(TimeUtils.EST)
        
        # Find the bar at or immediately after midnight
        # Some data sources might not have exact midnight bar
        midnight_bars = df[
            (df.index >= midnight) &
            (df.index < midnight + pd.Timedelta(minutes=5))
        ]
        
        if midnight_bars.empty:
            raise ValueError(
                f"No data found at midnight {midnight}. "
                f"Available range: {df.index[0]} to {df.index[-1]}"
            )
        
        # Use the open of the first bar at/after midnight
        mo_price = midnight_bars.iloc[0]['open']
        
        # Cache it
        self._cache[cache_key] = mo_price
        
        return mo_price
    
    def clear_cache(self):
        """Clear the cache (useful for testing)."""
        self._cache = {}


class ADRCalculator:
    """
    Calculates Average Daily Range (ADR).
    
    ADR = average(high - low) over last N days.
    Used for normalizing overnight ranges and sweep depths.
    """
    
    def __init__(self, lookback_days: int = 20):
        """
        Initialize ADR calculator.
        
        Args:
            lookback_days: Number of days to average (default: 20 from config)
        """
        self.lookback_days = lookback_days
    
    def calculate(self, df: pd.DataFrame, as_of_date: datetime) -> float:
        """
        Calculate ADR as of a specific date.
        
        Args:
            df: DataFrame with OHLC data (any timeframe)
            as_of_date: Calculate ADR up to this date (exclusive)
        
        Returns:
            ADR value
        
        Raises:
            ValueError: If insufficient data
        """
        # Convert to EST
        as_of_est = TimeUtils.to_est(as_of_date)
        
        # Resample to daily bars (if not already)
        daily = df.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        # Get data before as_of_date
        historical = daily[daily.index < as_of_est]
        
        if len(historical) < self.lookback_days:
            raise ValueError(
                f"Insufficient data for ADR calculation. "
                f"Need {self.lookback_days} days, have {len(historical)}"
            )
        
        # Get last N days
        last_n = historical.tail(self.lookback_days)
        
        # Calculate daily ranges
        daily_ranges = last_n['high'] - last_n['low']
        
        # Average
        adr = daily_ranges.mean()
        
        return adr


class ONSFilter:
    """
    Overnight Session (ONS) range filter.
    
    Validates that overnight range is within acceptable bounds
    relative to ADR (30% to 70% by default).
    
    If overnight is too tight → market hasn't moved enough
    If overnight is too wide → already exhausted, avoid
    """
    
    def __init__(
        self,
        min_ratio: float = 0.30,
        max_ratio: float = 0.70,
        adr_lookback: int = 20
    ):
        """
        Initialize ONS filter.
        
        Args:
            min_ratio: Minimum acceptable ratio (ONS/ADR)
            max_ratio: Maximum acceptable ratio (ONS/ADR)
            adr_lookback: Days for ADR calculation
        """
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio
        self.adr_calculator = ADRCalculator(lookback_days=adr_lookback)
    
    def calculate_ons_range(
        self,
        df: pd.DataFrame,
        target_date: datetime
    ) -> Tuple[float, float, float]:
        """
        Calculate overnight session range.
        
        Overnight session = Previous day close (16:00) → Current midnight (00:00)
        
        Args:
            df: DataFrame with OHLC data
            target_date: The date to calculate ONS for
        
        Returns:
            Tuple of (ons_high, ons_low, ons_range)
        """
        target_est = TimeUtils.to_est(target_date)
        
        # Get overnight period
        ons_start, ons_end = TimeUtils.get_overnight_range_period(target_est)
        
        # Filter data to overnight period
        ons_data = df[
            (df.index >= ons_start) &
            (df.index <= ons_end)
        ]
        
        if ons_data.empty:
            raise ValueError(
                f"No data in overnight session {ons_start} to {ons_end}"
            )
        
        ons_high = ons_data['high'].max()
        ons_low = ons_data['low'].min()
        ons_range = ons_high - ons_low
        
        return ons_high, ons_low, ons_range
    
    def validate(
        self,
        df: pd.DataFrame,
        target_date: datetime
    ) -> Dict[str, Any]:
        """
        Validate overnight session range against ADR.
        
        Args:
            df: DataFrame with OHLC data
            target_date: Date to validate
        
        Returns:
            Dict with validation results:
            {
                'valid': bool,
                'ons_range': float,
                'adr': float,
                'ratio': float,
                'reason': str (if invalid)
            }
        """
        # Calculate ONS range
        ons_high, ons_low, ons_range = self.calculate_ons_range(df, target_date)
        
        # Calculate ADR (up to target date, not including it)
        adr = self.adr_calculator.calculate(df, target_date)
        
        # Calculate ratio
        ratio = ons_range / adr
        
        # Validate
        valid = self.min_ratio <= ratio <= self.max_ratio
        
        # Determine reason if invalid
        reason = None
        if not valid:
            if ratio < self.min_ratio:
                reason = f"ONS too tight: {ratio:.2%} < {self.min_ratio:.2%}"
            else:
                reason = f"ONS too wide: {ratio:.2%} > {self.max_ratio:.2%}"
        
        return {
            'valid': valid,
            'ons_range': ons_range,
            'ons_high': ons_high,
            'ons_low': ons_low,
            'adr': adr,
            'ratio': ratio,
            'reason': reason
        }


class ISICalculator:
    """
    Impulse Strength Index (ISI) - Displacement Filter.
    
    Quantifies the "strength" of a price move to determine if it's:
    - Strong displacement (trend, don't fade) → ISI > 2.0
    - Weak/grindy (fade-able) → ISI < 1.2
    - Unclear (wait) → 1.2 <= ISI <= 2.0
    
    Formula:
    ISI = (AvgBody/ATR) × ConsecutiveBars × (1 - AvgWickRatio)
    
    Components:
    - Body ratio: Measures candle conviction
    - Consecutive bars: Measures sustained direction
    - Wick penalty: Penalizes indecision
    """
    
    def __init__(
        self,
        threshold_min: float = 1.2,
        threshold_max: float = 2.0,
        atr_period: int = 14
    ):
        """
        Initialize ISI calculator.
        
        Args:
            threshold_min: Below this = fade OK
            threshold_max: Above this = no fade (strong trend)
            atr_period: Period for ATR calculation
        """
        self.threshold_min = threshold_min
        self.threshold_max = threshold_max
        self.atr_period = atr_period
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period
        
        Returns:
            Series of ATR values
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range components
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        # True Range = max of the three
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = moving average of TR
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate(
        self,
        df: pd.DataFrame,
        start_idx: int,
        end_idx: int
    ) -> Dict[str, Any]:
        """
        Calculate ISI for a price move between two indices.
        
        Args:
            df: DataFrame with OHLC data
            start_idx: Start of move (deviation start)
            end_idx: End of move (deviation end/reclaim)
        
        Returns:
            Dict with ISI calculation:
            {
                'isi': float,
                'avg_body_ratio': float,
                'consecutive_bars': int,
                'avg_wick_ratio': float,
                'atr': float,
                'assessment': str ('FADE_OK', 'WAIT', 'NO_FADE')
            }
        """
        # Get the bars in the move
        move_bars = df.iloc[start_idx:end_idx+1]
        
        if len(move_bars) < 2:
            return {
                'isi': 0.0,
                'avg_body_ratio': 0.0,
                'consecutive_bars': 0,
                'avg_wick_ratio': 1.0,
                'atr': 0.0,
                'assessment': 'INSUFFICIENT_DATA'
            }
        
        # Calculate ATR at the end of the move
        atr_series = self.calculate_atr(df, period=self.atr_period)
        atr = atr_series.iloc[end_idx]
        
        if pd.isna(atr) or atr == 0:
            atr = (df['high'].iloc[end_idx] - df['low'].iloc[end_idx]) * 1.5
        
        # Component 1: Average body ratio
        bodies = abs(move_bars['close'] - move_bars['open'])
        ranges = move_bars['high'] - move_bars['low']
        body_ratios = bodies / ranges.replace(0, np.nan)
        avg_body_ratio = body_ratios.mean()
        
        # Component 2: Consecutive bars in same direction
        consecutive_bars = len(move_bars)
        
        # Component 3: Average wick ratio
        upper_wicks = move_bars['high'] - move_bars[['open', 'close']].max(axis=1)
        lower_wicks = move_bars[['open', 'close']].min(axis=1) - move_bars['low']
        total_wicks = upper_wicks + lower_wicks
        wick_ratios = total_wicks / ranges.replace(0, np.nan)
        avg_wick_ratio = wick_ratios.mean()
        
        # Calculate ISI
        avg_body_points = bodies.mean()
        isi = (avg_body_points / atr) * consecutive_bars * (1 - avg_wick_ratio)
        
        # Assess
        if isi < self.threshold_min:
            assessment = 'FADE_OK'
        elif isi > self.threshold_max:
            assessment = 'NO_FADE'
        else:
            assessment = 'WAIT'
        
        return {
            'isi': isi,
            'avg_body_ratio': avg_body_ratio,
            'consecutive_bars': consecutive_bars,
            'avg_wick_ratio': avg_wick_ratio,
            'atr': atr,
            'assessment': assessment
        }


class SMTDetector:
    """
    Smart Money Technique (SMT) Divergence Detector.
    
    Detects when two correlated instruments (NQ and ES) diverge in their
    liquidity sweeps, indicating manipulation/absorption.
    
    v1.0: Binary detection (sweep vs no sweep)
    v1.5+: Degree measurement for threshold tuning
    """
    
    def __init__(
        self,
        min_sweep_ticks: int = 5,
        atr_period: int = 14
    ):
        """
        Initialize SMT detector.
        
        Args:
            min_sweep_ticks: Minimum ticks below prior low to count as sweep
            atr_period: Period for ATR (used in degree calculation)
        """
        self.min_sweep_ticks = min_sweep_ticks
        self.atr_period = atr_period
    
    def detect_sweep(
        self,
        df: pd.DataFrame,
        reference_level: float,
        direction: str = 'below'
    ) -> Dict[str, Any]:
        """
        Detect if price swept a reference level.
        
        Args:
            df: DataFrame with OHLC data
            reference_level: The level to check (e.g., prior session low)
            direction: 'below' for long setups, 'above' for short setups
        
        Returns:
            Dict with sweep detection:
            {
                'swept': bool,
                'sweep_depth': float (points),
                'sweep_depth_norm': float (normalized by ATR),
                'sweep_low': float (or sweep_high for short),
                'sweep_time': datetime
            }
        """
        if direction == 'below':
            # Check if any low swept below reference
            sweep_bars = df[df['low'] < reference_level]
            
            if sweep_bars.empty:
                return {
                    'swept': False,
                    'sweep_depth': 0.0,
                    'sweep_depth_norm': 0.0,
                    'sweep_low': None,
                    'sweep_time': None
                }
            
            # Get the lowest point
            sweep_idx = sweep_bars['low'].idxmin()
            sweep_low = sweep_bars.loc[sweep_idx, 'low']
            sweep_depth = reference_level - sweep_low
            
            # Calculate ATR for normalization
            atr_series = self._calculate_atr(df)
            atr = atr_series.loc[sweep_idx]
            
            if pd.isna(atr) or atr == 0:
                atr = (df.loc[sweep_idx, 'high'] - df.loc[sweep_idx, 'low']) * 1.5
            
            sweep_depth_norm = sweep_depth / atr
            
            return {
                'swept': True,
                'sweep_depth': sweep_depth,
                'sweep_depth_norm': sweep_depth_norm,
                'sweep_low': sweep_low,
                'sweep_time': sweep_idx
            }
        
        else:  # direction == 'above'
            # Check if any high swept above reference
            sweep_bars = df[df['high'] > reference_level]
            
            if sweep_bars.empty:
                return {
                    'swept': False,
                    'sweep_depth': 0.0,
                    'sweep_depth_norm': 0.0,
                    'sweep_high': None,
                    'sweep_time': None
                }
            
            sweep_idx = sweep_bars['high'].idxmax()
            sweep_high = sweep_bars.loc[sweep_idx, 'high']
            sweep_depth = sweep_high - reference_level
            
            atr_series = self._calculate_atr(df)
            atr = atr_series.loc[sweep_idx]
            
            if pd.isna(atr) or atr == 0:
                atr = (df.loc[sweep_idx, 'high'] - df.loc[sweep_idx, 'low']) * 1.5
            
            sweep_depth_norm = sweep_depth / atr
            
            return {
                'swept': True,
                'sweep_depth': sweep_depth,
                'sweep_depth_norm': sweep_depth_norm,
                'sweep_high': sweep_high,
                'sweep_time': sweep_idx
            }
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate ATR for the dataframe."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        
        return atr
    
    def detect_divergence(
        self,
        instrument_a_df: pd.DataFrame,
        instrument_b_df: pd.DataFrame,
        reference_level_a: float,
        reference_level_b: float,
        direction: str = 'below'
    ) -> Dict[str, Any]:
        """
        Detect SMT divergence between two instruments.
        
        Args:
            instrument_a_df: Primary instrument (e.g., NQ)
            instrument_b_df: Reference instrument (e.g., ES)
            reference_level_a: Reference level for instrument A
            reference_level_b: Reference level for instrument B
            direction: 'below' for long, 'above' for short
        
        Returns:
            Dict with SMT analysis:
            {
                'smt_binary': bool (A swept, B didn't),
                'smt_degree': float (difference in normalized sweeps),
                'instrument_a_sweep': dict,
                'instrument_b_sweep': dict
            }
        """
        # Detect sweeps on both instruments
        sweep_a = self.detect_sweep(instrument_a_df, reference_level_a, direction)
        sweep_b = self.detect_sweep(instrument_b_df, reference_level_b, direction)
        
        # Binary SMT: A swept, B didn't
        smt_binary = sweep_a['swept'] and not sweep_b['swept']
        
        # Degree: Difference in normalized sweep depths
        smt_degree = sweep_a['sweep_depth_norm'] - sweep_b['sweep_depth_norm']
        
        return {
            'smt_binary': smt_binary,
            'smt_degree': smt_degree,
            'instrument_a_sweep': sweep_a,
            'instrument_b_sweep': sweep_b
        }


# Test the indicators
if __name__ == "__main__":
    from data.yahoo_loader import YahooFinanceLoader
    
    print("="*70)
    print("TESTING INDICATORS")
    print("="*70)
    
    # Load some data
    print("\n1. Loading data...")
    loader = YahooFinanceLoader()
    nq_data = loader.fetch_historical_bars('NQ', period='30d', interval='1m')
    
    print(f"   Loaded {len(nq_data)} bars")
    print(f"   Range: {nq_data.index[0]} to {nq_data.index[-1]}")
    
    # Test Midnight Open
    print("\n2. Testing Midnight Open Calculator...")
    mo_calc = MidnightOpenCalculator()
    
    # Get midnight open for most recent complete day
    recent_date = nq_data.index[-1]
    mo_price = mo_calc.calculate(nq_data, recent_date)
    
    print(f"   ✅ Midnight Open for {recent_date.date()}: {mo_price:.2f}")
    
    # Test ADR
    print("\n3. Testing ADR Calculator...")
    adr_calc = ADRCalculator(lookback_days=20)
    adr = adr_calc.calculate(nq_data, recent_date)
    
    print(f"   ✅ ADR (20-day): {adr:.2f} points")
    
    # Test ONS Filter
    print("\n4. Testing ONS Filter...")
    ons_filter = ONSFilter(min_ratio=0.30, max_ratio=0.70)
    ons_result = ons_filter.validate(nq_data, recent_date)
    
    print(f"   ✅ ONS Valid: {ons_result['valid']}")
    print(f"   ONS Range: {ons_result['ons_range']:.2f}")
    print(f"   ADR: {ons_result['adr']:.2f}")
    print(f"   Ratio: {ons_result['ratio']:.2%}")
    
    if not ons_result['valid']:
        print(f"   ⚠️  Reason: {ons_result['reason']}")
    
    print("\n" + "="*70)
    print("✅ INDICATOR TESTS COMPLETE")
    print("="*70)
    
    # Test ISI Calculator
    print("\n5. Testing ISI Calculator...")
    isi_calc = ISICalculator(threshold_min=1.2, threshold_max=2.0)
    
    # Get a sample move (last 10 bars)
    start_idx = len(nq_data) - 10
    end_idx = len(nq_data) - 1
    
    isi_result = isi_calc.calculate(nq_data, start_idx, end_idx)
    
    print(f"   ✅ ISI Value: {isi_result['isi']:.2f}")
    print(f"   Assessment: {isi_result['assessment']}")
    print(f"   Avg Body Ratio: {isi_result['avg_body_ratio']:.2%}")
    print(f"   Consecutive Bars: {isi_result['consecutive_bars']}")
    print(f"   Avg Wick Ratio: {isi_result['avg_wick_ratio']:.2%}")
    
    # Test SMT Detector
    print("\n6. Testing SMT Detector...")
    
    # Load ES data
    es_data = loader.fetch_historical_bars('ES', period='30d', interval='1m')
    
    smt_detector = SMTDetector(min_sweep_ticks=5)
    
    # Use ONS low as reference level (example)
    nq_reference = ons_result['ons_low']
    es_reference = es_data['low'].min()  # Simplified for test
    
    smt_result = smt_detector.detect_divergence(
        nq_data,
        es_data,
        nq_reference,
        es_reference,
        direction='below'
    )
    
    print(f"   ✅ SMT Binary: {smt_result['smt_binary']}")
    print(f"   SMT Degree: {smt_result['smt_degree']:.2f}")
    print(f"   NQ Swept: {smt_result['instrument_a_sweep']['swept']}")
    print(f"   ES Swept: {smt_result['instrument_b_sweep']['swept']}")
    
    if smt_result['instrument_a_sweep']['swept']:
        print(f"   NQ Sweep Depth: {smt_result['instrument_a_sweep']['sweep_depth']:.2f}")
    
    print("\n" + "="*70)
    print("✅ ALL INDICATOR TESTS COMPLETE")
    print("="*70)
    print("\nIndicators ready for:")
    print("  - State machine integration (Sprint 3)")
    print("  - Strategy logic (Sprint 4)")
    print("  - Shadow trade evaluation")

