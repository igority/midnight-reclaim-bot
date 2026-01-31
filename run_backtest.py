from backtest.backtest_runner import BacktestRunner
runner = BacktestRunner(debug=True)
cerebro = runner.run(period='5d')