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
    
    SPLIT PAYMENT (Mixed Cash + CC/Check):
    - For the CASH portion: Tech keeps their commission % + parts proportionally
    - For the CC portion: Company owes tech their commission % + parts proportionally
    - Balance is calculated for each portion and summed
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
        
        # Check if this is a split payment
        if job.payment_method == 'split':
            return self._calculate_split_payment(job, net_amount)
        
        # Determine payment flow based on payment method
        is_company_payment = job.payment_method in COMPANY_PAYMENT_METHODS
        
        # Check for fixed tech amount override
        if job.tech_amount is not None:
            tech_amount = job.tech_amount
            if is_company_payment:
                # Company received payment → owes tech fixed amount + parts
                tech_profit = tech_amount + job.parts
                balance = -tech_profit
            else:
                # Tech received cash → keeps fixed amount, brings rest
                tech_profit = tech_amount
                balance = job.total - job.parts - tech_amount
            
            return JobResult(
                job=job,
                net_amount=net_amount,
                tech_profit=tech_profit,
                balance=balance
            )
        
        # Technician's commission on net amount
        commission = net_amount * job.commission_rate
        
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
    
    def _calculate_split_payment(self, job: Job, net_amount: float) -> JobResult:
        """
        Calculate commission for a split payment job (cash + cc/check).
        
        The balance is calculated separately for each payment type:
        - Cash portion: tech owes company (total cash - commission on cash portion)
        - CC/Check portion: company owes tech (commission on that portion)
        
        Parts are typically paid from cash, so we deduct them from cash first.
        """
        total = job.total
        cash_amount = job.cash_amount
        cc_amount = job.cc_amount
        check_amount = job.check_amount
        company_amount = cc_amount + check_amount  # Amount company receives
        
        # Fixed tech amount override for split payments
        if job.tech_amount is not None:
            tech_amount = job.tech_amount
            total_tech_owed = tech_amount + job.parts
            
            # Tech keeps from cash up to total_tech_owed
            tech_keeps_from_cash = min(cash_amount, total_tech_owed)
            tech_owes_from_cash = cash_amount - tech_keeps_from_cash
            
            # Company owes tech whatever isn't covered by cash
            company_owes_to_tech = max(0, total_tech_owed - cash_amount)
            
            tech_profit = tech_amount + job.parts
            balance = tech_owes_from_cash - company_owes_to_tech
            
            return JobResult(
                job=job,
                net_amount=net_amount,
                tech_profit=tech_profit,
                balance=balance
            )
        
        # Commission rate
        rate = job.commission_rate
        
        # Total commission on net amount
        commission = net_amount * rate
        
        # Tech profit is the same regardless of payment method split
        # They earn commission on the net amount (total - parts)
        tech_profit = commission + job.parts
        
        # Balance calculation:
        # For CASH portion: Tech collected it, needs to give company their share
        #   Company's share of cash = cash_amount - (cash_portion of commission) - parts
        #   But simpler: company_share_of_cash = cash_amount * (1 - rate) - parts
        #   Tech owes: cash_amount - parts - (cash_amount * rate) = cash_amount * (1 - rate) - parts
        # For CC portion: Company collected it, needs to pay tech their share
        #   Tech's share of CC = cc_amount * rate
        #   Company owes: cc_amount * rate (positive means company owes)
        
        # Simplify: Parts come out of cash first
        cash_after_parts = cash_amount - job.parts
        
        # Tech's commission on the total net amount 
        # But we need to figure out how much goes from cash vs cc
        
        # Actually, the cleanest way:
        # Tech collects: cash_amount (has it in hand)
        # Tech should keep: parts + commission = parts + (total - parts) * rate
        # Tech should bring to company: cash_amount - (parts + commission on cash portion)
        
        # But the commission is on the TOTAL net, not split by payment type
        # So: tech_profit = (total - parts) * rate + parts
        # 
        # From CASH: tech collected cash_amount, keeps parts, keeps part of commission
        # From CC: company collected cc_amount, owes tech part of commission
        #
        # Let's think about it differently:
        # Total commission = (350 - 0) * 0.5 = 175
        # Tech profit = 175 + 0 = 175
        # 
        # Cash side: Tech has $200
        #   Commission portion from cash = 200 * 0.5 = 100 (or proportional to total)
        #   Tech keeps $100, brings $100 to company
        #
        # CC side: Company has $150
        #   Commission portion = 150 * 0.5 = 75
        #   Company owes tech $75
        #
        # Net balance: Tech owes $100 - $75 = $25 to company ✓
        
        # Calculate proportionally
        cash_commission = cash_after_parts * rate if cash_after_parts > 0 else 0
        company_commission = company_amount * rate
        
        # What tech owes from cash (after keeping their share and parts)
        tech_owes_from_cash = cash_after_parts - cash_commission if cash_after_parts > 0 else 0
        
        # What company owes tech from CC/check payments
        company_owes_to_tech = company_commission
        
        # Net balance: positive means tech owes company
        balance = tech_owes_from_cash - company_owes_to_tech
        
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
