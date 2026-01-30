# IBKR Connection Troubleshooting Guide

## ✅ Your Issue: "No security definition has been found"

**What it means:** The contract specification is wrong.

**The fix:** Use GLOBEX exchange, not CME.

---

## 🔧 Quick Fix

### **Step 1: Run the Contract Tester**

```bash
cd test-scripts
python test_ibkr_contracts.py
```

This will:
- Test different contract specifications
- Find the correct format for NQ and ES
- Show you available contract months
- Test data fetching

### **Step 2: Use the Results**

The tester will tell you exactly which contract format works.

---

## 📋 Common IBKR Issues

### Issue 1: "No security definition has been found"

**Symptoms:**
```
Error 200: No security definition has been found for the request
```

**Causes:**
- Wrong exchange (CME vs GLOBEX)
- Wrong contract month format
- Symbol doesn't exist
- No market data subscription

**Fix:**
- E-mini futures (NQ, ES) use **GLOBEX**, not CME
- Use contract search instead of hardcoding
- Verify market data subscription in TWS

### Issue 2: "Not connected"

**Symptoms:**
```
ConnectionRefusedError: [Errno 10061] No connection could be made
```

**Causes:**
- TWS/Gateway not running
- Wrong port (7497 vs 7496)
- API not enabled

**Fix:**
1. Start TWS or IB Gateway
2. Check port: 7497 (paper), 7496 (live)
3. File → Global Configuration → API → Settings
4. Check "Enable ActiveX and Socket Clients"

### Issue 3: "Historical Market Data Service error"

**Symptoms:**
```
Error 162: Historical Market Data Service error message
```

**Causes:**
- No market data subscription
- Requesting too much data
- Rate limit hit
- Outside market hours (some data types)

**Fix:**
- Verify you have market data subscription
- Use smaller time ranges
- Add delays between requests (`ib.sleep(1)`)
- Try `useRTH=False` for 24-hour data

### Issue 4: Empty data returned

**Symptoms:**
```python
bars = []  # Empty list
```

**Causes:**
- Market closed
- Wrong contract specification
- No data for that period
- Subscription issue

**Fix:**
- Check if market is open
- Verify contract with `reqContractDetails`
- Try a different time period
- Use `whatToShow='TRADES'` for futures

### Issue 5: "Client ID already in use"

**Symptoms:**
```
Error 326: Unable to connect as the client id is already in use
```

**Causes:**
- Previous connection not closed
- Another process using same client ID

**Fix:**
- Use different `clientId` parameter
- Close all connections: `ib.disconnect()`
- Restart TWS/Gateway if stuck

---

## 🎯 Best Practices

### 1. **Always Use Contract Search**

❌ **Bad (hardcoded):**
```python
contract = Future('NQ', '202503', 'CME')
```

✅ **Good (search):**
```python
contract = Contract()
contract.symbol = 'NQ'
contract.secType = 'FUT'
contract.exchange = 'GLOBEX'

details = ib.reqContractDetails(contract)
front_month = sorted(details, key=lambda d: d.contract.lastTradeDateOrContractMonth)[0]
nq = front_month.contract
```

### 2. **Handle Errors Gracefully**

```python
try:
    bars = ib.reqHistoricalData(...)
    if not bars:
        print("No data returned - might be outside market hours")
except Exception as e:
    print(f"Error: {e}")
```

### 3. **Add Delays**

```python
# When fetching multiple days
for day in days:
    data = fetch_data(day)
    ib.sleep(1)  # Be polite to IBKR servers
```

### 4. **Cache Data Locally**

```python
# Fetch once, save to CSV
data = loader.fetch_historical_bars('NQ', duration='30 D')
loader.save_to_csv(data, 'data/raw/nq_1min.csv')

# Then load from CSV for backtesting
data = pd.read_csv('data/raw/nq_1min.csv')
```

---

## 🔍 Debugging Checklist

When IBKR connection fails, check in this order:

1. ✅ Is TWS/Gateway running?
2. ✅ Is API enabled in settings?
3. ✅ Is port correct (7497 paper, 7496 live)?
4. ✅ Is 127.0.0.1 in trusted IPs?
5. ✅ Do you have market data subscription?
6. ✅ Is the contract specification correct?
7. ✅ Is the market open (or use useRTH=False)?

---

## 📞 Still Not Working?

### Check IBKR Logs

TWS generates logs in:
```
C:\Jts\<version>\log
```

Look for errors related to API connections.

### Verify Market Data

In TWS:
- Account → Market Data Subscriptions
- Ensure you have "US Equity and Options" or equivalent

### Test with Simple Example

```python
from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

# Test with a stock (simpler than futures)
contract = Stock('AAPL', 'SMART', 'USD')
ib.qualifyContracts(contract)

print(f"Contract: {contract}")

ib.disconnect()
```

If this works, the issue is with futures contract specification.

---

## 📚 Useful Resources

- **ib_insync docs:** https://ib-insync.readthedocs.io/
- **IBKR API:** https://interactivebrokers.github.io/tws-api/
- **Contract specifications:** Search "NQ futures contract specs"

---

## ✅ Next Steps After Fixing

Once you can successfully fetch data:

1. Run `test_ibkr_contracts.py` to verify
2. Fetch 5-10 days of NQ and ES data
3. Validate with `data/data_validator.py`
4. Save to CSV for backtesting
5. Ready for Sprint 2!

---

**Most common fix: Change 'CME' to 'GLOBEX' in contract specification.**
