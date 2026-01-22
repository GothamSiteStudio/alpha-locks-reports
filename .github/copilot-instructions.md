# GitHub Copilot Instructions for Alpha Reports

This project is a Streamlit-based application for managing locksmith technician reports and calculating commissions. It parses unstructured job messages, stores them in JSON files, and generates financial reports.

## Architecture & Core Concepts

- **Framework**: Streamlit (`app.py` is the entry point).
- **Data Storage**: File-based JSON storage in the `data/` directory.
  - `data/stored_jobs.json`: Main database of jobs.
  - `data/technicians.json`: Technician storage.
- **Domain Models** (`src/models.py`, `src/job_storage.py`):
  - `ParsedJob`: Transient object from message parsing.
  - `Job`: Core business object for calculations.
  - `StoredJob`: Persistent object with metadata (ID, timestamps).
  - `Technician`: Stores tech details and commission rates.

## Critical Workflows

- **Run Application**:
  ```bash
  streamlit run app.py
  ```
- **Authentication**: Simple username/password check in `auth_config.py`.
- **Parsing Logic**: The system relies heavily on `src/message_parser.py` to interpret "messy" human-written job messages (WhatsApp/SMS).

## Project Conventions

### Data Handling
- **Currency**: Use `float` for monetary values (note: `models.py` imports Decimal but uses `float` in dataclasses).
- **Date Handling**: Store dates as ISO 8601 strings (`YYYY-MM-DD`) in JSON, convert to `datetime.date` objects in memory.
- **Persistence**: Any changes to data structure must be reflected in `JobStorage` methods to ensure `stored_jobs.json` integrity.

### Commission Logic
Calculations differ based on payment method (defined in `README.md` and logic files):
- **CASH**: Tech keeps (Total - Parts) * Rate. Company gets the rest.
- **COMPANY (CC/Check)**: Tech gets (Total - Parts) * Rate + Parts. Company owes tech.

### UI/UX Pattern
- Use `st.session_state` for maintaining state across reruns (e.g., login status, current parsed messages).
- Separate logic (`src/`) from UI (`app.py` and other pages).

## Key Files
- `app.py`: Main Streamlit app and page routing.
- `src/message_parser.py`: Regex-heavy parsing logic.
- `src/job_storage.py`: CRUD operations for JSON files.
- `src/models.py`: Dataclasses for strict typing.

## New Feature Instructions
- When adding UI components, check `st.session_state` for required initialization.
- When modifying the parser, ensure both "Standard" and "Labeled" formats (see `README.md`) are supported.
- Always include type hints for new functions.
