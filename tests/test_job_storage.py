"""Storage regression tests for local JSON backend behavior."""
import os
import sys
from pathlib import Path

# Force local backend for tests
os.environ["USE_LOCAL_STORAGE"] = "true"

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_storage import JobStorage, StoredJob


class TestStoredJobNormalization:
    def test_from_dict_normalizes_tech_amount_and_defaults(self):
        base = {
            "id": "1",
            "technician_id": "tech-1",
            "technician_name": "John",
            "address": "123 Main St",
            "total": 400,
            "parts": 25,
            "payment_method": "cash",
            "description": "",
            "phone": "",
            "job_date": "2026-01-05",
            "created_at": "2026-01-05T10:00:00",
            "is_paid": False,
            "paid_date": None,
            "commission_rate": 0.5,
            "notes": "",
        }

        job_zero = StoredJob.from_dict({**base, "tech_amount": 0})
        assert job_zero.tech_amount is None

        job_str = StoredJob.from_dict({**base, "tech_amount": "120"})
        assert job_str.tech_amount == 120.0

        job_missing = StoredJob.from_dict(dict(base))
        assert job_missing.tech_amount is None
        assert job_missing.cash_amount == 0.0
        assert job_missing.cc_amount == 0.0
        assert job_missing.check_amount == 0.0


class TestJobStorageLocalFlow:
    def test_add_jobs_and_mark_paid_unpaid_batch(self, tmp_path):
        storage = JobStorage(data_dir=str(tmp_path))

        job1 = StoredJob(
            id="",
            technician_id="tech-1",
            technician_name="John",
            address="123 Main St",
            total=300,
            parts=20,
            payment_method="cash",
            description="lockout",
            phone="",
            job_date="2026-01-10",
            created_at="",
            is_paid=False,
            commission_rate=0.5,
            cash_amount=300,
            cc_amount=0,
            check_amount=0,
            tech_amount=120,
        )
        job2 = StoredJob(
            id="",
            technician_id="tech-1",
            technician_name="John",
            address="456 Elm Ave",
            total=500,
            parts=50,
            payment_method="check",
            description="rekey",
            phone="",
            job_date="2026-01-11",
            created_at="",
            is_paid=False,
            commission_rate=0.5,
            cash_amount=0,
            cc_amount=0,
            check_amount=500,
            tech_amount=None,
        )

        saved_jobs = storage.add_jobs([job1, job2])
        assert len(saved_jobs) == 2
        assert all(j.id for j in saved_jobs)
        assert all(j.created_at for j in saved_jobs)

        all_jobs = storage._get_all_jobs_local()
        ids = [j.id for j in all_jobs]
        assert len(ids) == 2

        updated_count = storage.mark_jobs_paid(ids)
        assert updated_count == 2

        all_paid = storage._get_all_jobs_local()
        assert all(j.is_paid for j in all_paid)
        assert all(j.paid_date for j in all_paid)

        reverted_count = storage.mark_jobs_unpaid(ids)
        assert reverted_count == 2

        all_unpaid = storage._get_all_jobs_local()
        assert all(not j.is_paid for j in all_unpaid)
        assert all(j.paid_date is None for j in all_unpaid)
