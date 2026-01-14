"""Commission calculation logic for Alpha Locks Reports"""
from typing import List
from .models import Job, JobResult, Technician
from config import COMPANY_PAYMENT_METHODS


class CommissionCalculator:
    """
    Calculates technician commission and balance for jobs.
    
    Business Logic:
    ===============
    
    When customer pays CASH to technician:
    - Tech keeps parts cost
    - Tech keeps their commission % of (Total - Parts)
    - Tech brings back the rest to company
    - Balance = Total - Parts - TechProfit (positive = tech owes company)
    
    When customer pays to COMPANY (CC/Check/Transfer):
    - Company receives full payment
    - Company pays tech: commission % of (Total - Parts) + Parts cost
    - Balance = negative (company owes tech)
    """
    
    def calculate_single(self, job: Job) -> JobResult:
        """
        Calculate commission for a single job.
        
        Args:
            job: The job to calculate
            
        Returns:
            JobResult with calculated values
        """
        # Net amount after parts
        net_amount = job.total - job.parts
        
        # Technician's commission on net amount
        commission = net_amount * job.commission_rate
        
        # Determine payment flow based on payment method
        is_company_payment = job.payment_method in COMPANY_PAYMENT_METHODS
        
        if is_company_payment:
            # Company received payment
            # Tech profit = commission + parts (company reimburses parts)
            tech_profit = commission + job.parts
            # Balance is negative (company owes tech)
            balance = -tech_profit
        else:
            # Tech received cash payment
            # Tech profit = commission (tech already kept parts)
            tech_profit = commission
            # Balance = what tech needs to bring to company
            # Tech collected Total, keeps Parts + Commission
            balance = job.total - job.parts - commission
        
        return JobResult(
            job=job,
            net_amount=net_amount,
            tech_profit=tech_profit,
            balance=balance
        )
    
    def calculate_batch(self, jobs: List[Job]) -> List[JobResult]:
        """
        Calculate commission for multiple jobs.
        
        Args:
            jobs: List of jobs to calculate
            
        Returns:
            List of JobResult objects
        """
        return [self.calculate_single(job) for job in jobs]
    
    def calculate_summary(self, results: List[JobResult]) -> dict:
        """
        Calculate summary totals for a list of job results.
        
        Args:
            results: List of JobResult objects
            
        Returns:
            Dictionary with summary totals
        """
        return {
            'job_count': len(results),
            'total_sales': sum(r.job.total for r in results),
            'total_parts': sum(r.job.parts for r in results),
            'total_cash': sum(r.job.cash_amount for r in results),
            'total_cc': sum(r.job.cc_amount for r in results),
            'total_check': sum(r.job.check_amount for r in results),
            'total_fee': sum(r.job.fee for r in results),
            'total_tech_profit': sum(r.tech_profit for r in results),
            'total_balance': sum(r.balance for r in results)
        }
