# test_ibkr_connection.py
from ib_insync import *

# Connect to IBKR
ib = IB()
ib.connect('127.0.0.1', 7496, clientId=1)  # 7497 = paper trading

# Test: Request NQ contract
nq = Future('NQ', '202503', 'CME')  # March 2025 contract
ib.qualifyContracts(nq)

print(f"Connected! Contract: {nq}")

# Disconnect
ib.disconnect()