"""
IBKR Data Loader
================
Fetches historical 1-minute data for NQ and ES futures using ib_insync.
Handles contract specifications, data validation, and timezone conversion.
"""

from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import pytz


class IBKRLoader:
    """
    Loads historical data from Interactive Brokers.
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,  # 7497 = paper, 7496 = live
        client_id: int = 1
    ):
        """
        Initialize IBKR connection.
        
        Args:
            host: IB Gateway/TWS host
            port: IB Gateway/TWS port (7497 for paper, 7496 for live)
            client_id: Unique client ID
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.connected = False
        
    def connect(self) -> None:
        """Connect to IBKR."""
        if not self.connected:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            print(f"✅ Connected to IBKR at {self.host}:{self.port}")
    
    def disconnect(self) -> None:
        """Disconnect from IBKR."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            print("🔌 Disconnected from IBKR")
    
    def _get_contract(self, symbol: str, expiry: str = None) -> Future:
        """
        Get futures contract for symbol.
        
        Args:
            symbol: "NQ" or "ES"
            expiry: Contract month in YYYYMM format (e.g., "202503" for March 2025)
                   If None, will use front month
        
        Returns:
            ib_insync Future contract
        """
        if expiry is None:
            # Use front month - this is approximate, adjust as needed
            # For production, you'd want to handle roll logic properly
            now = datetime.now()
            # Use next quarterly month (Mar, Jun, Sep, Dec)
            quarters = [3, 6, 9, 12]
            next_quarter = min([m for m in quarters if m >= now.month], default=3)
            
            if next_quarter < now.month:
                # Roll to next year
                expiry = f"{now.year + 1}{next_quarter:02d}"
            else:
                expiry = f"{now.year}{next_quarter:02d}"
        
        contract = Future(symbol, expiry, 'CME')
        
        # Qualify contract with IBKR
        self.ib.qualifyContracts(contract)
        
        return contract
    
    def fetch_historical_bars(
        self,
        symbol: str,
        duration: str = "1 D",
        bar_size: str = "1 min",
        what_to_show: str = "TRADES",
        end_datetime: Optional[datetime] = None,
        expiry: str = None
    ) -> pd.DataFrame:
        """
        Fetch historical bars from IBKR.
        
        Args:
            symbol: "NQ" or "ES"
            duration: How far back to fetch (e.g., "1 D", "5 D", "1 W")
            bar_size: Bar size (e.g., "1 min", "5 mins", "1 hour")
            what_to_show: Data type ("TRADES", "MIDPOINT", "BID", "ASK")
            end_datetime: End time for historical data (default: now)
            expiry: Contract expiry (default: front month)
        
        Returns:
            DataFrame with OHLCV data
        """
        if not self.connected:
            self.connect()
        
        # Get contract
        contract = self._get_contract(symbol, expiry)
        
        # Set end datetime
        if end_datetime is None:
            end_datetime = datetime.now()
        
        # Fetch bars
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_datetime,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=False,  # Include extended hours
            formatDate=1
        )
        
        # Convert to DataFrame
        df = util.df(bars)
        
        if df.empty:
            print(f"⚠️  No data returned for {symbol}")
            return df
        
        # Process DataFrame
        df = self._process_dataframe(df, symbol)
        
        print(f"✅ Fetched {len(df)} bars for {symbol}")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        
        return df
    
    def _process_dataframe(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Process raw IBKR data into standardized format.
        
        Args:
            df: Raw DataFrame from ib_insync
            symbol: Instrument symbol
        
        Returns:
            Processed DataFrame
        """
        # Rename columns to standard OHLCV
        df = df.rename(columns={
            'date': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        # Set timestamp as index
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Convert to EST (all strategy logic in EST)
            est = pytz.timezone('America/New_York')
            df['timestamp'] = df['timestamp'].dt.tz_convert(est)
            
            df.set_index('timestamp', inplace=True)
        
        # Add symbol column
        df['symbol'] = symbol
        
        # Keep only OHLCV columns
        df = df[['symbol', 'open', 'high', 'low', 'close', 'volume']]
        
        # Sort by timestamp
        df.sort_index(inplace=True)
        
        return df
    
    def fetch_multiple_days(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        bar_size: str = "1 min"
    ) -> pd.DataFrame:
        """
        Fetch data for multiple days (IBKR has daily limits).
        
        Args:
            symbol: "NQ" or "ES"
            start_date: Start date
            end_date: End date
            bar_size: Bar size
        
        Returns:
            Combined DataFrame
        """
        all_data = []
        current_date = end_date
        
        while current_date >= start_date:
            # Fetch one day at a time
            df = self.fetch_historical_bars(
                symbol=symbol,
                duration="1 D",
                bar_size=bar_size,
                end_datetime=current_date
            )
            
            if not df.empty:
                all_data.append(df)
            
            # Move back one day
            current_date -= timedelta(days=1)
            
            # Be polite to IBKR servers
            self.ib.sleep(1)
        
        if not all_data:
            return pd.DataFrame()
        
        # Combine all data
        combined = pd.concat(all_data)
        combined.sort_index(inplace=True)
        
        # Remove duplicates
        combined = combined[~combined.index.duplicated(keep='first')]
        
        print(f"✅ Fetched {len(combined)} total bars for {symbol}")
        
        return combined
    
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
        print(f"📂 Loaded {len(df)} bars from {filename}")
        return df


# Example usage
if __name__ == "__main__":
    # Initialize loader
    loader = IBKRLoader(port=7497)  # Paper trading port
    
    try:
        # Connect
        loader.connect()
        
        # Fetch 5 days of NQ data
        nq_data = loader.fetch_historical_bars(
            symbol="NQ",
            duration="5 D",
            bar_size="1 min"
        )
        
        print("\nNQ Data Sample:")
        print(nq_data.head())
        print(nq_data.tail())
        
        # Save to file
        loader.save_to_csv(nq_data, "data/raw/nq_1min.csv")
        
        # Fetch ES data
        es_data = loader.fetch_historical_bars(
            symbol="ES",
            duration="5 D",
            bar_size="1 min"
        )
        
        print("\nES Data Sample:")
        print(es_data.head())
        
        # Save to file
        loader.save_to_csv(es_data, "data/raw/es_1min.csv")
        
    finally:
        # Always disconnect
        loader.disconnect()
