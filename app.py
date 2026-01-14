"""Streamlit web interface for Alpha Locks Reports"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
import tempfile
from pathlib import Path

from src.models import Job, Technician
from src.report_generator import ReportGenerator
from src.data_loader import DataLoader
from config import COMPANY_NAME, DEFAULT_COMMISSION_RATE


def main():
    st.set_page_config(
        page_title=f"{COMPANY_NAME} - Reports",
        page_icon="🔐",
        layout="wide"
    )
    
    st.title(f"🔐 {COMPANY_NAME}")
    st.subheader("Technician Commission Reports")
    
    # Sidebar configuration
    st.sidebar.header("⚙️ Settings")
    
    technician_name = st.sidebar.text_input("Technician Name", value="")
    
    commission_rate = st.sidebar.slider(
        "Commission Rate (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5
    ) / 100
    
    st.sidebar.markdown("---")
    
    # Data input method
    input_method = st.radio(
        "How would you like to input job data?",
        ["📁 Upload Excel/CSV file", "✏️ Manual entry"],
        horizontal=True
    )
    
    jobs = []
    
    if input_method == "📁 Upload Excel/CSV file":
        uploaded_file = st.file_uploader(
            "Upload job data file",
            type=['xlsx', 'xls', 'csv']
        )
        
        if uploaded_file:
            # Save to temp file and load
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            try:
                if uploaded_file.name.endswith('.csv'):
                    jobs = DataLoader.load_from_csv(tmp_path, commission_rate)
                else:
                    jobs = DataLoader.load_from_excel(tmp_path, commission_rate)
                
                st.success(f"✅ Loaded {len(jobs)} jobs from file")
            except Exception as e:
                st.error(f"❌ Error loading file: {str(e)}")
            finally:
                Path(tmp_path).unlink()
    
    else:  # Manual entry
        st.markdown("### ➕ Add Jobs")
        
        # Session state for jobs
        if 'manual_jobs' not in st.session_state:
            st.session_state.manual_jobs = []
        
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
        
        jobs = st.session_state.manual_jobs
        
        if jobs:
            st.markdown(f"**{len(jobs)} jobs added**")
            if st.button("🗑️ Clear all jobs"):
                st.session_state.manual_jobs = []
                st.rerun()
    
    # Generate report
    st.markdown("---")
    
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
        
        # Generate Excel file in memory
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            generator.export_excel(tmp.name)
            with open(tmp.name, 'rb') as f:
                excel_data = f.read()
            Path(tmp.name).unlink()
        
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{technician_name.replace(' ', '_')}_{timestamp}.xlsx"
        
        st.download_button(
            label="📥 Download Excel Report",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    elif not technician_name:
        st.info("👈 Please enter the technician name in the sidebar")
    else:
        st.info("📁 Please upload a file or add jobs manually")


if __name__ == '__main__':
    main()
