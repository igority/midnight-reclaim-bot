from data.yahoo_loader import YahooFinanceLoader

loader = YahooFinanceLoader()
nq = loader.fetch_historical_bars('NQ', period='5d')

from data.data_validator import DataValidator

validator = DataValidator()
results = validator.validate(nq, 'NQ')
validator.print_report(results)