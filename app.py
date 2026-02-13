"""
Alpha Locks Reports - Main Application with Job Management
"""
import streamlit as st
import streamlit.components.v1 as components
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


# Initialize storage (cached across reruns)
@st.cache_resource
def _get_storage():
    return JobStorage()

storage = _get_storage()


def inject_matomo():
    """Inject Matomo analytics tracking code."""
    components.html(
        """
        <!-- Matomo -->
        <script>
          var _paq = window._paq = window._paq || [];
          _paq.push(['trackPageView']);
          _paq.push(['enableLinkTracking']);
          (function() {
            var u="https://alphalockandsafe.matomo.cloud/";
            _paq.push(['setTrackerUrl', u+'matomo.php']);
            _paq.push(['setSiteId', '5']);
            var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
            g.async=true; g.src='https://cdn.matomo.cloud/alphalockandsafe.matomo.cloud/matomo.js'; s.parentNode.insertBefore(g,s);
          })();
        </script>
        <!-- End Matomo Code -->
        """,
        height=0,
    )


def _parsed_job_to_state(pj) -> dict:
    """Normalize ParsedJob objects into session-friendly dicts."""
    return {
        "address": pj.address,
        "total": pj.total,
        "parts": pj.parts,
        "payment_method": pj.payment_method,
        "description": pj.description,
        "phone": pj.phone,
        "job_date": pj.job_date.isoformat() if getattr(pj, "job_date", None) else "",
        "technician_name": getattr(pj, "technician_name", "") or "",
        # Split payment amounts
        "cash_amount": getattr(pj, "cash_amount", 0.0) or 0.0,
        "cc_amount": getattr(pj, "cc_amount", 0.0) or 0.0,
        "check_amount": getattr(pj, "check_amount", 0.0) or 0.0,
        "tech_amount": getattr(pj, "tech_amount", None),
    }


