import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ==========================================
# 1. DATABASE CONFIGURATION & CONNECTION
# ==========================================
# Replace these with your actual Supabase project credentials (found in project settings)
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_URL = "https://your-actual-id.supabase.co"
SUPABASE_KEY = "your-actual-long-anon-key-here"
@st.cache_resource
def init_supabase() -> Client:
    """Initializes and caches the Supabase client connection."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    st.stop()

# ==========================================
# 2. CORE FINANCIAL & LOGIC FUNCTIONS
# ==========================================
def calculate_metrics(base_points: int, insurance_payout: float, monthly_bonus: float = 0.0) -> dict:
    """
    Automates the commission structure math.
    - Base Points: $360 per point
    - Insurance Commission: 4% of total payout
    - Tax Reserve: 30% of total gross commission
    """
    base_comm = base_points * 360
    ins_comm = insurance_payout * 0.04
    total_gross = base_comm + ins_comm + monthly_bonus
    tax_reserve = total_gross * 0.30
    net_profit = total_gross - tax_reserve
    
    return {
        "base_comm": base_comm,
        "ins_comm": ins_comm,
        "total_gross": total_gross,
        "tax_reserve": tax_reserve,
        "net_profit": net_profit
    }

def get_priority_color(stage: str) -> str:
    """Maps the 7 stages to a clear, scannable visual priority tier."""
    if stage in ["2: Inspections Scheduled/Completed", "3: Adjuster Meeting Pending"]:
        return "HOT"
    elif stage in ["4: Approved & Contract Signed", "5: Production & Build Pending"]:
        return "WARM"
    else:
        return "COLD"

def color_rows(row):
    """Applies soft CSS background styles to the dataframe based on lead warmth."""
    if row["Lead Warmth Priority"] == "HOT":
        return ["background-color: #FFC7CE; color: black"] * len(row)
    elif row["Lead Warmth Priority"] == "WARM":
        return ["background-color: #FFEB9C; color: black"] * len(row)
    elif row["Lead Warmth Priority"] == "COLD":
        return ["background-color: #E2EFDA; color: black"] * len(row)
    return [""] * len(row)

# ==========================================
# 3. STREAMLIT UI ARCHITECTURE
# ==========================================
st.set_page_config(page_title="Rose Roofing Pipeline Tracker", layout="wide")
st.title("🦅 Rose Roofing High-Velocity Sales Pipeline")
st.markdown("---")

# --- SIDEBAR: LEADS INPUT FORM ---
st.sidebar.header("Add / Update Lead Details")

with st.sidebar.form(key="lead_form", clear_on_submit=True):
    lead_id = st.number_input("Lead ID", min_value=1, step=1, value=1)
    address = st.text_input("Street Address", placeholder="123 Maple St")
    city = st.text_input("City", placeholder="Cumberland")
    state = st.selectbox("State", ["MD", "PA", "WV"])
    zip_code = st.text_input("Zip Code", max_chars=5)
    homeowner_name = st.text_input("Homeowner Name")
    
    stage = st.selectbox("Current Stage", [
        "1: Raw Prospecting / Cold Drop",
        "2: Inspections Scheduled/Completed",
        "3: Adjuster Meeting Pending",
        "4: Approved & Contract Signed",
        "5: Production & Build Pending",
        "6: Invoiced & Waiting on Final Payout",
        "7: Closed, Paid & Referral Engine"
    ])
    
    base_points = st.number_input("Base Points (Usually 1)", min_value=0, step=1, value=1)
    ins_payout_est = st.number_input("Insurance Payout Estimate ($)", min_value=0.0, step=500.0, value=13000.0)
    monthly_bonus = st.number_input("Manual Monthly Bonus Addition ($)", min_value=0.0, step=100.0, value=0.0)
    notes = st.text_area("Operational Notes")
    
    submit_button = st.form_submit_button(label="Sync Lead to Cloud")

# Handle Form Submission to Supabase
if submit_button:
    metrics = calculate_metrics(base_points, ins_payout_est, monthly_bonus)
    priority = get_priority_color(stage)
    
    payload = {
        "id": lead_id,
        "address": address,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "current_stage": stage,
        "priority": priority,
        "homeowner_name": homeowner_name,
        "base_points": base_points,
        "base_comm": metrics["base_comm"],
        "insurance_payout_est": ins_payout_est,
        "ins_comm": metrics["ins_comm"],
        "monthly_bonus": monthly_bonus,
        "total_gross_comm": metrics["total_gross"],
        "tax_reserve": metrics["tax_reserve"],
        "net_profit": metrics["net_profit"],
        "notes": notes
    }
    
    # Upsert pattern updates existing record if ID match is found, otherwise creates new
    response = supabase.table("roofing_pipeline").upsert(payload).execute()
    st.sidebar.success(f"Successfully processed Entry ID {lead_id}!")

# --- MAIN DASHBOARD VIEW ---

# Pull Data from Supabase
db_query = supabase.table("roofing_pipeline").select("*").order("id", ascending=True).execute()
data_records = db_query.data

if not data_records:
    st.info("Your pipeline is currently empty. Input raw drops in the sidebar to populate data.")
else:
    # Build clean Dataframe from DB records
    raw_df = pd.DataFrame(data_records)
    
    # Rename columns to match formatting hierarchy
    display_df = raw_df.rename(columns={
        "id": "ID", "address": "Address", "city": "City", "state": "State", "zip_code": "Zip Code",
        "current_stage": "Current Stage", "priority": "Lead Warmth Priority", 
        "homeowner_name": "Homeowner Name", "base_points": "Base Points",
        "base_comm": "Base Points Commission ($)", "insurance_payout_est": "Insurance Payout Est ($)",
        "ins_comm": "4% Insurance Comm ($)", "monthly_bonus": "Monthly Bonus ($)",
        "total_gross_comm": "Total Gross Comm ($)", "tax_reserve": "30% Tax Set-Aside ($)",
        "net_profit": "Estimated Net Profit ($)", "notes": "Notes"
    })
    
    # Re-order columns for clean visual flow
    cols_order = [
        "ID", "Address", "City", "State", "Zip Code", "Current Stage", "Lead Warmth Priority",
        "Homeowner Name", "Base Points", "Insurance Payout Est ($)", "4% Insurance Comm ($)",
        "Monthly Bonus ($)", "Total Gross Comm ($)", "Notes"
    ]
    
    # --- METRICS SUMMARY CARDS (Top of Dashboard) ---
    st.subheader("Financial Performance Block")
    
    total_volume = raw_df["insurance_payout_est"].sum()
    total_gross = raw_df["total_gross_comm"].sum()
    total_tax = raw_df["tax_reserve"].sum()
    total_net = raw_df["net_profit"].sum()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Active Pipeline Volume", f"${total_volume:,.2f}")
    m2.metric("Total Projected Gross Income", f"${total_gross:,.2f}")
    m3.metric("30% Tax Set-Aside Reserve", f"${total_tax:,.2f}", delta="-Tax Owed", delta_color="inverse")
    m4.metric("Estimated Net Profit (Take-Home)", f"${total_net:,.2f}", delta="Clean Cash")
    
    st.markdown("---")
    
    # --- DATA TABLE VIEW ---
    st.subheader("Master Pipeline Records")
    
    # Apply dynamic CSS injection to highlight data rows based on calculated warmth
    styled_df = display_df[cols_order].style.apply(color_rows, axis=1)
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
