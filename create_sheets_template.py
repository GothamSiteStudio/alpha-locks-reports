"""
Create Excel template file for Google Sheets upload
Run this script to generate the template file
"""
import pandas as pd
from pathlib import Path

# Define the columns for Jobs sheet
jobs_columns = [
    'id',
    'technician_id', 
    'technician_name',
    'address',
    'total',
    'parts',
    'payment_method',
    'description',
    'phone',
    'job_date',
    'created_at',
    'is_paid',
    'paid_date',
    'commission_rate',
    'notes'
]

# Define the columns for Technicians sheet
technicians_columns = [
    'id',
    'name',
    'commission_rate',
    'created_at'
]

# Create empty DataFrames with the correct columns
jobs_df = pd.DataFrame(columns=jobs_columns)
technicians_df = pd.DataFrame(columns=technicians_columns)

# Save to Excel with two sheets
output_path = Path(__file__).parent / "Alpha_Reports_Data.xlsx"

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    jobs_df.to_excel(writer, sheet_name='jobs', index=False)
    technicians_df.to_excel(writer, sheet_name='technicians', index=False)

print(f"✅ Template file created: {output_path}")
print("\nNext steps:")
print("1. Go to Google Sheets (sheets.google.com)")
print("2. Click 'Blank spreadsheet' to create new")
print("3. File → Import → Upload → Select 'Alpha_Reports_Data.xlsx'")
print("4. Choose 'Replace spreadsheet' and click 'Import data'")
print("5. Share the sheet with your Service Account email (Editor access)")
