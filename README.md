# Multi-Confirmation False Breakout Reversal Bot v1.0

**Status:** 🔒 FROZEN - No modifications until 50 live trades completed  
**Frozen Date:** January 30, 2025

---

## 📋 Overview

Automated intraday trading system exploiting liquidity-driven false breakouts around the New York session open.

### Core Strategy Elements
- **Anchor:** Midnight Open (00:00 EST)
- **Setup:** False breakout + SMT divergence + fast reclaim
- **Filters:** ONS range, displacement (ISI), time windows
- **Risk:** Fixed R per trade, 50% partial at 1R, trail remainder

### Key Principles
- **Selectivity over frequency:** 0-1 trades/day maximum
- **Failure avoidance:** Multiple confirmation filters
- **Debuggability:** Comprehensive logging, clear state machine
- **No optimization:** v1.0 parameters frozen until 50 trades

---

## 🎯 Expected Performance (Realistic)

| Metric | Target |
|--------|--------|
| Win Rate | 58-65% |
| Avg R-Multiple | 1.3-1.6 |
| Trades/Week | 2-5 |
| Max Drawdown | 8-15% |

**Note:** Any claims of 80% win rate are marketing, not engineering.

---

## 🏗️ Project Structure

```
midnight_reclaim_bot/
├── config/              # Frozen configuration files
│   ├── v1_params.yaml
│   └── instrument_specs.yaml
├── data/                # Data storage and loaders
│   ├── raw/
│   ├── processed/
│   └── ibkr_loader.py
├── core/                # Strategy core logic (Sprint 2-4)
│   ├── state_machine.py
│   ├── indicators.py
│   ├── strategy.py
│   └── position.py
├── utils/               # Utilities
│   ├── config_loader.py
│   ├── time_utils.py
│   └── helpers.py
├── logging/             # Dual logging system
│   ├── schemas.py
│   ├── logger.py
│   └── logs/
├── backtest/            # Backtesting engine (Sprint 6)
├── tests/               # Unit tests
└── main.py              # Entry point
```

---

## 🚀 Setup Instructions

### 1. Environment Setup

```bash
# Clone/create project directory
mkdir midnight_reclaim_bot
cd midnight_reclaim_bot

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. IBKR Setup

#### Download TWS or IB Gateway
- **TWS (Trader Workstation):** Full GUI, good for development
- **IB Gateway:** Lightweight, headless, good for production
- Download: https://www.interactivebrokers.com/en/trading/tws.php

#### Configure API Access
1. Open TWS/Gateway
2. Go to: **File → Global Configuration → API → Settings**
3. Enable these settings:
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Read-Only API
   - ✅ Download open orders on connection
4. Set socket port:
   - **7497** for paper trading
   - **7496** for live trading
5. Add trusted IP: `127.0.0.1`

#### Test Connection

```python
# test_connection.py
from data.ibkr_loader import IBKRLoader

loader = IBKRLoader(port=7497)  # Paper trading
loader.connect()
print("✅ Connected successfully!")
loader.disconnect()
```

### 3. Configuration

All parameters are in `config/v1_params.yaml`.

**⚠️ DO NOT MODIFY until 50 trades completed!**

Key parameters:
- Trading window: 09:30-10:30 EST
- Max trades/session: 1
- ONS filter: 30-70% of ADR
- Reclaim timeout: 45 minutes
- Risk: 1R target, 50% partial at TP1

---

## 📊 Data Management

### Fetch Historical Data

```python
from data.ibkr_loader import IBKRLoader

loader = IBKRLoader(port=7497)
loader.connect()

# Fetch 5 days of 1-minute data
nq_data = loader.fetch_historical_bars("NQ", duration="5 D")
es_data = loader.fetch_historical_bars("ES", duration="5 D")

# Save to CSV
loader.save_to_csv(nq_data, "data/raw/nq_1min.csv")
loader.save_to_csv(es_data, "data/raw/es_1min.csv")

