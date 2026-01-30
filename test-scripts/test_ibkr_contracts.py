"""
IBKR Contract Tester
====================
Tests different contract specifications to find the correct one for NQ and ES.

Run this to verify your IBKR connection and find the right contract format.
"""

from ib_insync import *
import sys

print("="*70)
print("IBKR CONTRACT TESTER")
print("="*70)
print()

# Connect to IBKR
print("Step 1: Connecting to IBKR...")
ib = IB()

try:
    ib.connect('127.0.0.1', 7496, clientId=1)
    print("✅ Connected to IBKR (Paper Trading Port)\n")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Is TWS running?")
    print("2. Is API access enabled in TWS settings?")
    print("3. Is port 7497 (paper) or 7496 (live) correct?")
    sys.exit(1)

# ============================================================================
# Test 1: NQ with different exchange specifications
# ============================================================================

print("="*70)
print("TEST 1: NQ (E-mini Nasdaq 100)")
print("="*70)

# Method A: Try GLOBEX exchange (correct for e-minis)
print("\nMethod A: Using GLOBEX exchange...")
try:
    nq_globex = Future('NQ', '202503', 'GLOBEX')
    qualified = ib.qualifyContracts(nq_globex)
    
    if qualified:
        print("✅ SUCCESS with GLOBEX!")
        print(f"   Contract: {qualified[0]}")
        print(f"   Trading class: {qualified[0].tradingClass}")
        print(f"   Con ID: {qualified[0].conId}")
    else:
        print("❌ GLOBEX didn't work")
except Exception as e:
    print(f"❌ GLOBEX error: {e}")

# Method B: Try with empty exchange (let IBKR find it)
print("\nMethod B: Using SMART routing (empty exchange)...")
try:
    nq_smart = Future('NQ', '202503', 'SMART')
    qualified = ib.qualifyContracts(nq_smart)
    
    if qualified:
        print("✅ SUCCESS with SMART!")
        print(f"   Contract: {qualified[0]}")
        print(f"   Actual exchange: {qualified[0].exchange}")
    else:
        print("❌ SMART didn't work")
except Exception as e:
    print(f"❌ SMART error: {e}")

# Method C: Try just the symbol without specifying exchange
print("\nMethod C: Using symbol only (let IBKR determine)...")
try:
    # Create contract with minimal info
    nq_minimal = Future('NQ', '202503')
    qualified = ib.qualifyContracts(nq_minimal)
    
    if qualified:
        print("✅ SUCCESS with minimal specification!")
        print(f"   Contract: {qualified[0]}")
        print(f"   Exchange: {qualified[0].exchange}")
    else:
        print("❌ Minimal spec didn't work")
except Exception as e:
    print(f"❌ Minimal error: {e}")

# Method D: Try different contract month formats
print("\nMethod D: Trying different date formats...")

# IBKR sometimes wants YYYYMMDD format for last trade date
# March 2025 E-mini contracts typically expire 3rd Friday
# March 21, 2025 is the 3rd Friday
date_formats = [
    '202503',      # YYYYMM
    '20250321',    # YYYYMMDD (March 21, 2025 - 3rd Friday)
    '202503M',     # YYYYMMX (X = month code)
    'MAR25',       # Month code
]

for date_fmt in date_formats:
    try:
        nq_test = Future('NQ', date_fmt, 'GLOBEX')
        qualified = ib.qualifyContracts(nq_test)
        
        if qualified:
            print(f"✅ SUCCESS with date format: {date_fmt}")
            print(f"   Contract: {qualified[0]}")
            print(f"   Last trade date: {qualified[0].lastTradeDateOrContractMonth}")
            break
    except:
        pass
else:
    print("❌ None of the date formats worked")

# ============================================================================
# Test 2: ES (E-mini S&P 500) - same tests
# ============================================================================

print("\n" + "="*70)
print("TEST 2: ES (E-mini S&P 500)")
print("="*70)

print("\nTrying ES with GLOBEX exchange...")
try:
    es = Future('ES', '202503', 'GLOBEX')
    qualified = ib.qualifyContracts(es)
    
    if qualified:
        print("✅ ES SUCCESS with GLOBEX!")
        print(f"   Contract: {qualified[0]}")
    else:
        print("❌ ES with GLOBEX didn't work")
except Exception as e:
    print(f"❌ ES error: {e}")

