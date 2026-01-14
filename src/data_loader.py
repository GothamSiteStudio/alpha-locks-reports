"""Data loading utilities for Alpha Locks Reports"""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .models import Job, Technician
from config import DEFAULT_COMMISSION_RATE


class DataLoader:
    """
    Load job data from various file formats.
    """
    
    @staticmethod
    def load_from_excel(filepath: str, commission_rate: float = None) -> List[Job]:
        """
        Load jobs from an Excel file.
        
        Expected columns:
        - Date (optional)
        - Address
        - Total
        - Parts (optional, default 0)
        - Payment Method: Cash, CC, Check, Transfer
        - Commission % (optional, uses default if not provided)
        - Fee (optional, for CC processing fees)
        
        Args:
            filepath: Path to Excel file
            commission_rate: Override commission rate for all jobs
            
        Returns:
            List of Job objects
        """
        df = pd.read_excel(filepath)
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        
        jobs = []
        for _, row in df.iterrows():
            # Parse date
            job_date = None
            if 'date' in df.columns and pd.notna(row.get('date')):
                date_val = row['date']
                if isinstance(date_val, str):
                    # Try to parse various date formats
                    for fmt in ['%Y%m%d', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                        try:
                            job_date = datetime.strptime(date_val, fmt).date()
                            break
                        except ValueError:
                            continue
                elif isinstance(date_val, datetime):
                    job_date = date_val.date()
            
            # Determine payment method and amounts
            cash_amount = float(row.get('cash', 0) or 0)
            cc_amount = float(row.get('cc', 0) or row.get('credit card', 0) or 0)
            check_amount = float(row.get('check', 0) or row.get('transfer', 0) or 0)
            
            if cash_amount > 0:
                payment_method = 'cash'
            elif cc_amount > 0:
                payment_method = 'cc'
            elif check_amount > 0:
                payment_method = 'check'
            else:
                payment_method = 'cash'  # Default
            
            # Commission rate
            rate = commission_rate
            if rate is None:
                rate_col = row.get('%', row.get('commission', row.get('rate', None)))
                if pd.notna(rate_col):
                    if isinstance(rate_col, str):
                        rate = float(rate_col.replace('%', '')) / 100
                    else:
                        rate = float(rate_col)
                        if rate > 1:
                            rate = rate / 100
                else:
                    rate = DEFAULT_COMMISSION_RATE
            
            job = Job(
                address=str(row.get('address', '')),
                total=float(row.get('total', 0)),
                parts=float(row.get('parts', 0) or 0),
                payment_method=payment_method,
                job_date=job_date,
                commission_rate=rate,
                fee=float(row.get('fee', 0) or 0),
                cash_amount=cash_amount,
                cc_amount=cc_amount,
                check_amount=check_amount
            )
            jobs.append(job)
        
        return jobs
    
    @staticmethod
    def load_from_csv(filepath: str, commission_rate: float = None) -> List[Job]:
        """
        Load jobs from a CSV file.
        Uses the same logic as Excel loading.
        """
        # Read CSV and save as temp Excel to reuse logic
        df = pd.read_csv(filepath)
        temp_path = Path(filepath).with_suffix('.xlsx')
        df.to_excel(temp_path, index=False)
        
        try:
            jobs = DataLoader.load_from_excel(str(temp_path), commission_rate)
        finally:
            temp_path.unlink()  # Clean up temp file
        
        return jobs
    
    @staticmethod
    def load_technicians(filepath: str) -> List[Technician]:
        """
        Load technicians from a JSON file.
        
        Expected format:
        [
            {"id": "tech1", "name": "John Doe", "commission_rate": 0.50},
            ...
        ]
        """
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return [Technician(**t) for t in data]