loader.disconnect()
```

### Load from CSV (for backtesting)

```python
loader = IBKRLoader()
nq_data = loader.load_from_csv("data/raw/nq_1min.csv")
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_indicators.py
```

---

## 📝 Logging System

### Dual Logging Architecture

1. **Event Log** (`logs/events/`)
   - High frequency (every state change)
   - Contains: price data, indicators, SMT values, ISI, state transitions
   - Used for: debugging, understanding market conditions

2. **Trade Log** (`logs/trades/`)
   - One row per trade (REAL and SHADOW)
   - Contains: entry/exit, P&L, R-multiples, setup quality
   - Used for: performance analysis, v1.5 evolution

3. **No-Trade Log** (`logs/no_trades/`)
   - Tracks rejected setups
   - Contains: rejection reasons, context at rejection
   - Used for: understanding filter effectiveness

### Shadow Trades (One-Filter-Failed)

**What are shadow trades?**
- Setups that passed ALL core filters
- Failed EXACTLY ONE gating filter
- Logged with same entry/exit logic as real trades
- Used to evaluate filter effectiveness

**CRITICAL RULES:**
1. ⛔ Shadow trades NEVER affect live decisions
2. ⛔ Shadow performance NOT reviewed until 50 REAL trades
3. ✅ Shadow trades use SAME exit logic as real trades
4. ✅ Only one-filter-failed setups are logged

**Why shadow trades?**
After 50 real trades, they help answer:
- "How many trades did SMT block that would have won?"
- "Are late reclaims actually bad, or just noisy?"
- "Which filter has the highest opportunity cost?"

**See:** `SHADOW_TRADE_DISCIPLINE.txt` for full psychological guardrail.

### Log Fields Reference

See `logging/schemas.py` for complete field definitions.

---

## 🎓 Development Roadmap

### ✅ Sprint 1: Foundation (COMPLETE)
- [x] Project structure
- [x] Configuration system
- [x] Time utilities
- [x] Logging schemas
- [x] IBKR data loader

### 📍 Sprint 2: Indicators (NEXT)
- [ ] Midnight Open calculator
- [ ] ONS filter (overnight range vs ADR)
- [ ] ADR calculator
- [ ] ISI (Impulse Strength Index)
- [ ] SMT detector (binary + degree logging)

### Sprint 3: State Machine
- [ ] State enum and transitions
- [ ] State validation
- [ ] State history tracking

### Sprint 4: Strategy Core
- [ ] Deviation detection
- [ ] SMT confirmation
- [ ] Reclaim detection
- [ ] Entry signal generation

### Sprint 5: Execution & Risk
- [ ] Position management
- [ ] Entry logic
- [ ] Stop placement
- [ ] TP1 + runner exits

### Sprint 6: Backtesting
- [ ] Backtrader integration
- [ ] Run on historical data
- [ ] Generate logs
- [ ] Sanity checks

### Sprint 7: Validation & Documentation
- [ ] Edge case testing
- [ ] State transition validation
- [ ] Documentation updates
- [ ] Ready for paper trading

---

## ⚠️ Hard Rules (Enforced by Code)

1. ❌ **No parameter optimization** in v1.0
2. ❌ **No logic changes** before 50 live trades
3. ❌ **No adding instruments** (NQ only)
4. ❌ **No discretionary overrides**
5. ✅ **Must log everything**
6. ✅ **Max 1 trade per session**

---

## 🔬 Evolution to v1.5 and Beyond

**v1.5 (After 50-100 Trades):**
- SMT degree thresholds (if data supports it)
- ATR-based volatility regime filter
- Adaptive reclaim windows
- Secondary instrument (ES)

**v2.0 (After Proven Stability):**
- VIX regime classification
- Gap classification
- Multi-mode exits
- ML-based regime clustering (if needed)

**Evolution principle:** Let FAILURE DATA dictate upgrades, not theory.

---

## 📞 Support & Feedback

### Key Files to Understand
1. `config/v1_params.yaml` - All strategy parameters
2. `logging/schemas.py` - Log data structures
3. `utils/time_utils.py` - Timezone handling
4. `data/ibkr_loader.py` - Data fetching

### Common Issues

**Issue:** Can't connect to IBKR  
**Fix:** Ensure TWS/Gateway is running and API is enabled

**Issue:** No data returned  
**Fix:** Check contract expiry, ensure market is open, verify symbol

**Issue:** Timezone confusion  
**Fix:** All strategy logic in EST, IBKR data auto-converted

---

## 📜 License

Private project. Not for distribution.

---

## 🙏 Acknowledgments

Developed through structured multi-agent collaboration:
- Agent 1: Core strategy concept
- Agent 2: Rigor and architecture
- Agent 3: Risk management and reality checks

**Final architecture:** 70% Agent 2 rigor + 30% Agent 1 simplicity + Agent 3 discipline

---

**Remember:** The goal is not perfection, it's **survivability and debuggability**.

Build simple. Trade disciplined. Evolve from data.

🚀 Let's build something that actually works.