# ============================================================================
# Test 3: Request contract details (most reliable method)
# ============================================================================

print("\n" + "="*70)
print("TEST 3: Search for NQ contracts (most reliable)")
print("="*70)

try:
    # This requests IBKR to tell us what NQ contracts exist
    contract = Contract()
    contract.symbol = 'NQ'
    contract.secType = 'FUT'
    contract.exchange = 'GLOBEX'
    contract.currency = 'USD'
    
    print("\nSearching for available NQ contracts...")
    details = ib.reqContractDetails(contract)
    
    if details:
        print(f"\n✅ Found {len(details)} NQ contracts!")
        print("\nShowing first 5 available contracts:")
        
        for i, detail in enumerate(details[:5]):
            c = detail.contract
            print(f"\n{i+1}. Symbol: {c.symbol}")
            print(f"   Last Trade Date: {c.lastTradeDateOrContractMonth}")
            print(f"   Trading Class: {c.tradingClass}")
            print(f"   Exchange: {c.exchange}")
            print(f"   Con ID: {c.conId}")
        
        # Find the front month (earliest expiry)
        front_month = sorted(details, key=lambda d: d.contract.lastTradeDateOrContractMonth)[0]
        print(f"\n📌 RECOMMENDED (Front Month):")
        print(f"   Use this contract: {front_month.contract}")
        print(f"   Expiry: {front_month.contract.lastTradeDateOrContractMonth}")
        
    else:
        print("❌ No NQ contracts found")
        
except Exception as e:
    print(f"❌ Search error: {e}")

# ============================================================================
# Test 4: Try to fetch historical data with correct contract
# ============================================================================

print("\n" + "="*70)
print("TEST 4: Fetch Historical Data (if contract found)")
print("="*70)

try:
    # Use the most reliable method: search first, then use the result
    contract = Contract()
    contract.symbol = 'NQ'
    contract.secType = 'FUT'
    contract.exchange = 'GLOBEX'
    contract.currency = 'USD'
    
    details = ib.reqContractDetails(contract)
    
    if details:
        # Use front month
        front_month = sorted(details, key=lambda d: d.contract.lastTradeDateOrContractMonth)[0]
        nq_contract = front_month.contract
        
        print(f"\nFetching 1 day of 1-minute bars for:")
        print(f"   {nq_contract.symbol} {nq_contract.lastTradeDateOrContractMonth}")
        
        bars = ib.reqHistoricalData(
            nq_contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=False,
            formatDate=1
        )
        
        if bars:
            print(f"\n✅ DATA FETCH SUCCESS!")
            print(f"   Received {len(bars)} bars")
            print(f"\n   First bar: {bars[0]}")
            print(f"   Last bar: {bars[-1]}")
        else:
            print("\n⚠️  No data returned (might be outside market hours)")
            
    else:
        print("❌ Could not find contract for data fetch")
        
except Exception as e:
    print(f"❌ Data fetch error: {e}")

# ============================================================================
# Summary and Recommendations
# ============================================================================

print("\n" + "="*70)
print("SUMMARY & RECOMMENDATIONS")
print("="*70)

print("""
Based on the tests above, here's what you should use:

FOR NQ (E-mini Nasdaq):
1. Exchange: GLOBEX (not CME)
2. Symbol: 'NQ'
3. Contract Month: Use the exact date from TEST 3 results
4. Or use the contract search method (most reliable)

RECOMMENDED CODE for data/ibkr_loader.py:

def _get_contract(self, symbol: str, expiry: str = None):
    '''Get futures contract by searching, not hardcoding.'''
    
    # Create search contract
    contract = Contract()
    contract.symbol = symbol
    contract.secType = 'FUT'
    contract.exchange = 'GLOBEX'  # ← Change from CME to GLOBEX
    contract.currency = 'USD'
    
    # Search for available contracts
    details = self.ib.reqContractDetails(contract)
    
    if not details:
        raise ValueError(f"No contracts found for {symbol}")
    
    # Sort by expiry, get front month
    front_month = sorted(details, 
                        key=lambda d: d.contract.lastTradeDateOrContractMonth)[0]
    
    return front_month.contract

This method is MUCH more reliable than hardcoding dates!
""")

# Disconnect
print("\nDisconnecting from IBKR...")
ib.disconnect()
print("✅ Disconnected\n")

print("="*70)
print("TEST COMPLETE")
print("="*70)
