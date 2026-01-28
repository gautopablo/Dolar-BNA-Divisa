# AGENTS

Project: Dolar BNA Divisa

Primary goal
- Build and maintain a Python 3.x script that daily scrapes Banco Nación Argentina (BNA) public site for USD "Divisas" "Venta" and stores a historical time series.

Data source
- https://www.bna.com.ar/Personas
- Section: Cotización Divisas
- Currency: Dólar U.S.A
- Type: Venta

Data requirements
- Output table columns: fecha (YYYY-MM-DD), moneda (string e.g. "USD"), tipo (string e.g. "Venta"), valor (float)
- Validate the value exists before storing.
- Handle encoding and numeric formatting carefully (decimal separator).

Persistence
- Prefer CSV by default; allow Excel or SQLite as optional targets.
- Script must be idempotent (no duplicate date rows).

Robustness
- Handle HTTP errors, timeouts, and minor HTML changes.
- Basic logging (print or logging module).
- Detect no-update days (same value as prior date) and log it.

Implementation constraints
- Use only: requests, beautifulsoup4, pandas (plus Python stdlib).
- Avoid Selenium unless strictly necessary.

Automation
- Script should be runnable daily (cron/Task Scheduler).
- Provide clear CLI usage or configuration hints if needed.

Deliverables
- Complete executable Python script.
- Brief flow explanation and daily execution guidance.
