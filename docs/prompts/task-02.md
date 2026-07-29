# PROJECT CONTEXT

Project: AI Trading Operating System

Completed:

- Task 1 – Project Structure

---

# CURRENT TASK

Task 2 – Configuration System

## Objective

Build a production-grade configuration system for the Trading Operating System.

Create only the configuration layer.

### Requirements

- Python 3.12
- Pydantic v2
- pydantic-settings
- python-dotenv
- Type hints
- Validation
- Environment detection
- Cached settings
- Constants
- Environment-specific configuration

Create:

config/
    settings.py
    constants.py
    validators.py
    environment.py

Support:

- Development
- Testing
- Production

Do not implement trading logic.

Do not modify unrelated files.

Stop after Task 2.

---

## OUTPUT

Explain:

1. Why configuration is separated from business logic.
2. Why environment variables are used.
3. Why validation is important before the application starts.