def render_edit_form(job, key_prefix: str):
    """Render inline edit form for a stored job. Used across all pages."""
    with st.container(border=True):
        st.markdown(f"#### ✏️ Editing Job")
        
        col1, col2 = st.columns(2)
        with col1:
            new_address = st.text_input("Address", value=job.address, key=f"e_addr_{key_prefix}_{job.id}")
            new_description = st.text_input("Description", value=job.description or "", key=f"e_desc_{key_prefix}_{job.id}")
            new_phone = st.text_input("Phone", value=job.phone or "", key=f"e_phone_{key_prefix}_{job.id}")
            try:
                date_val = date.fromisoformat(job.job_date)
            except (ValueError, TypeError):
                date_val = date.today()
            new_date = st.date_input("Date", value=date_val, key=f"e_date_{key_prefix}_{job.id}")
        
        with col2:
            technicians = storage.get_all_technicians()
            tech_names = [t['name'] for t in technicians]
            if job.technician_name and job.technician_name not in tech_names:
                tech_names.append(job.technician_name)
            tech_idx = tech_names.index(job.technician_name) if job.technician_name in tech_names else 0
            new_tech_name = st.selectbox("Technician", tech_names, index=tech_idx, key=f"e_tech_{key_prefix}_{job.id}")
            
            new_total = st.number_input("Total ($)", min_value=0.0, value=float(job.total), step=10.0, key=f"e_total_{key_prefix}_{job.id}")
            new_parts = st.number_input("Parts ($)", min_value=0.0, value=float(job.parts), step=5.0, key=f"e_parts_{key_prefix}_{job.id}")
            
            payment_options = ["cash", "check", "cc", "split"]
            pay_idx = payment_options.index(job.payment_method) if job.payment_method in payment_options else 0
            new_payment = st.selectbox("Payment Method", payment_options, index=pay_idx, key=f"e_pay_{key_prefix}_{job.id}")
        
        # Split amounts
        if new_payment == "split":
            st.markdown("##### 💳 Split Breakdown:")
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                new_cash = st.number_input("Cash ($)", min_value=0.0, value=float(job.cash_amount or 0), step=10.0, key=f"e_cash_{key_prefix}_{job.id}")
            with sc2:
                new_cc = st.number_input("CC ($)", min_value=0.0, value=float(job.cc_amount or 0), step=10.0, key=f"e_cc_{key_prefix}_{job.id}")
            with sc3:
                new_check_amt = st.number_input("Check ($)", min_value=0.0, value=float(job.check_amount or 0), step=10.0, key=f"e_chk_{key_prefix}_{job.id}")
            split_sum = new_cash + new_cc + new_check_amt
            if abs(split_sum - new_total) > 0.01 and split_sum > 0:
                st.warning(f"⚠️ Split amounts (${split_sum:.2f}) don't match total (${new_total:.2f})")
        else:
            new_cash = new_total if new_payment == "cash" else 0.0
            new_cc = new_total if new_payment == "cc" else 0.0
            new_check_amt = new_total if new_payment in ["check", "transfer"] else 0.0
        
        # Commission / Tech Amount
        cc1, cc2 = st.columns(2)
        with cc1:
            new_rate = st.slider("Commission Rate (%)", 0, 100, int((job.commission_rate or 0.5) * 100), 5, key=f"e_rate_{key_prefix}_{job.id}") / 100
        with cc2:
            ta_val = float(job.tech_amount) if getattr(job, 'tech_amount', None) else 0.0
            new_tech_amount = st.number_input(
                "Tech Fixed Amount ($)", min_value=0.0, value=ta_val, step=10.0,
                key=f"e_ta_{key_prefix}_{job.id}",
                help="If > 0, overrides commission rate with a fixed dollar amount for the tech"
            )
        
        new_notes = st.text_area("Notes", value=job.notes or "", key=f"e_notes_{key_prefix}_{job.id}", height=68)
        
        # Save / Cancel
        bcol1, bcol2, bcol3 = st.columns([1, 1, 3])
        with bcol1:
            if st.button("💾 Save", key=f"e_save_{key_prefix}_{job.id}", type="primary"):
                updates = {
                    'address': new_address.strip(),
                    'total': new_total,
                    'parts': new_parts,
                    'payment_method': new_payment,
                    'description': new_description.strip(),
                    'phone': new_phone.strip(),
                    'job_date': new_date.isoformat(),
                    'commission_rate': new_rate,
                    'tech_amount': new_tech_amount if new_tech_amount > 0 else None,
                    'notes': new_notes.strip(),
                    'cash_amount': new_cash,
                    'cc_amount': new_cc,
                    'check_amount': new_check_amt,
                }
                # Handle technician change
                if new_tech_name != job.technician_name:
                    tech_obj = storage.get_or_create_technician(new_tech_name.strip())
                    updates['technician_id'] = tech_obj['id']
                    updates['technician_name'] = tech_obj['name']
                
                storage.update_job(job.id, updates)
                st.session_state[f"editing_{job.id}"] = False
                st.success("✅ Job updated!")
                st.rerun()
        with bcol2:
            if st.button("❌ Cancel", key=f"e_cancel_{key_prefix}_{job.id}"):
                st.session_state[f"editing_{job.id}"] = False
                st.rerun()


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
        elif st.session_state.parsed_jobs and not isinstance(st.session_state.parsed_jobs[0], dict):
            # Normalize legacy ParsedJob objects
            st.session_state.parsed_jobs = [_parsed_job_to_state(pj) for pj in st.session_state.parsed_jobs]
        
        if parse_button and messages_text.strip():
            parser = MessageParser()
            parsed = parser.parse_multiple_jobs(messages_text)
            st.session_state.parsed_jobs = [_parsed_job_to_state(pj) for pj in parsed]
        
        # Show parsed jobs if available
        if st.session_state.parsed_jobs:
            st.success(f"✅ Found {len(st.session_state.parsed_jobs)} jobs!")
            
            st.markdown("#### Parsed Jobs:")
            
            # Editable parsed jobs
            edited_jobs = []
            remove_indices = []
            for i, pj_state in enumerate(st.session_state.parsed_jobs):
                job_state = pj_state if isinstance(pj_state, dict) else _parsed_job_to_state(pj_state)
                job_title = job_state.get("address", "")
                job_total = job_state.get("total", 0)
                title_text = f"Job {i+1}: {job_total:.0f}$ - {job_title[:40]}..." if len(job_title) > 40 else f"Job {i+1}: {job_total:.0f}$ - {job_title}"
                with st.expander(title_text, expanded=True):
                    col1, col2 = st.columns([3, 2])
                    
                    with col1:
                        address_input = st.text_input("Address", value=job_state.get("address", ""), key=f"addr_{i}")
                        description_input = st.text_area("Description", value=job_state.get("description", ""), key=f"desc_{i}", height=80)
                        phone_input = st.text_input("Phone", value=job_state.get("phone", ""), key=f"phone_{i}")
                    
                    with col2:
                        # Decide initial technician
                        detected_tech = job_state.get("technician_name", "")
                        if default_tech != "Auto-detect":
                            tech_default = default_tech
                        elif detected_tech:
                            tech_default = detected_tech
                        else:
                            tech_default = ""
                        tech_input = st.text_input(
                            f"Technician for Job {i+1}",
                            value=tech_default,
                            key=f"tech_{i}",
                            help=f"Detected: {detected_tech or 'None'}"
                        )
                        if detected_tech:
                            st.caption(f"🔍 Auto-detected: **{detected_tech}**")
                        # Date per job (fallback to sidebar date)
                        job_date_value = job_state.get("job_date")
                        try:
                            date_default = datetime.fromisoformat(job_date_value).date() if job_date_value else job_date
                        except ValueError:
                            date_default = job_date
                        job_date_input = st.date_input("Job Date", value=date_default, key=f"job_date_{i}")
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        total_input = st.number_input("Total ($)", min_value=0.0, value=float(job_state.get("total", 0) or 0), step=10.0, key=f"total_{i}")
                    with col_b:
                        parts_input = st.number_input("Parts ($)", min_value=0.0, value=float(job_state.get("parts", 0) or 0), step=5.0, key=f"parts_{i}")
                    with col_c:
                        pay_method = (job_state.get("payment_method") or "cash").lower()
                        payment_options = ["cash", "check", "cc", "split"]
                        payment_input = st.selectbox("Payment", payment_options, index=payment_options.index(pay_method if pay_method in payment_options else "cash"), key=f"payment_{i}")
                    
                    # Show split payment breakdown if payment is split
                    if payment_input == "split":
                        st.markdown("##### 💳 Split Payment Breakdown:")
                        split_col1, split_col2, split_col3 = st.columns(3)
                        with split_col1:
                            cash_amount_input = st.number_input("Cash ($)", min_value=0.0, value=float(job_state.get("cash_amount", 0) or 0), step=10.0, key=f"cash_amt_{i}")
                        with split_col2:
                            cc_amount_input = st.number_input("Credit Card ($)", min_value=0.0, value=float(job_state.get("cc_amount", 0) or 0), step=10.0, key=f"cc_amt_{i}")
                        with split_col3:
                            check_amount_input = st.number_input("Check ($)", min_value=0.0, value=float(job_state.get("check_amount", 0) or 0), step=10.0, key=f"check_amt_{i}")
                        # Validate split amounts match total
                        split_sum = cash_amount_input + cc_amount_input + check_amount_input
                        if abs(split_sum - total_input) > 0.01 and split_sum > 0:
                            st.warning(f"⚠️ Split amounts (${split_sum:.2f}) don't match total (${total_input:.2f})")
                    else:
                        cash_amount_input = total_input if payment_input == "cash" else 0.0
                        cc_amount_input = total_input if payment_input == "cc" else 0.0
                        check_amount_input = total_input if payment_input == "check" else 0.0

                    # Commission / Tech Amount override
                    comm_col1, comm_col2 = st.columns(2)
                    with comm_col1:
                        job_commission = st.slider(
                            "Commission Rate (%)", 0, 100, int(commission_rate * 100), 5,
                            key=f"comm_{i}"
                        ) / 100
                    with comm_col2:
                        tech_amt_default = float(job_state.get("tech_amount") or 0)
                        tech_amount_input = st.number_input(
                            "Tech Fixed Amount ($)", min_value=0.0, value=tech_amt_default, step=10.0,
                            key=f"techamt_{i}",
                            help="If set (>0), overrides commission rate with a fixed dollar amount for the tech"
                        )
                    if tech_amt_default > 0:
                        st.info(f"💡 Fixed tech amount detected: **${tech_amt_default:.0f}** (overrides {int(commission_rate*100)}% rate)")

                    if st.button("🗑️ Remove this job", key=f"remove_{i}"):
                        remove_indices.append(i)
                    
                    edited_jobs.append({
                        "address": address_input.strip(),
                        "total": total_input,
                        "parts": parts_input,
                        "payment_method": payment_input,
                        "description": description_input.strip(),
                        "phone": phone_input.strip(),
                        "job_date": job_date_input.isoformat(),
                        "technician_name": tech_input.strip(),
                        "cash_amount": cash_amount_input,
                        "cc_amount": cc_amount_input,
                        "check_amount": check_amount_input,
                        "tech_amount": tech_amount_input if tech_amount_input > 0 else None,
                        "commission_rate": job_commission,
                    })
            
            if remove_indices:
                st.session_state.parsed_jobs = [job for idx, job in enumerate(edited_jobs) if idx not in remove_indices]
                st.success(f"Removed {len(remove_indices)} job(s) from the parsed list.")
                st.rerun()
            else:
                st.session_state.parsed_jobs = edited_jobs
            
            # Save all jobs button
            st.markdown("---")
            if st.button("💾 Save All Jobs", type="primary"):
                saved_count = 0
                for job_data in edited_jobs:
                    tech_name = job_data['technician_name'].strip()
                    
                    if not tech_name:
                        st.warning(f"⚠️ Skipping job at {job_data['address'][:30]}... - no technician specified")
                        continue
                    if not job_data['address']:
                        st.warning("⚠️ Skipping a job with empty address")
                        continue
                    if not job_data['total']:
                        st.warning(f"⚠️ Skipping job at {job_data['address'][:30]}... - total is missing")
                        continue
                    
                    # Get or create technician
                    tech = storage.get_or_create_technician(tech_name, commission_rate)
                    
                    # Create stored job
                    stored_job = StoredJob(
                        id="",  # Will be auto-generated
                        technician_id=tech['id'],
                        technician_name=tech['name'],
                        address=job_data['address'],
                        total=job_data['total'],
                        parts=job_data['parts'],
                        payment_method=job_data['payment_method'],
                        description=job_data['description'],
                        phone=job_data['phone'],
                        job_date=job_data['job_date'] or job_date.isoformat(),
                        created_at="",  # Will be auto-generated
                        is_paid=False,
                        commission_rate=job_data.get('commission_rate', commission_rate),
                        cash_amount=job_data.get('cash_amount', 0.0),
                        cc_amount=job_data.get('cc_amount', 0.0),
                        check_amount=job_data.get('check_amount', 0.0),
                        tech_amount=job_data.get('tech_amount')
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
            
            col3, col4 = st.columns(2)
            with col3:
                manual_commission = st.slider("Commission Rate (%)", 0, 100, int(commission_rate * 100), 5, key="manual_comm") / 100
            with col4:
                manual_tech_amount = st.number_input(
                    "Tech Fixed Amount ($)", min_value=0.0, value=0.0, step=10.0,
                    key="manual_techamt",
                    help="If set (>0), overrides commission rate with a fixed dollar amount"
                )
            
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
                        commission_rate=manual_commission,
                        tech_amount=manual_tech_amount if manual_tech_amount > 0 else None
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
        if st.session_state.get(f"editing_{job.id}", False):
            render_edit_form(job, "manage")
            st.markdown("---")
        else:
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 1, 1, 1])
                
                with col1:
                    status_icon = "✅" if job.is_paid else "⏳"
                    st.markdown(f"**{status_icon} {job.address[:40]}**{'...' if len(job.address) > 40 else ''}")
                    caption_parts = [f"📅 {job.job_date}", f"👤 {job.technician_name}"]
                    if getattr(job, 'tech_amount', None):
                        caption_parts.append(f"💰 Tech: ${job.tech_amount:.0f}")
                    st.caption(" | ".join(caption_parts))
                
                with col2:
                    st.markdown(f"**${job.total:,.0f}**")
                    if job.parts > 0:
                        st.caption(f"Parts: ${job.parts:,.0f}")
                
                with col3:
                    st.markdown(f"**{job.payment_method.upper()}**")
                
                with col4:
                    if st.button("✏️", key=f"edit_{job.id}", help="Edit job"):
                        st.session_state[f"editing_{job.id}"] = True
                        st.rerun()
                
                with col5:
                    if job.is_paid:
                        if st.button("❌ Unpaid", key=f"unpaid_{job.id}"):
                            storage.mark_job_unpaid(job.id)
                            st.rerun()
                    else:
                        if st.button("✅ Paid", key=f"paid_{job.id}"):
                            storage.mark_job_paid(job.id)
                            st.rerun()
                
                with col6:
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
            unpaid_ids = [job.id for job in filtered_jobs if not job.is_paid]
            if unpaid_ids:
                storage.mark_jobs_paid(unpaid_ids)
            st.success("All jobs marked as paid!")
            st.rerun()
    
    with col2:
        if st.button("❌ Mark All Filtered as Unpaid"):
            paid_ids = [job.id for job in filtered_jobs if job.is_paid]
            if paid_ids:
                storage.mark_jobs_unpaid(paid_ids)
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
        # Use stored split amounts if available, otherwise default based on payment method
        if sj.payment_method == 'split':
            cash_amt = getattr(sj, 'cash_amount', 0) or 0
            cc_amt = getattr(sj, 'cc_amount', 0) or 0
            check_amt = getattr(sj, 'check_amount', 0) or 0
        else:
            cash_amt = sj.total if sj.payment_method == 'cash' else 0
            cc_amt = sj.total if sj.payment_method == 'cc' else 0
            check_amt = sj.total if sj.payment_method == 'check' else 0
        
        job = Job(
            job_date=date.fromisoformat(sj.job_date),
            address=sj.address,
            total=sj.total,
            parts=sj.parts,
            payment_method=sj.payment_method,
            commission_rate=commission_rate,
            fee=0,
            cash_amount=cash_amt,
            cc_amount=cc_amt,
            check_amount=check_amt,
            tech_amount=getattr(sj, 'tech_amount', None)
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
    
    # Editable job list
    with st.expander("📝 Edit Individual Jobs", expanded=False):
        for sj in tech_jobs:
            if st.session_state.get(f"editing_{sj.id}", False):
                render_edit_form(sj, "report")
            else:
                with st.container():
                    rc1, rc2, rc3 = st.columns([4, 2, 1])
                    with rc1:
                        st.markdown(f"**{sj.address[:40]}**{'...' if len(sj.address) > 40 else ''}")
                        cap = f"📅 {sj.job_date} | {sj.payment_method.upper()}"
                        if getattr(sj, 'tech_amount', None):
                            cap += f" | 💰 Tech: ${sj.tech_amount:.0f}"
                        st.caption(cap)
                    with rc2:
                        st.markdown(f"${sj.total:,.0f}")
                        if sj.parts > 0:
                            st.caption(f"Parts: ${sj.parts:,.0f}")
                    with rc3:
                        if st.button("✏️", key=f"edit_r_{sj.id}", help="Edit job"):
                            st.session_state[f"editing_{sj.id}"] = True
                            st.rerun()
            st.markdown("---")
    
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
        unpaid_ids = [sj.id for sj in tech_jobs if not sj.is_paid]
        if unpaid_ids:
            storage.mark_jobs_paid(unpaid_ids)
        st.success(f"Marked {len(tech_jobs)} jobs as paid!")
        st.rerun()


def page_technicians():
    """Page for managing technicians with detailed view"""
    st.header("👥 Technicians")
    
    technicians = storage.get_all_technicians()
    
    if not technicians:
        st.info("📭 No technicians yet. They will be auto-created when you add jobs.")
        return
    
    # Initialize selected technician in session state
    if 'selected_tech_id' not in st.session_state:
        st.session_state.selected_tech_id = None
    
    # Two-column layout: list on left, details on right
    col_list, col_details = st.columns([1, 2])
    
    with col_list:
        st.markdown("### 📋 Technicians List")
        
        for tech in technicians:
            stats = storage.get_technician_stats(tech['id'])
            
            # Create a button for each technician
            is_selected = st.session_state.selected_tech_id == tech['id']
            button_type = "primary" if is_selected else "secondary"
            
            with st.container():
                col_name, col_badge = st.columns([3, 1])
                with col_name:
                    if st.button(
                        f"👤 {tech['name']}", 
                        key=f"select_{tech['id']}", 
                        type=button_type,
                        use_container_width=True
                    ):
                        st.session_state.selected_tech_id = tech['id']
                        st.rerun()
                with col_badge:
                    if stats['unpaid_jobs'] > 0:
                        st.markdown(f"<span style='background-color: #ff4b4b; padding: 2px 8px; border-radius: 10px; color: white; font-size: 12px;'>{stats['unpaid_jobs']} unpaid</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Add new technician
        with st.expander("➕ Add New Technician"):
            new_name = st.text_input("Name", key="new_tech_name")
            new_commission = st.slider("Commission Rate (%)", 0, 100, 50, 5, key="new_tech_comm")
            
            if st.button("Add Technician", type="primary"):
                if new_name.strip():
                    existing = storage.get_technician_by_name(new_name)
                    if existing:
                        st.warning(f"'{new_name}' already exists!")
                    else:
                        storage.add_technician(new_name.strip(), new_commission / 100)
                        st.success(f"Added: {new_name}")
                        st.rerun()
                else:
                    st.error("Please enter a name")
    
    with col_details:
        if st.session_state.selected_tech_id:
            show_technician_details(st.session_state.selected_tech_id)
        else:
            st.info("👈 Select a technician to view details")


def show_technician_details(tech_id: str):
    """Show detailed view for a technician"""
    tech = storage.get_technician_by_id(tech_id)
    if not tech:
        st.error("Technician not found")
        return
    
    stats = storage.get_technician_stats(tech_id)
    jobs = storage.get_jobs_by_technician(tech_id)
    
    # Header with technician name
    st.markdown(f"## 👤 {tech['name']}")
    
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Jobs", stats['total_jobs'])
    with col2:
        st.metric("Total Sales", f"${stats['total_sales']:,.0f}")
    with col3:
        st.metric("Unpaid Jobs", stats['unpaid_jobs'])
    with col4:
        st.metric("Unpaid Amount", f"${stats['unpaid_amount']:,.0f}")
    
    st.markdown("---")
    
    # Tabs for different views
    tab_jobs, tab_report = st.tabs(["📋 Jobs", "📈 Generate Report"])
    
    with tab_jobs:
        # Filter options
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            show_paid = st.checkbox("Show paid jobs", value=False, key=f"show_paid_{tech_id}")
        with col_filter2:
            date_filter = st.selectbox(
                "Date Range",
                ["All Time", "This Week", "This Month", "Last 30 Days"],
                key=f"date_filter_{tech_id}"
            )
        
        # Filter jobs
        filtered_jobs = jobs
        if not show_paid:
            filtered_jobs = [j for j in filtered_jobs if not j.is_paid]
        
        # Date filtering
        if date_filter == "This Week":
            week_start = date.today() - timedelta(days=date.today().weekday())
            filtered_jobs = [j for j in filtered_jobs if j.job_date >= week_start.isoformat()]
        elif date_filter == "This Month":
            month_start = date.today().replace(day=1)
            filtered_jobs = [j for j in filtered_jobs if j.job_date >= month_start.isoformat()]
        elif date_filter == "Last 30 Days":
            start = date.today() - timedelta(days=30)
            filtered_jobs = [j for j in filtered_jobs if j.job_date >= start.isoformat()]
        
        # Sort by date (newest first)
        filtered_jobs.sort(key=lambda x: x.job_date, reverse=True)
        
        if not filtered_jobs:
            st.info("No jobs found with current filters.")
        else:
            st.markdown(f"**{len(filtered_jobs)} jobs**")
            
            for job in filtered_jobs:
                if st.session_state.get(f"editing_{job.id}", False):
                    render_edit_form(job, "tech")
                else:
                    with st.container():
                        col1, col2, col3, col4, col5 = st.columns([4, 2, 1, 1, 1])
                        
                        with col1:
                            status = "✅" if job.is_paid else "⏳"
                            addr_display = job.address[:35] + "..." if len(job.address) > 35 else job.address
                            st.markdown(f"{status} **{addr_display}**")
                            caption_txt = f"📅 {job.job_date}"
                            if getattr(job, 'tech_amount', None):
                                caption_txt += f" | 💰 Tech: ${job.tech_amount:.0f}"
                            st.caption(caption_txt)
                        
                        with col2:
                            st.markdown(f"**${job.total:,.0f}**")
                            if job.parts > 0:
                                st.caption(f"Parts: ${job.parts:,.0f}")
                        
                        with col3:
                            if st.button("✏️", key=f"edit_t_{job.id}", help="Edit job"):
                                st.session_state[f"editing_{job.id}"] = True
                                st.rerun()
                        
                        with col4:
                            if job.is_paid:
                                if st.button("❌", key=f"unpay_{job.id}", help="Mark as unpaid"):
                                    storage.mark_job_unpaid(job.id)
                                    st.rerun()
                            else:
                                if st.button("✅", key=f"pay_{job.id}", help="Mark as paid"):
                                    storage.mark_job_paid(job.id)
                                    st.rerun()
                        
                        with col5:
                            if st.button("🗑️", key=f"del_{job.id}", help="Delete job"):
                                storage.delete_job(job.id)
                                st.rerun()
                
                st.markdown("---")
            
            # Bulk actions
            st.markdown("#### ⚡ Bulk Actions")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Mark All as Paid", key=f"mark_all_paid_{tech_id}"):
                    unpaid_ids = [job.id for job in filtered_jobs if not job.is_paid]
                    if unpaid_ids:
                        storage.mark_jobs_paid(unpaid_ids)
                    st.success("All jobs marked as paid!")
                    st.rerun()
    
    with tab_report:
        st.markdown("### 📈 Generate Report")
        
        # Report options
        col1, col2 = st.columns(2)
        with col1:
            report_start = st.date_input("From Date", value=date.today() - timedelta(days=30), key=f"rep_start_{tech_id}")
        with col2:
            report_end = st.date_input("To Date", value=date.today(), key=f"rep_end_{tech_id}")
        
        include_paid_report = st.checkbox("Include paid jobs in report", value=False, key=f"inc_paid_{tech_id}")
        
        commission_rate = st.slider(
            "Commission Rate (%)",
            min_value=0,
            max_value=100,
            value=int(tech.get('commission_rate', 0.5) * 100),
            step=5,
            key=f"comm_{tech_id}"
        ) / 100
        
        # Get jobs for report
        report_jobs = [j for j in jobs if report_start.isoformat() <= j.job_date <= report_end.isoformat()]
        if not include_paid_report:
            report_jobs = [j for j in report_jobs if not j.is_paid]
        
        report_jobs.sort(key=lambda x: x.job_date)
        
        if not report_jobs:
            st.warning("No jobs found for selected criteria.")
        else:
            st.success(f"📋 Found **{len(report_jobs)}** jobs for report")
            
            # Summary
            total_sales = sum(j.total for j in report_jobs)
            total_parts = sum(j.parts for j in report_jobs)
            net = total_sales - total_parts
            tech_profit = net * commission_rate
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Sales", f"${total_sales:,.0f}")
            with col2:
                st.metric("Net (after parts)", f"${net:,.0f}")
            with col3:
                st.metric("Tech Profit", f"${tech_profit:,.0f}")
            
            st.markdown("---")
            
            # Convert to Job model for report
            jobs_for_report = []
            for sj in report_jobs:
                # Use stored split amounts if available, otherwise default based on payment method
                if sj.payment_method == 'split':
                    cash_amt = getattr(sj, 'cash_amount', 0) or 0
                    cc_amt = getattr(sj, 'cc_amount', 0) or 0
                    check_amt = getattr(sj, 'check_amount', 0) or 0
                else:
                    cash_amt = sj.total if sj.payment_method == 'cash' else 0
                    cc_amt = sj.total if sj.payment_method == 'cc' else 0
                    check_amt = sj.total if sj.payment_method == 'check' else 0
                
                job = Job(
                    job_date=date.fromisoformat(sj.job_date),
                    address=sj.address,
                    total=sj.total,
                    parts=sj.parts,
                    payment_method=sj.payment_method,
                    commission_rate=commission_rate,
                    fee=0,
                    cash_amount=cash_amt,
                    cc_amount=cc_amt,
                    check_amount=check_amt,
                    tech_amount=getattr(sj, 'tech_amount', None)
                )
                jobs_for_report.append(job)
            
            technician_obj = Technician(
                id=tech['id'],
                name=tech['name'],
                commission_rate=commission_rate
            )
            
            # Generate reports
            html_exporter = HTMLReportExporter(technician_obj)
            html_exporter.add_jobs(jobs_for_report)
            html_content = html_exporter.generate_html()
            
            timestamp = datetime.now().strftime('%Y%m%d')
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📄 Download HTML Report",
                    data=html_content,
                    file_name=f"{tech['name'].replace(' ', '_')}_{timestamp}.html",
                    mime="text/html",
                    key=f"dl_html_{tech_id}"
                )
            
            with col2:
                generator = ReportGenerator(technician_obj)
                generator.add_jobs(jobs_for_report)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    tmp_path = tmp.name
                generator.export_excel(tmp_path)
                with open(tmp_path, 'rb') as f:
                    excel_data = f.read()
                try:
                    Path(tmp_path).unlink()
                except:
                    pass
                
                st.download_button(
                    label="📊 Download Excel Report",
                    data=excel_data,
                    file_name=f"{tech['name'].replace(' ', '_')}_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_excel_{tech_id}"
                )
            
            st.markdown("---")
            
            if not include_paid_report:
                if st.button("✅ Mark All Jobs in Report as Paid", type="primary", key=f"mark_report_paid_{tech_id}"):
                    unpaid_ids = [sj.id for sj in report_jobs if not sj.is_paid]
                    if unpaid_ids:
                        storage.mark_jobs_paid(unpaid_ids)
                    st.success(f"Marked {len(report_jobs)} jobs as paid!")
                    st.rerun()


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
    
    # Analytics
    inject_matomo()
    
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
