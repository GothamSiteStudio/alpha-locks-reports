"""Regression tests for message parsing behavior."""
import sys
from pathlib import Path
from datetime import date

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.message_parser import MessageParser


class TestMessageParserRegression:
    """Covers common real-world parsing scenarios."""

    def setup_method(self):
        self.parser = MessageParser()

    def test_parse_labeled_message_with_tech_amount_and_date(self):
        text = """
Addr: 123 Main St, White Plains, NY 10601
Desc: Lockout front door
Ph: (914) 555-1212
date: 1/5/26
Total cash 450
Parts 50
Tech 120
John
""".strip()

        job = self.parser.parse_single_job(text)

        assert job is not None
        assert job.address == "123 Main St, White Plains, NY 10601"
        assert job.total == 450
        assert job.parts == 50
        assert job.payment_method == "cash"
        assert job.phone == "(914) 555-1212"
        assert job.job_date == date(2026, 1, 5)
        assert job.technician_name == "John"
        assert job.tech_amount == 120

    def test_parse_split_payment_message(self):
        text = """
27 Deepwood Hill St, Chappaqua, NY 10514
200 cash
150 with the credit card
50 check
Parts 25
Alex
""".strip()

        job = self.parser.parse_single_job(text)

        assert job is not None
        assert job.payment_method == "split"
        assert job.total == 400
        assert job.cash_amount == 200
        assert job.cc_amount == 150
        assert job.check_amount == 50
        assert job.parts == 25
        assert job.technician_name == "Alex"

    def test_parse_multiple_jobs_block(self):
        text = """
123 Main St, White Plains, NY 10601
alpha job
$300
Parts $20
John

456 Elm Ave, Yonkers, NY 10701
alpha job
Total check 500
Parts 50
Mike
""".strip()

        jobs = self.parser.parse_multiple_jobs(text)

        assert len(jobs) == 2
        assert jobs[0].address.startswith("123 Main")
        assert jobs[0].payment_method == "cash"
        assert jobs[0].total == 300
        assert jobs[0].technician_name == "John"

        assert jobs[1].address.startswith("456 Elm")
        assert jobs[1].payment_method == "check"
        assert jobs[1].total == 500
        assert jobs[1].technician_name == "Mike"
