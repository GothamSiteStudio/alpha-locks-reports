"""Google Sheets storage backend for persistent data storage"""
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# Google Sheets configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Sheet ID from your Google Sheet URL
SHEET_ID = "1yB80SogQbQCs0n2snHt6rQJ50qhY5Adggd3sqpEHylE"


class GoogleSheetsClient:
    """Client for interacting with Google Sheets"""
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self._connect()
    
    def _get_credentials(self) -> Optional[Credentials]:
        """Get Google credentials from various sources"""
        
        # Option 1: Streamlit secrets (for deployed app)
        try:
            import streamlit as st
            if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                creds_dict = dict(st.secrets['gcp_service_account'])
                return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception:
            pass
        
        # Option 2: Environment variable with JSON content
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            try:
                creds_dict = json.loads(creds_json)
                return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            except Exception:
                pass
        
        # Option 3: Local file in secrets folder
        secrets_path = Path(__file__).parent.parent / "secrets" / "google_credentials.json"
        if secrets_path.exists():
            return Credentials.from_service_account_file(str(secrets_path), scopes=SCOPES)
        
        # Option 4: File path from environment variable
        creds_file = os.environ.get('GOOGLE_CREDENTIALS_FILE')
        if creds_file and Path(creds_file).exists():
            return Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        
        return None
    
    def _connect(self):
        """Connect to Google Sheets"""
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread is not installed. Run: pip install gspread google-auth")
        
        creds = self._get_credentials()
        if not creds:
            raise ValueError(
                "Google credentials not found. Please provide credentials via:\n"
                "1. Streamlit secrets (gcp_service_account)\n"
                "2. GOOGLE_CREDENTIALS_JSON environment variable\n"
                "3. secrets/google_credentials.json file\n"
                "4. GOOGLE_CREDENTIALS_FILE environment variable"
            )
        
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(SHEET_ID)
    
    def get_worksheet(self, name: str):
        """Get or create a worksheet by name"""
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=name, rows=1000, cols=20)
    
    # ============ JOBS ============
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs from the sheet"""
        try:
            worksheet = self.get_worksheet('jobs')
            records = worksheet.get_all_records()
            
            # Convert types
            for record in records:
                # Convert numeric fields
                for field in ['total', 'parts', 'commission_rate', 'cash_amount', 'cc_amount', 'check_amount']:
                    if field in record and record[field] != '':
                        try:
                            record[field] = float(record[field])
                        except (ValueError, TypeError):
                            record[field] = 0.0
                    elif field in record:
                        record[field] = 0.0
                    else:
                        # Field doesn't exist in sheet - add default
                        record[field] = 0.0
                
                # Convert boolean
                if 'is_paid' in record:
                    record['is_paid'] = str(record['is_paid']).lower() in ('true', '1', 'yes')
                
                # Handle None values
                if 'paid_date' in record and record['paid_date'] == '':
                    record['paid_date'] = None
                if 'notes' not in record:
                    record['notes'] = ''
            
            return records
        except Exception as e:
            print(f"Error getting jobs: {e}")
            return []
    
    def add_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new job to the sheet"""
        worksheet = self.get_worksheet('jobs')
        
        # Get headers
        headers = worksheet.row_values(1)
        if not headers:
            headers = ['id', 'technician_id', 'technician_name', 'address', 'total', 
                      'parts', 'payment_method', 'description', 'phone', 'job_date',
                      'created_at', 'is_paid', 'paid_date', 'commission_rate', 'notes',
                      'cash_amount', 'cc_amount', 'check_amount']
            worksheet.update('A1', [headers])
        
        # Prepare row data
        row = []
        for header in headers:
            value = job_data.get(header, '')
            # Convert boolean to string for sheets
            if isinstance(value, bool):
                value = str(value).lower()
            # Convert None to empty string
            if value is None:
                value = ''
            row.append(value)
        
        # Append row
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        return job_data
    
    def add_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add multiple jobs at once"""
        worksheet = self.get_worksheet('jobs')
        
        # Get headers
        headers = worksheet.row_values(1)
        if not headers:
            headers = ['id', 'technician_id', 'technician_name', 'address', 'total', 
                      'parts', 'payment_method', 'description', 'phone', 'job_date',
                      'created_at', 'is_paid', 'paid_date', 'commission_rate', 'notes',
                      'cash_amount', 'cc_amount', 'check_amount']
            worksheet.update('A1', [headers])
        
        # Prepare all rows
        rows = []
        for job_data in jobs:
            row = []
            for header in headers:
                value = job_data.get(header, '')
                if isinstance(value, bool):
                    value = str(value).lower()
                if value is None:
                    value = ''
                row.append(value)
            rows.append(row)
        
        # Append all rows at once
        if rows:
            worksheet.append_rows(rows, value_input_option='USER_ENTERED')
        
        return jobs
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a job by ID"""
        worksheet = self.get_worksheet('jobs')
        
        # Find the row with this job ID
        try:
            cell = worksheet.find(job_id, in_column=1)
            if not cell:
                return None
            
            row_num = cell.row
            headers = worksheet.row_values(1)
            current_row = worksheet.row_values(row_num)
            
            # Build updated row
            updated_data = {}
            for i, header in enumerate(headers):
                if i < len(current_row):
                    updated_data[header] = current_row[i]
                else:
                    updated_data[header] = ''
            
            # Apply updates
            updated_data.update(updates)
            
            # Convert types for sheets
            new_row = []
            for header in headers:
                value = updated_data.get(header, '')
                if isinstance(value, bool):
                    value = str(value).lower()
                if value is None:
                    value = ''
                new_row.append(value)
            
            # Update the row
            worksheet.update(f'A{row_num}', [new_row])
            
            return updated_data
        except Exception as e:
            print(f"Error updating job: {e}")
            return None
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID"""
        worksheet = self.get_worksheet('jobs')
        
        try:
            cell = worksheet.find(job_id, in_column=1)
            if cell:
                worksheet.delete_rows(cell.row)
                return True
        except Exception as e:
            print(f"Error deleting job: {e}")
        
        return False
    
    # ============ TECHNICIANS ============
    
    def get_all_technicians(self) -> List[Dict[str, Any]]:
        """Get all technicians from the sheet"""
        try:
            worksheet = self.get_worksheet('technicians')
            records = worksheet.get_all_records()
            
            # Convert types
            for record in records:
                if 'commission_rate' in record and record['commission_rate'] != '':
                    try:
                        record['commission_rate'] = float(record['commission_rate'])
                    except (ValueError, TypeError):
                        record['commission_rate'] = 0.5
                elif 'commission_rate' in record:
                    record['commission_rate'] = 0.5
            
            return records
        except Exception as e:
            print(f"Error getting technicians: {e}")
            return []
    
    def add_technician(self, tech_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new technician"""
        worksheet = self.get_worksheet('technicians')
        
        # Get headers
        headers = worksheet.row_values(1)
        if not headers:
            headers = ['id', 'name', 'commission_rate', 'created_at']
            worksheet.update('A1', [headers])
        
        # Prepare row
        row = [tech_data.get(h, '') for h in headers]
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        
        return tech_data
    
    def update_technician(self, tech_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a technician by ID"""
        worksheet = self.get_worksheet('technicians')
        
        try:
            cell = worksheet.find(tech_id, in_column=1)
            if not cell:
                return None
            
            row_num = cell.row
            headers = worksheet.row_values(1)
            current_row = worksheet.row_values(row_num)
            
            # Build updated data
            updated_data = {}
            for i, header in enumerate(headers):
                if i < len(current_row):
                    updated_data[header] = current_row[i]
            
            updated_data.update(updates)
            
            # Update row
            new_row = [updated_data.get(h, '') for h in headers]
            worksheet.update(f'A{row_num}', [new_row])
            
            return updated_data
        except Exception as e:
            print(f"Error updating technician: {e}")
            return None
    
    def delete_technician(self, tech_id: str) -> bool:
        """Delete a technician by ID"""
        worksheet = self.get_worksheet('technicians')
        
        try:
            cell = worksheet.find(tech_id, in_column=1)
            if cell:
                worksheet.delete_rows(cell.row)
                return True
        except Exception as e:
            print(f"Error deleting technician: {e}")
        
        return False


# Singleton instance - cached as Streamlit resource (survives reruns)
@st.cache_resource
def get_sheets_client() -> GoogleSheetsClient:
    """Get or create the Google Sheets client singleton (cached across reruns)."""
    return GoogleSheetsClient()
