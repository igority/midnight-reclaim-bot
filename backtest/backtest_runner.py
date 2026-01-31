"""
Backtest Runner
===============
Runs backtests using Backtrader framework.

This is the entry point for running historical backtests.
"""

import backtrader as bt
from datetime import datetime
import pandas as pd

from backtest.bt_strategy import MidnightReclaimStrategy
from data.yahoo_loader import YahooFinanceLoader
from utils.config_loader import Config


class BacktestRunner:
    """
    Executes backtests using Backtrader.
    """
    
    def __init__(
        self,
        starting_capital: float = 100000.0,
        risk_per_trade_pct: float = 0.01,
        debug: bool = True
    ):
        """
        Initialize backtest runner.
        
        Args:
            starting_capital: Starting account size
            risk_per_trade_pct: Risk per trade as % of account
            debug: Print debug messages
        """
        self.starting_capital = starting_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.debug = debug
        
        # Initialize config
        Config.initialize()
        
        print("="*70)
        print("BACKTEST RUNNER INITIALIZED")
        print("="*70)
        print(f"Starting capital: ${starting_capital:,.2f}")
        print(f"Risk per trade: {risk_per_trade_pct:.1%}")
        print("="*70)
    
    def run(
        self,
        period: str = "30d",
        instruments: list = None
    ) -> bt.Cerebro:
        """
        Run backtest.
        
        Args:
            period: Yahoo Finance period ("5d", "30d", etc.)
            instruments: List of instruments (default: ['NQ', 'ES'])
        
        Returns:
            Cerebro instance with results
        """
        if instruments is None:
            instruments = ['NQ', 'ES']
        
        print(f"\n{'='*70}")
        print(f"LOADING DATA")
        print(f"{'='*70}")
        
        # Load data
        loader = YahooFinanceLoader()
        
        data_feeds = {}
        for symbol in instruments:
            print(f"Fetching {symbol} data ({period})...")
            df = loader.fetch_historical_bars(symbol, period=period, interval='1m')
            
            if df.empty:
                raise ValueError(f"No data for {symbol}")
            
            print(f"  {symbol}: {len(df)} bars ({df.index[0]} to {df.index[-1]})")
            data_feeds[symbol] = df
        
        print(f"\n{'='*70}")
        print(f"INITIALIZING BACKTEST")
        print(f"{'='*70}")
        
        # Create Cerebro
        cerebro = bt.Cerebro()
        
        # Add strategy
        cerebro.addstrategy(
            MidnightReclaimStrategy,
            account_size=self.starting_capital,
            risk_per_trade_pct=self.risk_per_trade_pct,
            debug=self.debug
        )
        
        # Add data feeds
        for i, (symbol, df) in enumerate(data_feeds.items()):
            data = bt.feeds.PandasData(
                dataname=df,
                name=symbol
            )
            cerebro.adddata(data)
            print(f"Added data feed: {symbol}")
        
        # Set broker
        cerebro.broker.setcash(self.starting_capital)
        cerebro.broker.setcommission(commission=0.0)  # Set commission if needed
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        print(f"Starting portfolio value: ${cerebro.broker.getvalue():,.2f}")
        
        # Run
        print(f"\n{'='*70}")
        print(f"RUNNING BACKTEST")
        print(f"{'='*70}\n")
        
        results = cerebro.run()
        
        # Print results
        print(f"\n{'='*70}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*70}")
        
        final_value = cerebro.broker.getvalue()
        pnl = final_value - self.starting_capital
        return_pct = (pnl / self.starting_capital) * 100
        
        print(f"\n💰 ACCOUNT")
        print(f"   Starting: ${self.starting_capital:,.2f}")
        print(f"   Ending: ${final_value:,.2f}")
        print(f"   P&L: ${pnl:+,.2f}")
        print(f"   Return: {return_pct:+.2f}%")
        
        # Analyzer results
        strat = results[0]
        
        # Sharpe
        try:
            sharpe = strat.analyzers.sharpe.get_analysis()
            if sharpe and 'sharperatio' in sharpe:
                print(f"\n📊 METRICS")
                print(f"   Sharpe Ratio: {sharpe['sharperatio']:.2f}")
        except:
            pass
        
        # Drawdown
        try:
            dd = strat.analyzers.drawdown.get_analysis()
            if dd:
                print(f"   Max Drawdown: {dd.max.drawdown:.2f}%")
        except:
            pass
        
        # Trades
        try:
            trades = strat.analyzers.trades.get_analysis()
            if trades and 'total' in trades:
                total = trades.total.total if hasattr(trades.total, 'total') else 0
                won = trades.won.total if hasattr(trades, 'won') and hasattr(trades.won, 'total') else 0
                lost = trades.lost.total if hasattr(trades, 'lost') and hasattr(trades.lost, 'total') else 0
                
                print(f"\n📈 TRADES")
                print(f"   Total: {total}")
                print(f"   Won: {won}")
                print(f"   Lost: {lost}")
                if total > 0:
                    win_rate = (won / total) * 100
                    print(f"   Win Rate: {win_rate:.1f}%")
        except:
            pass
        
        print(f"\n{'='*70}\n")
        
        return cerebro


# Example usage
if __name__ == "__main__":
    # Create runner
    runner = BacktestRunner(
        starting_capital=100000.0,
        risk_per_trade_pct=0.01,
        debug=True
    )
    
    # Run backtest
    try:
        cerebro = runner.run(period='5d')
        
        # Optionally plot
        # cerebro.plot()
        
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
