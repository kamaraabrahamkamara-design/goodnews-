import os
from datetime import datetime
import pandas as pd
import streamlit as st
from supabase import Client, create_client

# Configure the Streamlit page layout for hosted environments
st.set_page_config(page_title="Mobile Money Ledger", layout="wide")

# Initialize Supabase Client securely using cached singletons
@st.cache_resource
def init_supabase() -> Client:
    # Pulls credentials from Streamlit secrets or environment variables
    url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        st.error("⚠️ Supabase credentials missing! Please configure SUPABASE_URL and SUPABASE_KEY in your settings.")
        st.stop()
    return create_client(url, key)

supabase = init_supabase()

# Display mappings to hide internal DB primary key IDs cleanly
DISPLAY_COLUMNS = {
    "created_at": "Date & Time",
    "tx_type": "Transaction Type",
    "customer_name": "Customer Name",
    "phone_number": "Phone Number",
    "amount": "Amount ($)",
    "tx_id": "Transaction ID (TxID)",
    "digital_float_bal": "Digital Float Bal ($)",
    "physical_cash_bal": "Physical Cash Bal ($)",
    "notes": "Notes"
}

def fetch_ledger_data() -> pd.DataFrame:
    """Fetches all ledger records from Supabase sorted chronologically (latest first)."""
    try:
        response = supabase.table("ledger").select("*").order("created_at", ascending=False).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Failed to fetch data from Supabase instance: {str(e)}")
        return pd.DataFrame()

# Fetch the live ledger array snapshot
db_df = fetch_ledger_data()

# Calculate running ledger parameters dynamically 
DEFAULT_INITIAL_FLOAT = 1000.0
DEFAULT_INITIAL_CASH = 1000.0

if not db_df.empty and "digital_float_bal" in db_df.columns:
    try:
        current_digital_float = float(db_df.iloc[0]["digital_float_bal"])
        current_physical_cash = float(db_df.iloc[0]["physical_cash_bal"])
    except (ValueError, KeyError, TypeError):
        current_digital_float = DEFAULT_INITIAL_FLOAT
        current_physical_cash = DEFAULT_INITIAL_CASH
else:
    current_digital_float = DEFAULT_INITIAL_FLOAT
    current_physical_cash = DEFAULT_INITIAL_CASH


def add_transaction(tx_type, name, phone, amount, tx_id, notes, current_float, current_cash):
    """Executes float math constraints and ships structured mutations securely to Supabase."""
    name = name.strip()
    phone = phone.strip()
    tx_id = tx_id.strip()

    if not name or not phone or not tx_id or amount <= 0:
        st.error("⚠️ Transaction failed: Please verify all required inputs are populated and amount exceeds 0.")
        return False

    amount = float(amount)

    # Core mobile money transaction vector mechanics
    if tx_type == "Deposit (Cash-In)":
        new_float = current_float - amount
        new_cash = current_cash + amount
    else:  # Withdrawal (Cash-Out)
        new_float = current_float + amount
        new_cash = current_cash - amount

    # Format ISO timestamp layout string explicitly for PostgreSQL schema compatibility
    now_str = datetime.now().isoformat()

    new_entry = {
        "created_at": now_str,
        "tx_type": tx_type,
        "customer_name": name,
        "phone_number": phone,
        "amount": amount,
        "tx_id": tx_id,
        "digital_float_bal": round(new_float, 2),
        "physical_cash_bal": round(new_cash, 2),
        "notes": notes.strip() if notes else ""
    }

    try:
        supabase.table("ledger").insert(new_entry).execute()
        return True
    except Exception as e:
        st.error(f"❌ Database update failure: {str(e)}")
        return False


# --- STREAMLIT DASHBOARD UI INTERFACE LAYOUT ---
st.title("📱 Mobile Money Digital Log Book")
st.markdown("A persistent production-grade ledger engine hosted live in the cloud.")

# Running balances metrics display container
metric_col1, metric_col2 = st.columns(2)
with metric_col1:
    st.metric(label="Current Digital Float ($)", value=f"${current_digital_float:,.2f}")
with metric_col2:
    st.metric(label="Current Physical Cash ($)", value=f"${current_physical_cash:,.2f}")

st.markdown("---")

left_panel, right_panel = st.columns([1, 1])

# Left Panel Component UI: Safe Form Processing Pipelines
with left_panel:
    st.markdown("### Log New Entry")
    
    with st.form("ledger_input_form", clear_on_submit=True):
        tx_type = st.radio(
            "Transaction Type", 
            ["Deposit (Cash-In)", "Withdrawal (Cash-Out)"], 
            index=0
        )
        cust_name = st.text_input("Customer Name", placeholder="e.g. Jane Smith")
        cust_phone = st.text_input("Phone Number", placeholder="e.g. +23177XXXXXX")
        amount = st.number_input("Transaction Amount ($)", min_value=0.0, step=1.0, value=0.0)
        tx_id = st.text_input("Transaction ID (TxID Reference)", placeholder="Paste provider confirmation token")
        notes = st.text_area("Notes / Remarks", placeholder="Optional operation log notes")

        submit_btn = st.form_submit_button("Add Entry & Update Log", type="primary")
        
        if submit_btn:
            success = add_transaction(
                tx_type, cust_name, cust_phone, amount, tx_id, notes, 
                current_digital_float, current_physical_cash
            )
            if success:
                st.toast("✅ Transaction added successfully!", icon="🎉")
                st.rerun()

# Right Panel Component UI: Cloud Ledger Viewports & Downloads
with right_panel:
    st.markdown("### Live Ledger Sheet (Cloud Database)")
    
    if not db_df.empty:
        # Format timestamps for display
        if "created_at" in db_df.columns:
            try:
                db_df["created_at"] = pd.to_datetime(db_df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        # Scrub database engineering keys, reorder columns, and display
        display_df = db_df.drop(columns=["id"], errors="ignore").rename(columns=DISPLAY_COLUMNS)
        desired_order = [col for col in DISPLAY_COLUMNS.values() if col in display_df.columns]
        display_df = display_df[desired_order]
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("### Export Complete Log Engine")
        csv_buffer = display_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download Log Ledger (CSV)",
            data=csv_buffer,
            file_name="mobile_money_ledger_cloud_export.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("Cloud storage schema verified. Ledger database instance is currently empty.")