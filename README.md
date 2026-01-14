# 🔐 Alpha Locks and Safe - Technician Reports

A commission calculation and report generation system for locksmith technicians.

## 📋 Overview

This system automatically calculates technician commissions based on:
- Commission rate (percentage)
- Parts cost
- Payment method (Cash, Credit Card, Check, Bank Transfer)

## 💰 Commission Logic

### When customer pays CASH to technician:
```
Tech Profit = (Total - Parts) × Commission Rate
Balance = Total - Parts - Tech Profit  (Tech brings this to company)
```

**Example:** $1000 job, $50 parts, 50% commission
- Tech Profit: (1000 - 50) × 50% = **$475**
- Balance to bring: $1000 - $50 - $475 = **$475**

### When customer pays COMPANY (CC/Check/Transfer):
```
Tech Payment = (Total - Parts) × Commission Rate + Parts
Balance = negative (Company owes tech)
```

**Example:** $1000 CC payment, $50 parts, 50% commission
- Tech receives: (1000 - 50) × 50% + 50 = $475 + $50 = **$525**

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Web Interface
```bash
streamlit run app.py
```

### 3. Open in Browser
Navigate to `http://localhost:8501`

---

## 📊 Features

- ✅ **Web Interface** - Easy-to-use Streamlit app
- ✅ **Paste Messages** - Parse job closure messages automatically
- ✅ **Labeled Format Support** - Parse messages with labels (Addr:, Ph:, Desc:, date:, Total cash:)
- ✅ **Excel Import** - Upload job data from Excel/CSV files
- ✅ **Manual Entry** - Add jobs one by one
- ✅ **HTML Reports** - Beautiful reports styled like professional invoices
- ✅ **Excel Export** - Download data as Excel spreadsheet
- ✅ **Auto Calculation** - Instant commission and balance calculations
- ✅ **Summary View** - Total jobs, sales, profit, and balance at a glance

---

## 📋 Supported Message Formats

### Format 1: Labeled Format (New!)
```
date:1/5/26
Ph: 9175003599
Addr: 36 N Goodwin Ave, Elmsford, NY, 10523
Desc: Home Lockout
Occu: Locksmith

Total cash:510$
```

### Format 2: Standard Format
```
36 N Goodwin Ave, Elmsford, NY 10523
Home Lockout
(917) 500-3599
alpha job
$510
Parts $15
```

### Format 3: Simple Format
```
123 Main St, New York, NY 10001
Total cash 450
Parts 20
```

---

## 📁 Project Structure

```
alpha-locks-reports/
├── app.py                 # Streamlit web interface
├── main.py                # CLI interface
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── src/
│   ├── models.py          # Data models (Job, Technician, JobResult)
│   ├── calculator.py      # Commission calculation logic
│   ├── report_generator.py # Excel report generation
│   ├── html_exporter.py   # HTML report generation
│   └── data_loader.py     # Excel/CSV data loading
├── data/
│   ├── technicians.json   # Technician list
│   └── jobs/              # Job data files
├── output/
│   └── reports/           # Generated reports
└── tests/
    └── test_calculator.py # Unit tests
```

---

## 📥 Input File Format

Excel or CSV with these columns:

| Column | Description | Required |
|--------|-------------|----------|
| Date | Job date (YYYYMMDD) | Optional |
| Address | Job location | Yes |
| Total | Total job amount | Yes |
| Parts | Parts cost | Optional |
| Cash | Cash payment amount | * |
| CC | Credit card amount | * |
| Check | Check amount | * |
| % | Commission rate | Optional |
| FEE | Processing fee | Optional |

*At least one payment method required

---

## 📄 Report Output

### HTML Report
Beautiful, print-ready report with:
- Company name and technician name header
- Date range
- Detailed job table
- Color-coded summary row (cyan)
- Formatted currency values

### Excel Report
Spreadsheet with:
- Same data as HTML
- Proper column formatting
- Summary row with totals

---

## 🖥️ CLI Usage

```bash
python main.py jobs.xlsx --technician "John Doe" --commission 0.5
```

Options:
- `-t, --technician` - Technician name (required)
- `-c, --commission` - Commission rate (default: 0.5)
- `-o, --output` - Output file path

---

## ⚙️ Configuration

Edit `config.py` to customize:

```python
COMPANY_NAME = "Alpha Locks and Safe"
DEFAULT_COMMISSION_RATE = 0.50  # 50%

# Payment methods that go to company
COMPANY_PAYMENT_METHODS = ['cc', 'check', 'transfer']
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

All 8 tests should pass ✅

---

## 📝 License

Private - Alpha Locks and Safe

---

Made with ❤️ for NYC locksmiths
