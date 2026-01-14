"""Tests for the commission calculator"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import Job, Technician
from src.calculator import CommissionCalculator


class TestCommissionCalculator:
    """Test cases for CommissionCalculator"""
    
    def setup_method(self):
        self.calc = CommissionCalculator()
    
    def test_cash_payment_no_parts(self):
        """
        Test: Cash payment, no parts
        Job: $1000 cash, 50% commission
        Expected:
        - Tech profit: $500
        - Balance: $500 (tech owes company)
        """
        job = Job(
            address="123 Test St",
            total=1000,
            parts=0,
            payment_method='cash',
            commission_rate=0.50
        )
        
        result = self.calc.calculate_single(job)
        
        assert result.tech_profit == 500
        assert result.balance == 500
        assert result.tech_owes_company is True
    
    def test_cash_payment_with_parts(self):
        """
        Test: Cash payment with parts
        Job: $1000 cash, $50 parts, 50% commission
        Expected:
        - Net: $950
        - Tech profit: $475
        - Balance: $475 (tech owes company)
        """
        job = Job(
            address="123 Test St",
            total=1000,
            parts=50,
            payment_method='cash',
            commission_rate=0.50
        )
        
        result = self.calc.calculate_single(job)
        
        assert result.net_amount == 950
        assert result.tech_profit == 475
        assert result.balance == 475
    
    def test_cc_payment_no_parts(self):
        """
        Test: Credit card payment, no parts
        Job: $1000 CC, 50% commission
        Expected:
        - Tech profit: $500
        - Balance: -$500 (company owes tech)
        """
        job = Job(
            address="123 Test St",
            total=1000,
            parts=0,
            payment_method='cc',
            commission_rate=0.50
        )
        
        result = self.calc.calculate_single(job)
        
        assert result.tech_profit == 500
        assert result.balance == -500
        assert result.tech_owes_company is False
    
    def test_cc_payment_with_parts(self):
        """
        Test: Credit card payment with parts
        Job: $1000 CC, $50 parts, 50% commission
        Expected:
        - Net: $950
        - Tech profit: $475 + $50 = $525
        - Balance: -$525 (company owes tech)
        """
        job = Job(
            address="123 Test St",
            total=1000,
            parts=50,
            payment_method='cc',
            commission_rate=0.50
        )
        
        result = self.calc.calculate_single(job)
        
        assert result.net_amount == 950
        assert result.tech_profit == 525
        assert result.balance == -525
    
    def test_check_payment(self):
        """
        Test: Check payment (same as CC - goes to company)
        """
        job = Job(
            address="123 Test St",
            total=1000,
            parts=50,
            payment_method='check',
            commission_rate=0.50
        )
        
        result = self.calc.calculate_single(job)
        
        assert result.tech_profit == 525
        assert result.balance == -525
    
    def test_different_commission_rate(self):
        """
        Test: Different commission rate (40%)
        Job: $550 cash, $9 parts, 40% commission
        Expected:
        - Net: $541
        - Tech profit: $216.40
        - Balance: $324.60
        """
        job = Job(
            address="123 Test St",
            total=550,
            parts=9,
            payment_method='cash',
            commission_rate=0.40
        )
        
        result = self.calc.calculate_single(job)
        
        assert result.net_amount == 541
        assert abs(result.tech_profit - 216.40) < 0.01
        assert abs(result.balance - 324.60) < 0.01
    
    def test_batch_calculation(self):
        """Test batch calculation of multiple jobs"""
        jobs = [
            Job(address="Job 1", total=100, parts=0, payment_method='cash', commission_rate=0.50),
            Job(address="Job 2", total=200, parts=20, payment_method='cash', commission_rate=0.50),
            Job(address="Job 3", total=300, parts=0, payment_method='cc', commission_rate=0.50),
        ]
        
        results = self.calc.calculate_batch(jobs)
        
        assert len(results) == 3
        assert results[0].balance == 50
        assert results[1].balance == 90
        assert results[2].balance == -150
    
    def test_summary_calculation(self):
        """Test summary totals"""
        jobs = [
            Job(address="Job 1", total=100, parts=0, payment_method='cash', commission_rate=0.50),
            Job(address="Job 2", total=200, parts=20, payment_method='cash', commission_rate=0.50),
        ]
        
        results = self.calc.calculate_batch(jobs)
        summary = self.calc.calculate_summary(results)
        
        assert summary['job_count'] == 2
        assert summary['total_sales'] == 300
        assert summary['total_parts'] == 20
        assert summary['total_balance'] == 140  # 50 + 90


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
