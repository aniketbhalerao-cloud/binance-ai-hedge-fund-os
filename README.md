# 🚀 AI Trading Operating System

![Python](https://img.shields.io/badge/Python-3.14-blue)
![Tests](https://img.shields.io/badge/Tests-215%20Passing-success)
![Architecture](https://img.shields.io/badge/Architecture-Clean-blueviolet)
![License](https://img.shields.io/badge/License-MIT-green)

---

# Overview

AI Trading Operating System is a modular, event-driven algorithmic trading platform built using Clean Architecture, Domain-Driven Design (DDD), and Dependency Injection.

The platform separates every trading responsibility into independent frameworks that communicate through standardized domain models and an Event Bus.

The architecture is designed to support:

- Cryptocurrency Trading
- Equity Trading
- Multi-Broker Integration
- AI Trading Agents
- Paper Trading
- Backtesting
- Live Trading
- Portfolio Analytics

without changing existing frameworks.

---

# Architecture

```
                    Market Data Framework
                            │
                            ▼
                     Trading Engine
                            │
                            ▼
                  Strategy Framework
                            │
                            ▼
                    Risk Framework
                            │
                            ▼
              Order Management Framework
                            │
                            ▼
                 Execution Framework
                            │
                            ▼
            Exchange Adapter Framework
                            │
                            ▼
                 Binance Spot Adapter
                            │
                            ▼
             Portfolio Management Framework
                            │
                            ▼
             Position Management Framework
                            │
                            ▼
              Trade Lifecycle Framework
```

---

# Project Structure

```
core/
market_data/
strategies/
risk/
order_management/
execution/
exchange_adapters/
adapters/
portfolio/
positions/
trades/
tests/
docs/
```

---

# Frameworks Completed

| Version | Framework | Status |
|----------|-----------|--------|
| v1.0 | Core Infrastructure | ✅ |
| v2.3 | Strategy Framework | ✅ |
| v2.4 | Risk Framework | ✅ |
| v2.5 | Order Management | ✅ |
| v3.0 | Execution Framework | ✅ |
| v3.1 | Exchange Adapter Framework | ✅ |
| v3.2 | Binance Spot Adapter | ✅ |
| v3.3 | Portfolio Management | ✅ |
| v3.4 | Position Management | ✅ |
| v3.5 | Trade Lifecycle Framework | ✅ |

---

# Features

- Event-Driven Architecture
- Dependency Injection
- Thread-Safe Components
- Exchange Independence
- Immutable Domain Models
- Structured Logging
- Clean Architecture
- Domain Driven Design
- Modular Frameworks
- Extensive Automated Testing

---

# Technology Stack

- Python 3.14
- Pytest
- Dependency Injection
- Event Bus
- HMAC SHA256
- Binance Spot API
- Clean Architecture
- SOLID Principles

---

# Running the Project

Clone the repository:

```bash
git clone https://github.com/aniketbhalerao-cloud/binance-ai-hedge-fund-os.git

cd binance-ai-hedge-fund-os
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Expected output:

```
215 passed
```

---

# Documentation

Architecture Decision Records (ADR):

```
docs/architecture/decisions/
```

Task Reviews:

```
docs/reviews/
```

Development Prompts:

```
docs/prompts/
```

---

# Project Statistics

Current Version:

**v3.5 – Trade Lifecycle Framework**

Frameworks:

- 10 Major Frameworks

Automated Tests:

- **215 Passing Tests**

Architecture:

- Event Driven
- Clean Architecture
- Domain Driven Design
- Dependency Injection

---

# Roadmap

Upcoming milestones:

- Performance Analytics Framework
- Backtesting Framework
- Paper Trading Framework
- AI Decision Engine
- Live Trading Orchestrator

---

# License

MIT License

---

# Author

**Aniket Bhalerao**

GitHub:

https://github.com/aniketbhalerao-cloudgit status