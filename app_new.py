"""
Alpha Locks Reports - Main Application with Job Management
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
import tempfile
from pathlib import Path

from src.models import Job, Technician
from src.report_generator import ReportGenerator
from src.html_exporter import HTMLReportExporter
from src.data_loader import DataLoader
from src.message_parser import MessageParser
from src.job_storage import JobStorage, StoredJob
from config import COMPANY_NAME, DEFAULT_COMMISSION_RATE
from auth_config import verify_password


# Initialize storage
storage = JobStorage()


def login_page():
    """Display login page."""
    st.set_page_config(
        page_title=f"{COMPANY_NAME} - Login",
        page_icon="🔐",
        layout="centered"
    )
    
    st.title("🔐 Alpha Locks and Safe")
    st.subheader("Login to Reports System")
    
    st.markdown("---")
    
    with st.form("login_form"):
        username = st.text_input("👤 Username")
        password = st.text_input("🔑 Password", type="password")
        submit = st.form_submit_button("🚀 Login", type="primary")
        
        if submit:
            if verify_password(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
    
    st.markdown("---")
    st.caption("© Alpha Locks and Safe - Reports System")


def page_add_jobs():
    """Page for adding new jobs"""
    st.header("📝 Add New Jobs")
    st.markdown("Paste job closure messages and they will be saved automatically.")
    
    # Get all technicians for dropdown
    technicians = storage.get_all_technicians()
    tech_names = ["Auto-detect"] + [t['name'] for t in technicians]
    
    # Sidebar settings
    st.sidebar.markdown("### ⚙️ Job Settings")
    
    default_tech = st.sidebar.selectbox(
        "Default Technician",
        options=tech_names,
        index=0,
        help="Select technician or let system auto-detect from message"
    )
    
    commission_rate = st.sidebar.slider(
        "Commission Rate (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5
    ) / 100
    
    job_date = st.sidebar.date_input(
        "Job Date",
        value=date.today(),
        help="Date for all jobs being added"
    )
    
    # Main content - Input tabs
    tab1, tab2 = st.tabs(["📋 Paste Messages", "✏️ Manual Entry"])
    
    # Tab 1: Paste Messages
    with tab1:
        st.markdown("#### Paste job closure messages below:")
        st.caption("Each job should contain: Address, Alpha Job marker, Price, and Technician name (last line)")
        
        messages_text = st.text_area(
            "Messages:",
            height=300,
            placeholder="""Example:
20 N Broadway, White Plains, NY 10601
Change locks 

+1 (570) 262-7631

Alpha job

Total 750 Zelle to Oren 
Parts 60 

Omri

---

77 Worthington Rd, White Plains, NY 10607
Basement door lockout 

Alpha job

400$

