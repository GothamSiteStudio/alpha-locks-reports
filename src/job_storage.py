"""Job storage system for persistent job management"""
import json
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class StoredJob:
    """Represents a stored job with all metadata"""
    id: str
    technician_id: str
    technician_name: str
    address: str
    total: float
    parts: float
    payment_method: str  # 'cash', 'cc', 'check'
    description: str
    phone: str
    job_date: str  # ISO format YYYY-MM-DD
    created_at: str  # ISO format datetime
    is_paid: bool = False
    paid_date: Optional[str] = None
    commission_rate: float = 0.50
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StoredJob':
        return cls(**data)


class JobStorage:
    """Manages persistent storage of jobs and technicians"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.jobs_file = self.data_dir / "stored_jobs.json"
        self.technicians_file = self.data_dir / "technicians.json"
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize files if they don't exist
        if not self.jobs_file.exists():
            self._save_jobs([])
        if not self.technicians_file.exists():
            self._save_technicians([])
    
    # ============ JOBS ============
    
    def get_all_jobs(self) -> List[StoredJob]:
        """Get all stored jobs"""
        try:
            with open(self.jobs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [StoredJob.from_dict(job) for job in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_jobs_by_technician(self, technician_id: str) -> List[StoredJob]:
        """Get all jobs for a specific technician"""
        jobs = self.get_all_jobs()
        return [job for job in jobs if job.technician_id == technician_id]
    
    def get_jobs_by_date_range(self, start_date: date, end_date: date) -> List[StoredJob]:
        """Get jobs within a date range"""
        jobs = self.get_all_jobs()
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        return [job for job in jobs if start_str <= job.job_date <= end_str]
    
    def get_unpaid_jobs(self) -> List[StoredJob]:
        """Get all unpaid jobs"""
        jobs = self.get_all_jobs()
        return [job for job in jobs if not job.is_paid]
    
    def get_unpaid_jobs_by_technician(self, technician_id: str) -> List[StoredJob]:
        """Get unpaid jobs for a specific technician"""
        jobs = self.get_jobs_by_technician(technician_id)
        return [job for job in jobs if not job.is_paid]
    
    def add_job(self, job: StoredJob) -> StoredJob:
        """Add a new job"""
        jobs = self.get_all_jobs()
        
        # Generate ID if not provided
        if not job.id:
            job.id = str(uuid.uuid4())
        
        # Set created_at if not provided
        if not job.created_at:
            job.created_at = datetime.now().isoformat()
        
        jobs.append(job)
        self._save_jobs(jobs)
        return job
    
    def add_jobs(self, new_jobs: List[StoredJob]) -> List[StoredJob]:
        """Add multiple jobs at once"""
        jobs = self.get_all_jobs()
        
        for job in new_jobs:
            if not job.id:
                job.id = str(uuid.uuid4())
            if not job.created_at:
                job.created_at = datetime.now().isoformat()
            jobs.append(job)
        
        self._save_jobs(jobs)
        return new_jobs
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[StoredJob]:
        """Update a job by ID"""
        jobs = self.get_all_jobs()
        
        for i, job in enumerate(jobs):
            if job.id == job_id:
                job_dict = job.to_dict()
                job_dict.update(updates)
                jobs[i] = StoredJob.from_dict(job_dict)
                self._save_jobs(jobs)
                return jobs[i]
        
        return None
    
    def mark_job_paid(self, job_id: str) -> Optional[StoredJob]:
        """Mark a job as paid"""
        return self.update_job(job_id, {
            'is_paid': True,
            'paid_date': datetime.now().isoformat()
        })
    
    def mark_job_unpaid(self, job_id: str) -> Optional[StoredJob]:
        """Mark a job as unpaid"""
        return self.update_job(job_id, {
            'is_paid': False,
            'paid_date': None
        })
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID"""
        jobs = self.get_all_jobs()
        original_count = len(jobs)
        jobs = [job for job in jobs if job.id != job_id]
        
        if len(jobs) < original_count:
            self._save_jobs(jobs)
            return True
        return False
    
    def get_job_by_id(self, job_id: str) -> Optional[StoredJob]:
        """Get a specific job by ID"""
        jobs = self.get_all_jobs()
        for job in jobs:
            if job.id == job_id:
                return job
        return None
    
    def _save_jobs(self, jobs: List[StoredJob]):
        """Save jobs to file"""
        with open(self.jobs_file, 'w', encoding='utf-8') as f:
            json.dump([job.to_dict() for job in jobs], f, indent=2, ensure_ascii=False)
    
    # ============ TECHNICIANS ============
    
    def get_all_technicians(self) -> List[Dict[str, Any]]:
        """Get all technicians"""
        try:
            with open(self.technicians_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_technician_by_id(self, tech_id: str) -> Optional[Dict[str, Any]]:
        """Get a technician by ID"""
        technicians = self.get_all_technicians()
        for tech in technicians:
            if tech['id'] == tech_id:
                return tech
        return None
    
    def get_technician_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a technician by name (case-insensitive)"""
        technicians = self.get_all_technicians()
        name_lower = name.lower().strip()
        for tech in technicians:
            if tech['name'].lower().strip() == name_lower:
                return tech
        return None
    
    def add_technician(self, name: str, commission_rate: float = 0.50) -> Dict[str, Any]:
        """Add a new technician"""
        technicians = self.get_all_technicians()
        
        # Check if technician already exists
        existing = self.get_technician_by_name(name)
        if existing:
            return existing
        
        new_tech = {
            'id': str(uuid.uuid4()),
            'name': name.strip(),
            'commission_rate': commission_rate,
            'created_at': datetime.now().isoformat()
        }
        
        technicians.append(new_tech)
        self._save_technicians(technicians)
        return new_tech
    
    def get_or_create_technician(self, name: str, commission_rate: float = 0.50) -> Dict[str, Any]:
        """Get existing technician or create new one"""
        existing = self.get_technician_by_name(name)
        if existing:
            return existing
        return self.add_technician(name, commission_rate)
    
    def update_technician(self, tech_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a technician"""
        technicians = self.get_all_technicians()
        
        for i, tech in enumerate(technicians):
            if tech['id'] == tech_id:
                technicians[i].update(updates)
                self._save_technicians(technicians)
                return technicians[i]
        
        return None
    
    def delete_technician(self, tech_id: str) -> bool:
        """Delete a technician"""
        technicians = self.get_all_technicians()
        original_count = len(technicians)
        technicians = [t for t in technicians if t['id'] != tech_id]
        
        if len(technicians) < original_count:
            self._save_technicians(technicians)
            return True
        return False
    
    def _save_technicians(self, technicians: List[Dict[str, Any]]):
        """Save technicians to file"""
        with open(self.technicians_file, 'w', encoding='utf-8') as f:
            json.dump(technicians, f, indent=2, ensure_ascii=False)
    
    # ============ STATISTICS ============
    
    def get_technician_stats(self, technician_id: str) -> Dict[str, Any]:
        """Get statistics for a technician"""
        jobs = self.get_jobs_by_technician(technician_id)
        
        total_jobs = len(jobs)
        paid_jobs = len([j for j in jobs if j.is_paid])
        unpaid_jobs = total_jobs - paid_jobs
        
        total_sales = sum(j.total for j in jobs)
        total_parts = sum(j.parts for j in jobs)
        
        unpaid_amount = sum(j.total - j.parts for j in jobs if not j.is_paid)
        
        return {
            'total_jobs': total_jobs,
            'paid_jobs': paid_jobs,
            'unpaid_jobs': unpaid_jobs,
            'total_sales': total_sales,
            'total_parts': total_parts,
            'unpaid_amount': unpaid_amount
        }
