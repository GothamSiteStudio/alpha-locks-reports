"""Streamlit web interface for Alpha Locks Reports"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
import tempfile
from pathlib import Path

from src.models import Job, Technician
from src.report_generator import ReportGenerator
from src.html_exporter import HTMLReportExporter
from src.data_loader import DataLoader
from src.message_parser import MessageParser
from config import COMPANY_NAME, DEFAULT_COMMISSION_RATE
from auth_config import verify_password


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


def main():
    # Check authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        login_page()
        return
    
    st.set_page_config(
        page_title=f"{COMPANY_NAME} - Reports",
        page_icon="🔐",
        layout="wide"
    )
    
    st.title(f"🔐 {COMPANY_NAME}")
    st.subheader("Technician Commission Reports")
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Settings")
    
    # Show logged in user and logout button
    st.sidebar.markdown(f"👤 Logged in as: **{st.session_state.username}**")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
    
    st.sidebar.markdown("---")
    
    technician_name = st.sidebar.text_input("Technician Name", value="")
    
    commission_rate = st.sidebar.slider(
        "Commission Rate (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5
    ) / 100
    
    # Session state for jobs
    if 'manual_jobs' not in st.session_state:
        st.session_state.manual_jobs = []
    
    # Input method tabs
    tab1, tab2 = st.tabs(["📋 Paste Messages", "✏️ Manual Entry"])
    
    # Tab 1: Paste Messages
    with tab1:
        st.markdown("### 📋 Paste Job Closure Messages")
        st.markdown("Paste your job closure messages below. The app will automatically extract the data.")
        
        messages_text = st.text_area(
            "Paste messages here:",
            height=300,
            placeholder="""Example:
27 Deepwood Hill St, Chappaqua, NY 10514
locks change 
(847) 444-9779
alpha job
$446
Parts $15

15 E Franklin St, Tarrytown, NY 10591 
Hlo
+1 (917) 584-6993
Alpha Job
Total cash 1231 
Parts 30"""
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
            
            # Show parsed jobs for confirmation
            st.markdown("#### Parsed Jobs:")
            for i, pj in enumerate(st.session_state.parsed_jobs):
                with st.expander(f"Job {i+1}: {pj.address[:50]}..." if len(pj.address) > 50 else f"Job {i+1}: {pj.address}"):
                    st.write(f"**Address:** {pj.address}")
                    st.write(f"**Total:** ${pj.total:,.2f}")
                    st.write(f"**Parts:** ${pj.parts:,.2f}")
                    st.write(f"**Payment:** {pj.payment_method.upper()}")
                    if pj.description:
                        st.write(f"**Description:** {pj.description}")
            
            # Add all parsed jobs button
            if st.button("✅ Add All Jobs to Report", type="primary"):
                for pj in st.session_state.parsed_jobs:
                    new_job = Job(
                        job_date=date.today(),
                        address=pj.address,
                        total=pj.total,
                        parts=pj.parts,
                        payment_method=pj.payment_method,
                        commission_rate=commission_rate,
                        fee=0,
                        cash_amount=pj.total if pj.payment_method == 'cash' else 0,
                        cc_amount=pj.total if pj.payment_method == 'cc' else 0,
                        check_amount=pj.total if pj.payment_method == 'check' else 0
                    )
                    st.session_state.manual_jobs.append(new_job)
                added_count = len(st.session_state.parsed_jobs)
                st.session_state.parsed_jobs = []  # Clear parsed jobs
                st.success(f"✅ Added {added_count} jobs!")
                st.rerun()
        
        elif parse_button and messages_text.strip():
            st.warning("⚠️ Could not parse any jobs. Make sure messages contain address, 'alpha job', and price.")
    
    # Tab 2: Manual Entry
    with tab2:
        st.markdown("### ✏️ Add Job Manually")
    
        with st.form("add_job_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                job_date = st.date_input("Date", value=date.today())
                address = st.text_input("Address")
                total = st.number_input("Total ($)", min_value=0.0, step=10.0)
            
            with col2:
                parts = st.number_input("Parts ($)", min_value=0.0, step=5.0)
                payment = st.selectbox("Payment Method", ["Cash", "Credit Card", "Check", "Bank Transfer"])
                fee = st.number_input("Processing Fee ($)", min_value=0.0, step=1.0)
            
            submitted = st.form_submit_button("➕ Add Job")
            
            if submitted and address and total > 0:
                payment_map = {
                    "Cash": "cash",
                    "Credit Card": "cc",
                    "Check": "check",
                    "Bank Transfer": "transfer"
                }
                
                new_job = Job(
                    job_date=job_date,
                    address=address,
                    total=total,
                    parts=parts,
                    payment_method=payment_map[payment],
                    commission_rate=commission_rate,
                    fee=fee,
                    cash_amount=total if payment == "Cash" else 0,
                    cc_amount=total if payment == "Credit Card" else 0,
                    check_amount=total if payment in ["Check", "Bank Transfer"] else 0
                )
                st.session_state.manual_jobs.append(new_job)
                st.success("✅ Job added!")
                st.rerun()
    
    # Show current jobs
    jobs = st.session_state.manual_jobs
    
    st.markdown("---")
    if jobs:
        st.markdown(f"### 📝 Current Jobs ({len(jobs)})")
        
        # Show jobs table preview
        jobs_preview = []
        for j in jobs:
            jobs_preview.append({
                'Address': j.address[:40] + '...' if len(j.address) > 40 else j.address,
                'Total': f"${j.total:,.0f}",
                'Parts': f"${j.parts:,.0f}" if j.parts > 0 else '-',
                'Payment': j.payment_method.upper()
            })
        st.dataframe(jobs_preview, use_container_width=True, hide_index=True)
        
        if st.button("🗑️ Clear all jobs"):
            st.session_state.manual_jobs = []
            st.session_state.parsed_jobs = []
            st.rerun()
    
    # Generate report
    st.markdown("---")
    
    if jobs and not technician_name:
        st.warning("⚠️ Please enter the **Technician Name** in the sidebar to generate the report")
    
    if jobs and technician_name:
        st.markdown("### 📊 Report Preview")
        
        technician = Technician(
            id='tech',
            name=technician_name,
            commission_rate=commission_rate
        )
        
        generator = ReportGenerator(technician)
        generator.add_jobs(jobs)
        
        # Preview table
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
        
        # Download button
        st.markdown("---")
        st.markdown("### 📥 Download Report")
        
        # Generate HTML report
        html_exporter = HTMLReportExporter(technician)
        html_exporter.add_jobs(jobs)
        html_content = html_exporter.generate_html()
        
        timestamp = datetime.now().strftime('%Y%m%d')
        html_filename = f"{technician_name.replace(' ', '_')}_{timestamp}.html"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📄 Download HTML Report",
                data=html_content,
                file_name=html_filename,
                mime="text/html"
            )
        
        with col2:
            # Generate Excel file in memory
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp_path = tmp.name
            
            generator.export_excel(tmp_path)
            with open(tmp_path, 'rb') as f:
                excel_data = f.read()
            
            try:
                Path(tmp_path).unlink()
            except:
                pass  # Ignore if file is locked
            
            excel_filename = f"{technician_name.replace(' ', '_')}_{timestamp}.xlsx"
            
            st.download_button(
                label="📊 Download Excel Report",
                data=excel_data,
                file_name=excel_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    elif not technician_name:
        st.info("👈 Please enter the technician name in the sidebar")
    else:
        st.info("📁 Please upload a file or add jobs manually")


if __name__ == '__main__':
    main()
