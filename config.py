"""Configuration settings for Alpha Locks Reports"""

# Company Information
COMPANY_NAME = "Alpha Locks and Safe"
COMPANY_PHONE = ""
COMPANY_EMAIL = ""

# Default commission rate (50%)
DEFAULT_COMMISSION_RATE = 0.50

# Payment method codes
PAYMENT_METHODS = {
    'cash': 'Cash',
    'cc': 'Credit Card',
    'check': 'Check',
    'transfer': 'Bank Transfer',
    'split': 'Split (Cash + Card)'
}

# Payment methods that go to company (not to technician directly)
COMPANY_PAYMENT_METHODS = ['cc', 'check', 'transfer']

# Excel styling
EXCEL_STYLES = {
    'header_bg_color': 'D3D3D3',  # Light gray
    'summary_bg_color': '00FFFF',  # Cyan
    'font_name': 'Arial',
    'font_size': 10
}