Nodi"""
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            parse_button = st.button("🔍 Parse Messages", type="primary")
        
        # Initialize parsed jobs in session state
        if 'parsed_jobs' not in st.session_state:
            st.session_state.parsed_jobs = []
        
        if parse_button and messages_text.strip():
            parser = MessageParser()
            st.session_state.parsed_jobs = parser.parse_multiple_jobs(messages_text)
        
        # Show parsed jobs if available
        if st.session_state.parsed_jobs:
            st.success(f"✅ Found {len(st.session_state.parsed_jobs)} jobs!")
            
            st.markdown("#### Parsed Jobs:")
            
            # Editable parsed jobs
            edited_jobs = []
            for i, pj in enumerate(st.session_state.parsed_jobs):
                with st.expander(f"Job {i+1}: {pj.total:.0f}$ - {pj.address[:40]}..." if len(pj.address) > 40 else f"Job {i+1}: {pj.total:.0f}$ - {pj.address}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Address:** {pj.address}")
                        st.write(f"**Total:** ${pj.total:,.2f}")
                        st.write(f"**Parts:** ${pj.parts:,.2f}")
                        st.write(f"**Payment:** {pj.payment_method.upper()}")
                    
                    with col2:
                        # Technician selection
                        detected_tech = pj.technician_name if pj.technician_name else ""
                        
                        if default_tech != "Auto-detect":
                            tech_name = default_tech
                        elif detected_tech:
                            tech_name = detected_tech
                        else:
                            tech_name = ""
                        
                        tech_input = st.text_input(
                            f"Technician for Job {i+1}",
                            value=tech_name,
                            key=f"tech_{i}",
                            help="Detected: " + (detected_tech if detected_tech else "None")
                        )
                        
                        if detected_tech:
                            st.caption(f"🔍 Auto-detected: **{detected_tech}**")
                    
                    edited_jobs.append({
                        'job': pj,
                        'technician': tech_input
                    })
            
            # Save all jobs button
            st.markdown("---")
            if st.button("💾 Save All Jobs", type="primary"):
                saved_count = 0
                for item in edited_jobs:
                    pj = item['job']
                    tech_name = item['technician'].strip()
                    
                    if not tech_name:
                        st.warning(f"⚠️ Skipping job at {pj.address[:30]}... - no technician specified")
                        continue
                    
                    # Get or create technician
                    tech = storage.get_or_create_technician(tech_name, commission_rate)
                    
                    # Create stored job
                    stored_job = StoredJob(
                        id="",  # Will be auto-generated
                        technician_id=tech['id'],
                        technician_name=tech['name'],
                        address=pj.address,
                        total=pj.total,
                        parts=pj.parts,
                        payment_method=pj.payment_method,
                        description=pj.description,
                        phone=pj.phone,
                        job_date=job_date.isoformat(),
                        created_at="",  # Will be auto-generated
                        is_paid=False,
                        commission_rate=commission_rate
                    )
                    
                    storage.add_job(stored_job)
                    saved_count += 1
                
                if saved_count > 0:
                    st.success(f"✅ Saved {saved_count} jobs!")
                    st.session_state.parsed_jobs = []
                    st.rerun()
        
        elif parse_button and not messages_text.strip():
            st.warning("⚠️ Please paste some messages first")
    
    # Tab 2: Manual Entry
    with tab2:
        st.markdown("#### Add a single job manually:")
        
        with st.form("manual_job_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                manual_date = st.date_input("Date", value=date.today())
                manual_address = st.text_input("Address *")
                manual_total = st.number_input("Total ($) *", min_value=0.0, step=10.0)
                manual_parts = st.number_input("Parts ($)", min_value=0.0, step=5.0, value=0.0)
            
            with col2:
                manual_tech = st.text_input("Technician Name *")
                manual_payment = st.selectbox("Payment Method", ["Cash", "Check", "Credit Card"])
                manual_phone = st.text_input("Phone (optional)")
                manual_description = st.text_input("Description (optional)")
            
            submitted = st.form_submit_button("💾 Save Job", type="primary")
            
            if submitted:
                if not manual_address or not manual_total or not manual_tech:
                    st.error("❌ Please fill in all required fields (Address, Total, Technician)")
                else:
                    payment_map = {"Cash": "cash", "Check": "check", "Credit Card": "cc"}
                    
                    # Get or create technician
                    tech = storage.get_or_create_technician(manual_tech.strip(), commission_rate)
                    
                    stored_job = StoredJob(
                        id="",
                        technician_id=tech['id'],
                        technician_name=tech['name'],
                        address=manual_address,
                        total=manual_total,
                        parts=manual_parts,
                        payment_method=payment_map[manual_payment],
                        description=manual_description,
                        phone=manual_phone,
                        job_date=manual_date.isoformat(),
                        created_at="",
                        is_paid=False,
                        commission_rate=commission_rate
                    )
                    
                    storage.add_job(stored_job)
                    st.success(f"✅ Job saved for {tech['name']}!")
                    st.rerun()


def page_manage_jobs():
    """Page for managing all jobs"""
    st.header("📊 Manage Jobs")
    
    # Get all data
    all_jobs = storage.get_all_jobs()
    technicians = storage.get_all_technicians()
    
    if not all_jobs:
        st.info("📭 No jobs saved yet. Go to 'Add Jobs' to add some!")
        return
    
    # Filters in sidebar
    st.sidebar.markdown("### 🔍 Filters")
    
    # Technician filter
    tech_options = ["All Technicians"] + [t['name'] for t in technicians]
    selected_tech = st.sidebar.selectbox("Technician", tech_options)
    
    # Date filter
    st.sidebar.markdown("#### Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=30))
    with col2:
        end_date = st.date_input("To", value=date.today())
    
    # Payment status filter
    payment_filter = st.sidebar.selectbox(
        "Payment Status",
        ["All", "Unpaid Only", "Paid Only"]
    )
    
    # Apply filters
    filtered_jobs = all_jobs
    
    if selected_tech != "All Technicians":
        filtered_jobs = [j for j in filtered_jobs if j.technician_name == selected_tech]
    
    filtered_jobs = [j for j in filtered_jobs if start_date.isoformat() <= j.job_date <= end_date.isoformat()]
    
    if payment_filter == "Unpaid Only":
        filtered_jobs = [j for j in filtered_jobs if not j.is_paid]
    elif payment_filter == "Paid Only":
        filtered_jobs = [j for j in filtered_jobs if j.is_paid]
    
    # Sort by date (newest first)
    filtered_jobs.sort(key=lambda x: x.job_date, reverse=True)
    
    # Summary stats
    st.markdown("### 📈 Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Jobs", len(filtered_jobs))
    with col2:
        total_sales = sum(j.total for j in filtered_jobs)
        st.metric("Total Sales", f"${total_sales:,.0f}")
    with col3:
        unpaid_count = len([j for j in filtered_jobs if not j.is_paid])
        st.metric("Unpaid Jobs", unpaid_count)
    with col4:
        unpaid_amount = sum(j.total - j.parts for j in filtered_jobs if not j.is_paid)
        st.metric("Unpaid Amount", f"${unpaid_amount:,.0f}")
    
    st.markdown("---")
    
    # Jobs table
    st.markdown(f"### 📋 Jobs ({len(filtered_jobs)})")
    
    if not filtered_jobs:
        st.info("No jobs match the selected filters.")
        return
    
    # Display jobs
    for job in filtered_jobs:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
            
            with col1:
                status_icon = "✅" if job.is_paid else "⏳"
                st.markdown(f"**{status_icon} {job.address[:40]}**{'...' if len(job.address) > 40 else ''}")
                st.caption(f"📅 {job.job_date} | 👤 {job.technician_name}")
            
            with col2:
                st.markdown(f"**${job.total:,.0f}**")
                if job.parts > 0:
                    st.caption(f"Parts: ${job.parts:,.0f}")
            
            with col3:
                st.markdown(f"**{job.payment_method.upper()}**")
            
            with col4:
                if job.is_paid:
                    if st.button("❌ Unpaid", key=f"unpaid_{job.id}"):
                        storage.mark_job_unpaid(job.id)
                        st.rerun()
                else:
                    if st.button("✅ Paid", key=f"paid_{job.id}"):
                        storage.mark_job_paid(job.id)
                        st.rerun()
            
            with col5:
                if st.button("🗑️", key=f"delete_{job.id}"):
                    storage.delete_job(job.id)
                    st.success("Job deleted!")
                    st.rerun()
            
            st.markdown("---")
    
    # Bulk actions
    st.markdown("### ⚡ Bulk Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Mark All Filtered as Paid"):
            for job in filtered_jobs:
                if not job.is_paid:
                    storage.mark_job_paid(job.id)
            st.success("All jobs marked as paid!")
            st.rerun()
    
    with col2:
        if st.button("❌ Mark All Filtered as Unpaid"):
            for job in filtered_jobs:
                if job.is_paid:
                    storage.mark_job_unpaid(job.id)
            st.success("All jobs marked as unpaid!")
            st.rerun()


def page_reports():
    """Page for generating reports"""
    st.header("📈 Generate Reports")
    
    technicians = storage.get_all_technicians()
    all_jobs = storage.get_all_jobs()
    
    if not technicians:
        st.info("📭 No technicians found. Add some jobs first!")
        return
    
    # Report settings
    st.sidebar.markdown("### 📊 Report Settings")
    
    selected_tech_name = st.sidebar.selectbox(
        "Select Technician",
        options=[t['name'] for t in technicians]
    )
    
    selected_tech = storage.get_technician_by_name(selected_tech_name)
    
    st.sidebar.markdown("#### Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=30), key="report_start")
    with col2:
        end_date = st.date_input("To", value=date.today(), key="report_end")
    
    include_paid = st.sidebar.checkbox("Include paid jobs", value=False)
    
    commission_rate = st.sidebar.slider(
        "Commission Rate (%)",
        min_value=0,
        max_value=100,
        value=int(selected_tech.get('commission_rate', 0.5) * 100),
        step=5
    ) / 100
    
    # Get jobs for report
    tech_jobs = storage.get_jobs_by_technician(selected_tech['id'])
    
    # Filter by date
    tech_jobs = [j for j in tech_jobs if start_date.isoformat() <= j.job_date <= end_date.isoformat()]
    
    # Filter by payment status
    if not include_paid:
        tech_jobs = [j for j in tech_jobs if not j.is_paid]
    
    # Sort by date
    tech_jobs.sort(key=lambda x: x.job_date)
    
    if not tech_jobs:
        st.warning(f"⚠️ No {'unpaid ' if not include_paid else ''}jobs found for {selected_tech_name} in this date range.")
        return
    
    st.success(f"📋 Found {len(tech_jobs)} jobs for **{selected_tech_name}**")
    
    # Convert StoredJobs to Job model for report generator
    jobs_for_report = []
    for sj in tech_jobs:
        job = Job(
            job_date=date.fromisoformat(sj.job_date),
            address=sj.address,
            total=sj.total,
            parts=sj.parts,
            payment_method=sj.payment_method,
            commission_rate=commission_rate,
            fee=0,
            cash_amount=sj.total if sj.payment_method == 'cash' else 0,
            cc_amount=sj.total if sj.payment_method == 'cc' else 0,
            check_amount=sj.total if sj.payment_method == 'check' else 0
        )
        jobs_for_report.append(job)
    
    # Create technician and generator
    technician = Technician(
        id=selected_tech['id'],
        name=selected_tech_name,
        commission_rate=commission_rate
    )
    
    generator = ReportGenerator(technician)
    generator.add_jobs(jobs_for_report)
    
    # Preview
    st.markdown("### 📊 Report Preview")
    
    df = generator.to_dataframe()
    st.dataframe(df, use_container_width=True)
    
    # Summary
    summary = generator.calculator.calculate_summary(generator.results)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Jobs", summary['job_count'])
    with col2:
        st.metric("Total Sales", f"${summary['total_sales']:,.2f}")
    with col3:
        st.metric("Tech Profit", f"${summary['total_tech_profit']:,.2f}")
    with col4:
        balance = summary['total_balance']
        if balance > 0:
            st.metric("Tech Owes", f"${balance:,.2f}", delta_color="inverse")
        else:
            st.metric("Company Owes", f"${abs(balance):,.2f}")
    
    # Download buttons
    st.markdown("---")
    st.markdown("### 📥 Download Report")
    
    # Generate HTML report
    html_exporter = HTMLReportExporter(technician)
    html_exporter.add_jobs(jobs_for_report)
    html_content = html_exporter.generate_html()
    
    timestamp = datetime.now().strftime('%Y%m%d')
    html_filename = f"{selected_tech_name.replace(' ', '_')}_{timestamp}.html"
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📄 Download HTML Report",
            data=html_content,
            file_name=html_filename,
            mime="text/html"
        )
    
    with col2:
        # Generate Excel file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            tmp_path = tmp.name
        
        generator.export_excel(tmp_path)
        with open(tmp_path, 'rb') as f:
            excel_data = f.read()
        
        try:
            Path(tmp_path).unlink()
        except:
            pass
        
        excel_filename = f"{selected_tech_name.replace(' ', '_')}_{timestamp}.xlsx"
        
        st.download_button(
            label="📊 Download Excel Report",
            data=excel_data,
            file_name=excel_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Option to mark jobs as paid after generating report
    st.markdown("---")
    if not include_paid and st.button("✅ Mark All Jobs in Report as Paid", type="primary"):
        for sj in tech_jobs:
            storage.mark_job_paid(sj.id)
        st.success(f"Marked {len(tech_jobs)} jobs as paid!")
        st.rerun()


def page_technicians():
    """Page for managing technicians"""
    st.header("👥 Manage Technicians")
    
    technicians = storage.get_all_technicians()
    
    if not technicians:
        st.info("📭 No technicians yet. They will be auto-created when you add jobs.")
    else:
        st.markdown("### Current Technicians")
        
        for tech in technicians:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    st.markdown(f"### 👤 {tech['name']}")
                
                with col2:
                    stats = storage.get_technician_stats(tech['id'])
                    st.metric("Total Jobs", stats['total_jobs'])
                
                with col3:
                    st.metric("Unpaid Jobs", stats['unpaid_jobs'])
                
                with col4:
                    # Only allow deletion if no jobs
                    if stats['total_jobs'] == 0:
                        if st.button("🗑️", key=f"del_tech_{tech['id']}"):
                            storage.delete_technician(tech['id'])
                            st.success("Technician deleted!")
                            st.rerun()
                    else:
                        st.caption("Has jobs")
                
                st.markdown("---")
    
    # Add new technician manually
    st.markdown("### ➕ Add Technician Manually")
    with st.form("add_tech_form"):
        new_name = st.text_input("Name")
        new_commission = st.slider("Default Commission Rate (%)", 0, 100, 50, 5)
        
        if st.form_submit_button("Add Technician"):
            if new_name.strip():
                existing = storage.get_technician_by_name(new_name)
                if existing:
                    st.warning(f"Technician '{new_name}' already exists!")
                else:
                    storage.add_technician(new_name.strip(), new_commission / 100)
                    st.success(f"Added technician: {new_name}")
                    st.rerun()
            else:
                st.error("Please enter a name")


def main():
    # Check authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        login_page()
        return
    
    st.set_page_config(
        page_title=f"{COMPANY_NAME} - Job Management",
        page_icon="🔐",
        layout="wide"
    )
    
    # Sidebar navigation
    st.sidebar.title(f"🔐 {COMPANY_NAME}")
    st.sidebar.markdown(f"👤 Logged in as: **{st.session_state.username}**")
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📝 Add Jobs", "📊 Manage Jobs", "📈 Reports", "👥 Technicians"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    
    # Page routing
    if page == "📝 Add Jobs":
        page_add_jobs()
    elif page == "📊 Manage Jobs":
        page_manage_jobs()
    elif page == "📈 Reports":
        page_reports()
    elif page == "👥 Technicians":
        page_technicians()


if __name__ == '__main__':
    main()
