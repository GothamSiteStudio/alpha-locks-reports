"""
Migrate existing data from local JSON files to Google Sheets
Run this script once to transfer your existing jobs and technicians.
"""
import json
from pathlib import Path

def migrate_data():
    """Migrate data from local files to Google Sheets"""
    
    # Import the sheets client
    from src.sheets_storage import get_sheets_client
    
    data_dir = Path("data")
    jobs_file = data_dir / "stored_jobs.json"
    technicians_file = data_dir / "technicians.json"
    
    client = get_sheets_client()
    print("✅ Connected to Google Sheets")
    
    # Migrate technicians first
    if technicians_file.exists():
        with open(technicians_file, 'r', encoding='utf-8') as f:
            technicians = json.load(f)
        
        print(f"\n📋 Found {len(technicians)} technicians to migrate...")
        
        for tech in technicians:
            try:
                client.add_technician(tech)
                print(f"  ✓ {tech['name']}")
            except Exception as e:
                print(f"  ✗ Error with {tech['name']}: {e}")
        
        print(f"✅ Technicians migrated!")
    else:
        print("⚠️ No technicians file found")
    
    # Migrate jobs
    if jobs_file.exists():
        with open(jobs_file, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        
        print(f"\n📋 Found {len(jobs)} jobs to migrate...")
        
        # Add all jobs at once for efficiency
        if jobs:
            try:
                client.add_jobs(jobs)
                print(f"✅ All {len(jobs)} jobs migrated!")
            except Exception as e:
                print(f"✗ Error migrating jobs: {e}")
                # Try one by one
                print("Trying one by one...")
                for job in jobs:
                    try:
                        client.add_job(job)
                        print(f"  ✓ {job.get('address', 'Unknown')[:40]}...")
                    except Exception as e2:
                        print(f"  ✗ Error: {e2}")
    else:
        print("⚠️ No jobs file found")
    
    print("\n" + "="*50)
    print("🎉 Migration complete!")
    print("="*50)
    print("\nYou can now deploy your app to Streamlit Cloud.")
    print("Your data is safely stored in Google Sheets!")


if __name__ == "__main__":
    migrate_data()
