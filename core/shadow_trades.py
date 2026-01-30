"""
Shadow Trade Manager
====================
Manages logging and analysis of "near-miss" trades (one-filter-failed).

CRITICAL RULES:
1. Shadow trades NEVER affect live trading decisions
2. Only log trades that failed exactly ONE filter
3. Shadow trades use SAME exit logic as real trades
4. Shadow performance NOT reviewed until 50 real trades complete

This is write-only telemetry for post-50 filter evaluation.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib


@dataclass
class FilterCheck:
    """
    Result of a single filter check.
    """
    filter_name: str
    passed: bool
    
    # Proximity to threshold (how close was it?)
    value: Optional[float] = None  # Actual value
    threshold: Optional[float] = None  # Required threshold
    distance: Optional[float] = None  # How far from passing
    
    # Context
    notes: Optional[str] = None


class ShadowTradeManager:
    """
    Determines if a rejected setup qualifies as a shadow trade.
    """
    
    # Filters that can block trades
    CORE_FILTERS = [
        'TIME_WINDOW',
        'ONS_VALID',
        'DEVIATION_DETECTED',
        'RECLAIM_DETECTED'
    ]
    
    GATING_FILTERS = [
        'SMT_BINARY',
        'SMT_DEGREE',
        'ISI_DISPLACEMENT',
        'RECLAIM_TIMEOUT',
        'RECLAIM_BODY_RATIO'
    ]
    
    def __init__(self):
        self.shadow_trade_count = 0
        self.review_unlocked = False  # Lock until 50 real trades
    
    def evaluate_for_shadow_trade(
        self,
        filter_results: List[FilterCheck]
    ) -> Dict[str, Any]:
        """
        Determine if a rejected setup qualifies as a shadow trade.
        
        Shadow trade criteria:
        1. ALL core structural filters passed
        2. EXACTLY ONE gating filter failed
        3. Failed filter was a "near miss" (close to threshold)
        
        Args:
            filter_results: List of FilterCheck objects
            
        Returns:
            Dict with shadow trade decision and metadata
        """
        # Separate core and gating filters
        core_results = [f for f in filter_results if f.filter_name in self.CORE_FILTERS]
        gating_results = [f for f in filter_results if f.filter_name in self.GATING_FILTERS]
        
        # Check 1: All core filters must pass
        core_passed = all(f.passed for f in core_results)
        
        if not core_passed:
            return {
                'is_shadow_trade': False,
                'reason': 'Core structural conditions not met',
                'blocked_by': None
            }
        
        # Check 2: Count gating filter failures
        gating_failures = [f for f in gating_results if not f.passed]
        
        if len(gating_failures) == 0:
            # This shouldn't happen - trade should have been taken
            return {
                'is_shadow_trade': False,
                'reason': 'All filters passed - should be real trade',
                'blocked_by': None
            }
        
        if len(gating_failures) > 1:
            # Multiple failures - not a near miss
            return {
                'is_shadow_trade': False,
                'reason': f'Multiple filters failed ({len(gating_failures)})',
                'blocked_by': [f.filter_name for f in gating_failures]
            }
        
        # Exactly one gating filter failed - this is a shadow trade candidate
        failed_filter = gating_failures[0]
        
        # Check 3: Was it a "near miss"? (optional proximity check)
        is_near_miss = self._is_near_miss(failed_filter)
        
        self.shadow_trade_count += 1
        
        return {
            'is_shadow_trade': True,
            'reason': 'One-filter-failed candidate',
            'blocked_by': failed_filter.filter_name,
            'blocking_filter_value': failed_filter.value,
            'blocking_filter_threshold': failed_filter.threshold,
            'proximity': failed_filter.distance,
            'is_near_miss': is_near_miss,
            'filters_passed': [f.filter_name for f in filter_results if f.passed],
            'filters_failed': [f.filter_name for f in gating_failures]
        }
    
    def _is_near_miss(self, failed_filter: FilterCheck) -> bool:
        """
        Determine if a failed filter was a "near miss".
        
        Near miss definition: Within 20% of threshold.
        """
        if failed_filter.distance is None:
            return True  # Can't determine, assume yes
        
        if failed_filter.threshold is None or failed_filter.threshold == 0:
            return True
        
        # Calculate relative distance
        relative_distance = abs(failed_filter.distance) / abs(failed_filter.threshold)
        
        return relative_distance < 0.2  # Within 20%
    
    def unlock_review(self, real_trade_count: int) -> None:
        """
        Unlock shadow trade review after 50 real trades.
        
        Args:
            real_trade_count: Number of real trades completed
        """
        if real_trade_count >= 50 and not self.review_unlocked:
            self.review_unlocked = True
            print("\n" + "="*70)
            print("🔓 SHADOW TRADE REVIEW UNLOCKED")
            print("="*70)
            print(f"Real trades completed: {real_trade_count}")
            print(f"Shadow trades logged: {self.shadow_trade_count}")
            print("\nYou may now analyze shadow trade performance.")
            print("="*70 + "\n")
    
    def get_filter_summary(self, filter_results: List[FilterCheck]) -> Dict[str, int]:
        """
        Summarize which filters passed/failed.
        
        Returns:
            Dict of filter_name -> count of failures
        """
        summary = {}
        for f in filter_results:
            if not f.passed:
                summary[f.filter_name] = summary.get(f.filter_name, 0) + 1
        return summary


class ShadowTradeAnalyzer:
    """
    Analyzes shadow trade performance after 50 real trades.
    
    DO NOT USE BEFORE 50 REAL TRADES COMPLETED.
    """
    
    def __init__(self, trade_log_df):
        """
        Initialize analyzer with trade log DataFrame.
        
        Args:
            trade_log_df: DataFrame from logs/trades/ CSV
        """
        self.df = trade_log_df
        self.real_trades = self.df[self.df['trade_type'] == 'REAL']
        self.shadow_trades = self.df[self.df['trade_type'] == 'SHADOW']
        
        if len(self.real_trades) < 50:
            raise ValueError(
                f"Analysis prohibited until 50 real trades. "
                f"Current count: {len(self.real_trades)}"
            )
    
    def analyze_by_filter(self) -> Dict[str, Dict[str, float]]:
        """
        Compare shadow trade performance by blocking filter.
        
        Returns:
            Dict of filter_name -> performance metrics
        """
        results = {}
        
        for filter_name in self.shadow_trades['blocked_by_filter'].unique():
            if pd.isna(filter_name):
                continue
            
            filter_shadows = self.shadow_trades[
                self.shadow_trades['blocked_by_filter'] == filter_name
            ]
            
            results[filter_name] = {
                'count': len(filter_shadows),
                'win_rate': filter_shadows['win'].mean(),
                'avg_r': filter_shadows['pnl_r'].mean(),
                'total_r': filter_shadows['pnl_r'].sum(),
                'best_r': filter_shadows['pnl_r'].max(),
                'worst_r': filter_shadows['pnl_r'].min()
            }
        
        return results
    
    def compare_to_real_trades(self) -> Dict[str, Any]:
        """
        Compare shadow trades to real trades.
        
        Returns:
            Comparison metrics
        """
        return {
            'real_trades': {
                'count': len(self.real_trades),
                'win_rate': self.real_trades['win'].mean(),
                'avg_r': self.real_trades['pnl_r'].mean(),
                'total_r': self.real_trades['pnl_r'].sum()
            },
            'shadow_trades': {
                'count': len(self.shadow_trades),
                'win_rate': self.shadow_trades['win'].mean(),
                'avg_r': self.shadow_trades['pnl_r'].mean(),
                'total_r': self.shadow_trades['pnl_r'].sum()
            }
        }
    
    def filter_opportunity_cost(self) -> Dict[str, float]:
        """
        Calculate opportunity cost of each filter.
        
        Opportunity cost = (R lost from blocking good trades) - (R saved from blocking bad trades)
        
        Returns:
            Dict of filter_name -> opportunity_cost
        """
        costs = {}
        
        for filter_name in self.shadow_trades['blocked_by_filter'].unique():
            if pd.isna(filter_name):
                continue
            
            filter_shadows = self.shadow_trades[
                self.shadow_trades['blocked_by_filter'] == filter_name
            ]
            
            # Opportunity cost = what we missed
            opportunity_cost = filter_shadows['pnl_r'].sum()
            
            costs[filter_name] = opportunity_cost
        
        return costs


# Example usage
if __name__ == "__main__":
    # Example filter checks for a rejected setup
    filter_results = [
        # Core filters (all passed)
        FilterCheck('TIME_WINDOW', passed=True),
        FilterCheck('ONS_VALID', passed=True),
        FilterCheck('DEVIATION_DETECTED', passed=True),
        FilterCheck('RECLAIM_DETECTED', passed=True),
        
        # Gating filters
        FilterCheck('SMT_BINARY', passed=False, value=False, threshold=True),
        FilterCheck('ISI_DISPLACEMENT', passed=True, value=1.1, threshold=1.2),
        FilterCheck('RECLAIM_TIMEOUT', passed=True, value=35, threshold=45),
    ]
    
    manager = ShadowTradeManager()
    result = manager.evaluate_for_shadow_trade(filter_results)
    
    print("Shadow Trade Evaluation:")
    print(f"  Is shadow trade: {result['is_shadow_trade']}")
    print(f"  Blocked by: {result.get('blocked_by')}")
    print(f"  Reason: {result['reason']}")
    
    if result['is_shadow_trade']:
        print(f"  Filters passed: {result['filters_passed']}")
        print(f"  Near miss: {result['is_near_miss']}")
        
        print("\n✅ This setup should be logged as a shadow trade")
        print("   (Simulated entry, same exit rules, logged as SHADOW)")
