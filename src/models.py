"""Data models for Alpha Locks Reports"""
from dataclasses import dataclass
from datetime import date
from typing import Optional, Literal
from decimal import Decimal

PaymentMethod = Literal['cash', 'cc', 'check', 'transfer', 'split']


@dataclass
class Technician:
    """Represents a technician"""
    id: str
    name: str
    commission_rate: float = 0.50  # Default 50%
    
    def __post_init__(self):
        if not 0 <= self.commission_rate <= 1:
            raise ValueError("Commission rate must be between 0 and 1")


@dataclass
class Job:
    """Represents a single job/service call"""
    address: str
    total: float
    payment_method: PaymentMethod
    job_date: Optional[date] = None
    parts: float = 0.0
    commission_rate: float = 0.50
    job_type: str = ""
    fee: float = 0.0  # Processing fee (for CC)
    
    # Payment breakdown (optional - for mixed payments)
    cash_amount: float = 0.0
    cc_amount: float = 0.0
    check_amount: float = 0.0
    
    # Fixed tech amount override (when set, overrides commission_rate)
    tech_amount: Optional[float] = None
    
    def __post_init__(self):
        # If single payment method, set the corresponding amount
        if self.payment_method == 'cash' and self.cash_amount == 0:
            self.cash_amount = self.total
        elif self.payment_method == 'cc' and self.cc_amount == 0:
            self.cc_amount = self.total
        elif self.payment_method in ['check', 'transfer'] and self.check_amount == 0:
            self.check_amount = self.total


@dataclass
class JobResult:
    """Result of commission calculation for a job"""
    job: Job
    net_amount: float  # Total - Parts
    tech_profit: float  # Technician's earnings
    balance: float  # Positive = tech owes company, Negative = company owes tech
    
    @property
    def tech_owes_company(self) -> bool:
        return self.balance > 0
