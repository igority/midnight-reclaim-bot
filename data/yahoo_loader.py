"""
Yahoo Finance Data Loader
==========================
Free alternative to IBKR for backtesting.

IMPORTANT: This is for backtesting only. For live trading, use MT5 feed.

Yahoo Finance provides:
- Free historical data
- 1-minute bars (limited lookback)
- Continuous futures contracts (NQ=F, ES=F)

Limitations:
- May have gaps
- Not true futures tick data
- Slightly different from IBKR prices
- Accept this as normal for free data
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import pytz


class YahooFinanceLoader:
    """
    Loads historical data from Yahoo Finance (free).
    """
    
    # Symbol mapping
    SYMBOL_MAP = {
        'NQ': 'NQ=F',  # E-mini Nasdaq continuous
        'ES': 'ES=F',  # E-mini S&P 500 continuous
        'YM': 'YM=F',  # E-mini Dow continuous
        'RTY': 'RTY=F' # E-mini Russell 2000 continuous
    }
    
    def __init__(self):
        """Initialize Yahoo Finance loader."""
        print("📊 Yahoo Finance Loader initialized (FREE)")
        print("   ⚠️  For backtesting only - use MT5 feed for live trading")
    
    def fetch_historical_bars(
        self,
        symbol: str,
        period: str = "5d",
        interval: str = "1m"
    ) -> pd.DataFrame:
        """
        Fetch historical bars from Yahoo Finance.
        
        Args:
            symbol: "NQ", "ES", "YM", or "RTY"
            period: Time period ("1d", "5d", "1mo", "3mo", "1y", "2y")
            interval: Bar size ("1m", "5m", "15m", "1h", "1d")
        
        Returns:
            DataFrame with OHLCV data (EST timezone)
        
        Note:
            - 1m data limited to last 7 days
            - 5m data limited to last 60 days
            - Use larger intervals for longer lookbacks
        """
        # Convert our symbol to Yahoo symbol
        yahoo_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        
        print(f"📥 Fetching {symbol} data from Yahoo Finance...")
        print(f"   Period: {period}, Interval: {interval}")
        
        # Create ticker
        ticker = yf.Ticker(yahoo_symbol)
        
        # Fetch data
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            print(f"⚠️  No data returned for {symbol}")
            return df
        
        # Process data
        df = self._process_dataframe(df, symbol)
        
        print(f"✅ Fetched {len(df)} bars for {symbol}")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        
        return df
    
    def fetch_date_range(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """
        Fetch data for specific date range.
        
        Args:
            symbol: "NQ", "ES", "YM", or "RTY"
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            interval: Bar size
        
        Returns:
            DataFrame with OHLCV data
        """
        yahoo_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        
        print(f"📥 Fetching {symbol} from {start_date} to {end_date}...")
        
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(start=start_date, end=end_date, interval=interval)
        
        if df.empty:
            print(f"⚠️  No data returned")
            return df
        
        df = self._process_dataframe(df, symbol)
        
        print(f"✅ Fetched {len(df)} bars")
        
        return df
    
    def _process_dataframe(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Process raw Yahoo Finance data into standard format.
        
        Args:
            df: Raw DataFrame from yfinance
            symbol: Instrument symbol
        
        Returns:
            Processed DataFrame
        """
        # Rename columns to lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # Ensure we have required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Convert index to EST timezone
        if df.index.tz is None:
            # Yahoo returns UTC by default
            df.index = df.index.tz_localize('UTC')
        
        est = pytz.timezone('America/New_York')
        df.index = df.index.tz_convert(est)
        
        # Rename index
        df.index.name = 'timestamp'
        
        # Add symbol column
        df['symbol'] = symbol
        
        # Keep only OHLCV columns
        df = df[['symbol', 'open', 'high', 'low', 'close', 'volume']]
        
        # Remove any NaN rows
        df = df.dropna()
        
        # Sort by timestamp
        df = df.sort_index()
        
        return df
    
    def save_to_csv(self, df: pd.DataFrame, filename: str) -> None:
        """
        Save DataFrame to CSV file.
        
        Args:
            df: DataFrame to save
            filename: Output filename
        """
        df.to_csv(filename)
        print(f"💾 Saved data to {filename}")
    
    def load_from_csv(self, filename: str) -> pd.DataFrame:
        """
        Load DataFrame from CSV file.
        
        Args:
            filename: Input filename
        
        Returns:
            DataFrame
        """
        df = pd.read_csv(filename, index_col=0, parse_dates=True)
        
        # Ensure timezone is set
        if df.index.tz is None:
            est = pytz.timezone('America/New_York')
            df.index = df.index.tz_localize(est)
        
        print(f"📂 Loaded {len(df)} bars from {filename}")
        return df


# Example usage
if __name__ == "__main__":
    loader = YahooFinanceLoader()
    
    # Fetch 5 days of 1-minute NQ data
    print("\n" + "="*70)
    print("Fetching NQ data...")
    print("="*70)
    
    nq_data = loader.fetch_historical_bars("NQ", period="5d", interval="1m")
    
    if not nq_data.empty:
        print("\nSample data:")
        print(nq_data.head())
        print("\n...")
        print(nq_data.tail())
        
        # Save to file
        loader.save_to_csv(nq_data, "data/raw/nq_1min_yahoo.csv")
    
    # Fetch ES data
    print("\n" + "="*70)
    print("Fetching ES data...")
    print("="*70)
    
    es_data = loader.fetch_historical_bars("ES", period="5d", interval="1m")
    
    if not es_data.empty:
        print("\nSample ES data:")
        print(es_data.head())
        
        loader.save_to_csv(es_data, "data/raw/es_1min_yahoo.csv")
    
    print("\n" + "="*70)
    print("✅ Data fetch complete!")
    print("="*70)
    print("\nIMPORTANT:")
    print("- This data is FREE but may have gaps")
    print("- Good enough for backtesting v1.0")
    print("- For live trading, use MT5 feed (not Yahoo)")
    print("- Validate data with data_validator.py before backtesting")
