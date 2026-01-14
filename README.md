# Alpha Locks and Safe - Technician Reports System

## 📋 תיאור הפרויקט

מערכת ליצירת דוחות עמלות לטכנאים של Alpha Locks and Safe.

המערכת מחשבת אוטומטית את החלוקה בין החברה לטכנאי לפי:
- אחוז העמלה של הטכנאי
- עלות החלקים
- אמצעי התשלום (מזומן/אשראי/צ'ק/העברה בנקאית)

---

## 💰 לוגיקת החישוב

### כאשר הלקוח משלם במזומן לטכנאי:
```
רווח_טכנאי = (סכום_עבודה - חלקים) × אחוז_עמלה
באלנס_להבאה = סכום_עבודה - חלקים - רווח_טכנאי
```

**דוגמה:** עבודה ב-$1000, חלקים $50, עמלה 50%
- רווח טכנאי: (1000 - 50) × 50% = $475
- באלנס להבאה לחברה: $1000 - $50 - $475 = **$475**

### כאשר הלקוח משלם לחברה (אשראי/צ'ק/העברה):
```
תשלום_לטכנאי = (סכום_עבודה - חלקים) × אחוז_עמלה + חלקים
באלנס = -תשלום_לטכנאי (החברה חייבת לטכנאי)
```

**דוגמה:** עבודה ב-$1000, חלקים $50, עמלה 50%
- תשלום לטכנאי: (1000 - 50) × 50% + 50 = $475 + $50 = **$525**

---

## 🏗️ מבנה הפרויקט

```
alpha-locks-reports/
├── README.md
├── requirements.txt
├── config.py              # הגדרות (אחוזי עמלה, שמות טכנאים)
├── src/
│   ├── __init__.py
│   ├── models.py          # מודלים: Job, Technician, Report
│   ├── calculator.py      # לוגיקת חישוב העמלות
│   ├── report_generator.py # יצירת הדוחות
│   └── excel_exporter.py  # ייצוא ל-Excel
├── templates/
│   └── report_template.xlsx
├── data/
│   ├── jobs/              # קבצי עבודות (CSV/Excel)
│   └── technicians.json   # רשימת טכנאים
├── output/
│   └── reports/           # דוחות שנוצרו
└── tests/
    └── test_calculator.py
```

---

## 📊 מבנה הדוח

| עמודה | תיאור |
|-------|-------|
| Date | תאריך העבודה |
| Address | כתובת העבודה |
| % | אחוז העמלה של הטכנאי |
| Total | סכום העבודה הכולל |
| Parts | עלות חלקים |
| Cash | תשלום במזומן |
| CC | תשלום באשראי |
| Check | תשלום בצ'ק |
| FEE | עמלת סליקה |
| Tech Profit | רווח הטכנאי |
| Balance | באלנס (+ טכנאי חייב / - חברה חייבת) |

---

## 🚀 תוכנית עבודה

### שלב 1: תשתית בסיסית ✅
- [x] יצירת Repository
- [ ] הקמת מבנה תיקיות
- [ ] הגדרת dependencies (pandas, openpyxl)

### שלב 2: לוגיקה עסקית
- [ ] מודל Job - ייצוג עבודה בודדת
- [ ] מודל Technician - פרטי טכנאי ואחוז עמלה
- [ ] Calculator - חישוב עמלות ובאלנס

### שלב 3: קלט נתונים
- [ ] קריאת נתונים מ-Excel/CSV
- [ ] ממשק פשוט להזנת עבודות
- [ ] שמירת נתוני טכנאים

### שלב 4: יצירת דוחות
- [ ] עיצוב תבנית Excel
- [ ] כותרת עם שם חברה, טכנאי ותאריכים
- [ ] טבלת עבודות מפורטת
- [ ] שורת סיכום

### שלב 5: ממשק משתמש (אופציונלי)
- [ ] ממשק ווב פשוט (Streamlit)
- [ ] העלאת קובץ Excel
- [ ] הורדת דוח מוכן

---

## 🛠️ טכנולוגיות

- **Python 3.10+**
- **Pandas** - עיבוד נתונים
- **OpenPyXL** - עבודה עם Excel
- **Streamlit** (אופציונלי) - ממשק משתמש

---

## 📝 שימוש בסיסי

```python
from src.calculator import CommissionCalculator
from src.report_generator import ReportGenerator

# הגדרת עבודה
job = {
    'date': '2024-01-15',
    'address': '101 Needham Avenue, Bronx, NY 10466',
    'total': 1000,
    'parts': 50,
    'payment_method': 'cash',  # cash / cc / check / transfer
    'commission_rate': 0.50
}

# חישוב
calc = CommissionCalculator()
result = calc.calculate(job)
print(f"Tech Profit: ${result['tech_profit']}")
print(f"Balance: ${result['balance']}")

# יצירת דוח
generator = ReportGenerator(technician_name="John Doe")
generator.add_jobs([job])
generator.export("output/report_january.xlsx")
```

---

## 📞 יצירת קשר

**Alpha Locks and Safe**

---

*נוצר עם ❤️ למנעולנים בניו יורק*
