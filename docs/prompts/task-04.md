# PROJECT CONTEXT

Project:
AI Trading Operating System

Completed

✅ Project Structure

✅ Configuration

✅ Documentation

Architecture Decision

The platform is exchange-agnostic.

The Trading Engine must never depend directly on Binance, Zerodha, or any broker.

Instead, every exchange must implement the same interface.

---------------------------------------

CURRENT TASK

Task 4

Build the Exchange Interface.

Objective

Create the abstraction that every exchange adapter must implement.

Create ONLY:

adapters/

    interfaces.py

Requirements

Python 3.12

Use abc.ABC

Use abstractmethod

Use dataclasses where appropriate

Type hints everywhere

Methods required

connect()

disconnect()

is_connected()

get_balance()

get_market_price()

place_order()

cancel_order()

get_order_status()

get_positions()

get_open_orders()

Do NOT implement the methods.

Only define the interface.

Include proper docstrings.

Do NOT create Binance code.

Do NOT create Zerodha code.

Do NOT create Paper Trading code.

Do NOT modify any existing files.

Stop after Task 4.

---------------------------------------

OUTPUT

Explain

Why interfaces exist

How Binance will use it

How Zerodha will use it

Why the Trading Engine never changes