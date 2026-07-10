import streamlit as st
import pandas as pd
import datetime
from google.oauth2.service_account import Credentials
import gspread

# --- APP CONFIGURATION ---
st.set_page_config(page_title="CVI Strategic Outreach Tracker", page_icon="🚓", layout="wide")

# --- INITIALIZE SESSION STATE FOR AUTH ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None  # Tracks "Admin" or "Supervisor"

# --- DATABASE CONNECTION (Google Sheets via Dynamic Secrets & gspread) ---
@st.cache_data(ttl=0)  
def load_data():
    try:
        raw_key = st.secrets["connections"]["gsheets"]["private_key"]
        private_key = raw_key.replace("\\n", "\n")
        while "\n\n" in private_key:
            private_key = private_key.replace("\n\n", "\n")

        info = {
            "type": "service_account",
            "project_id": st.secrets["connections"]["gsheets"]["project_id"],
            "private_key_id": st.secrets["connections"]["gsheets"]["private_key_id"],
            "private_key": private_key,
            "client_email": st.secrets["connections"]["gsheets"]["client_email"],
            "client_id": st.secrets["connections"]["gsheets"]["client_id"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets["connections"]["gsheets"]["client_x509_cert_url"],
            "universe_domain": "googleapis.com"
        }

        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)

        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet = client.open_by_url(spreadsheet_url).sheet1
        
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet

    except Exception as e:
        st.error(f"Failed to connect to Deployment sheet: {e}")
        return pd.DataFrame(), None

# --- WRITE BACK VIA GSPREAD ---
def save_dataframe_to_gsheet(df_to_save):
    if sheet_api_client is not None:
        try:
            # 1. Pull the live text array from the sheet to locate the exact row index of "END"
            raw_ids = sheet_api_client.col_values(1) # Gets all values from the first column (Id)
            
            end_row_number = None
            for idx, val in enumerate(raw_ids):
                if str(val).strip().upper() == "END":
                    end_row_number = idx + 1 # Google Sheets is 1-indexed
                    break
            
            # 2. Grab only the very last row appended to our Dataframe (the one the user just typed)
            new_entry = df_to_save.iloc[-1].copy()
            
            # Format the date cleanly before pushing
            if 'Date' in new_entry and pd.notna(new_entry['Date']):
                new_entry['Date'] = pd.to_datetime(new_entry['Date']).strftime('%Y-%m-%d')
            
            new_entry = new_entry.fillna("")
            new_row_payload = new_entry.values.tolist()
            
            if end_row_number is not None:
                # 🌟 INJECT A NEW ROW DIRECTLY ABOVE THE "END" MARKER ROW
                # This automatically pushes row 14 to row 15, preserving everything below it!
                sheet_api_client.insert_row(new_row_payload, index=end_row_number, value_input_option="USER_ENTERED")
            else:
                # Fallback safeguard: if "END" went missing, append at the absolute bottom
                sheet_api_client.append_row(new_row_payload, value_input_option="USER_ENTERED")
                
            return True
            
        except Exception as e:
            st.error(f"Error updating deployment logs: {e}")
            return False
    return False  
    
# --- FETCH DATA ---
df_deployments, sheet_api_client = load_data()

if not df_deployments.empty:
    # 1. Clean up hidden spaces from headers
    df_deployments.columns = df_deployments.columns.str.strip()
    
    # Convert ID to string to safely look for the word "END"
    id_series = df_deployments['Id'].astype(str).str.strip().str.upper()
    
    if "END" in id_series.values:
        # Find the first row index where "END" appears
        end_index = id_series[id_series == "END"].index[0]
        # Only keep rows *before* this index
        df_deployments = df_deployments.iloc[:end_index]
    
    # 3. Double-check to clean any trailing phantom/blank rows before that marker
    df_deployments = df_deployments[
        (df_deployments['Location'].astype(str).str.strip() != "") & 
        (df_deployments['Location'].notna())
    ]
    
    if 'Date' in df_deployments.columns:
        df_deployments['Date'] = pd.to_datetime(df_deployments['Date'], errors='coerce')


# --- DROPDOWN OPTIONS MAPPED TO YOUR NEW CONFIGURATION ---
LOCATION_OPTIONS = ["East Bakersfield", "Southeast Bakersfield", "Central Bakersfield", "Oildale", "Delano", "Other"]
TRIGGER_OPTIONS = ["Gun Shot Wound (GSW)", "Assault", "Stabbing", "Shooting", "Community Tension", "Retaliatory Conflict"]
INTEL_OPTIONS = ["ShotSpotter", "BPD Intel", "HBVI Intel", "Community Intelligence"]


def safe_int(val, default=0):
    try:
        if pd.isna(val) or str(val).strip() == '':
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or str(val).strip() == '':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default
        

# =========================================================================
# 🔐 GATED INTERFACE CONTROL
# =========================================================================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 CVI Operational Gateway</h2>", unsafe_allow_html=True)
    
    _, auth_col, _ = st.columns([1, 2, 1])
    with auth_col:
        with st.form("login_gateway"):
            input_password = st.text_input("Enter Access Password", type="password")
            submit_login = st.form_submit_button("Authenticate & Enter", use_container_width=True)
            
            if submit_login:
                try:
                    admin_pass = st.secrets["ADMIN_PASSWORD"]
                    super_pass = st.secrets["SUPERVISOR_PASSWORD"]
                except KeyError:
                    admin_pass, super_pass = "admin123", "super123"
                
                if input_password == admin_pass:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Admin"
                    st.rerun()
                elif input_password == super_pass:
                    st.session_state.logged_in = True
                    st.session_state.user_role = "Supervisor"
                    st.rerun()
                else:
                    st.error("Invalid passcode credential. Connection refused.")
    st.stop()

# --- LOGOUT CONTROL IN SIDEBAR ---
st.sidebar.title("🔐 Security Status")
st.sidebar.info(f"Signed in as: **{st.session_state.user_role}**")
if st.sidebar.button("Log Out / Lock Console"):
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.rerun()


# =========================================================================
# 📊 MAIN DASHBOARD SYSTEM
# =========================================================================
st.title("𝄃 CVI Strategic Outreach & Deployment Dashboard")

# --- HIGH IMPACT SUMMARY ---
st.markdown("### 📊 High-Impact Footprint Summary")
col1, col2, col3, col4 = st.columns(4)

if not df_deployments.empty:
    total_hot_zones = len(df_deployments['Location'].dropna().unique()) if 'Location' in df_deployments.columns else 0
    total_engaged = int(pd.to_numeric(df_deployments['Community Member Engaged'], errors='coerce').sum()) if 'Community Member Engaged' in df_deployments.columns else 0
    total_staff = int(pd.to_numeric(df_deployments['Staff Count Attended'], errors='coerce').sum()) if 'Staff Count Attended' in df_deployments.columns else 0
    total_hours = float(pd.to_numeric(df_deployments['Total Hours Deployed'], errors='coerce').sum()) if 'Total Hours Deployed' in df_deployments.columns else 0
else:
    total_hot_zones, total_engaged, total_staff, total_hours = 0, 0, 0, 0

col1.metric(label="Unique Hot Zones Addressed", value=total_hot_zones)
col2.metric(label="Community Members Engaged", value=total_engaged)
col3.metric(label="Staff Deployments (Cumulative)", value=total_staff)
col4.metric(label="Total Hours on the Block", value=f"{total_hours} hrs")

st.markdown("---")

# --- TAB LAYOUT SYSTEM ---
tab1, tab2, tab3 = st.tabs([
    "➕ Log New Deployment Zone", 
    "🎯 Recent Intel Deployments", 
    "🔍 Search & Manage Field History"
])

# --- TAB 1: NEW ENTRY FORM FIRST ---
with tab1:
    st.header("➕ Record New Deployment Entry")
    
    with st.form("new_deployment_form", clear_on_submit=True):
        n_loc = st.selectbox("Location", LOCATION_OPTIONS)
        n_neigh = st.text_input("Neighborhood")
        n_date = st.date_input("Date of Incident", datetime.date.today())
        
        n_trigger = st.selectbox("Trigger Incident", TRIGGER_OPTIONS)
        n_intel = st.selectbox("Intel / Source", INTEL_OPTIONS)
        
        nc1, nc2, nc3 = st.columns(3)
        with nc1:
            n_engaged = st.number_input("Community Member Engaged", min_value=0, value=0)
        with nc2:
            n_staff = st.number_input("Staff Count Attended", min_value=1, value=1)
        with nc3:
            n_hours = st.number_input("Total Hours Deployed", min_value=0.0, step=0.5, value=1.0)
            
        n_concerns = st.text_area("Community Concerns / Purpose")
        
        submit_new = st.form_submit_button("Submit Deployment to Tracker", use_container_width=True)

        if submit_new:
            # Calculate next numeric ID based on active deployments
            next_id = int(df_deployments['Id'].max() + 1) if not df_deployments.empty and 'Id' in df_deployments.columns else 1
            
            new_row = {
                "Id": next_id,
                "Location": n_loc,
                "Neighborhood": n_neigh,
                "Date": pd.to_datetime(n_date), 
                "Trigger Incident": n_trigger,
                "Intel / Source": n_intel,
                "Community Member Engaged": n_engaged,
                "Staff Count Attended": n_staff,
                "Total Hours Deployed": n_hours,
                "Author": st.session_state.user_role, 
                "Community Concerns / Purpose": n_concerns
            }
            
            if df_deployments.empty:
                updated_df = pd.DataFrame([new_row])
            else:
                updated_df = pd.concat([df_deployments, pd.DataFrame([new_row])], ignore_index=True)
            
            # This safely injects the data right above your END row layout
            if save_dataframe_to_gsheet(updated_df):
                st.cache_data.clear()
                st.success("New deployment entry recorded safely right above your template boundary!")
                st.rerun()
        
# --- TAB 2: RECENT INTEL DEPLOYMENTS ---
with tab2:
    st.header("Recent Intel Deployments")
    if df_deployments.empty:
        st.info("No deployments registered in the sheet.")
    else:
        latest_deployments = df_deployments.sort_values(by="Date", ascending=False).head(5)
        for idx, row in latest_deployments.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    date_str = row['Date'].strftime('%b %d, %Y') if pd.notna(row['Date']) else "Date Pending"
                    st.markdown(f"### {row['Location']} ({row['Neighborhood']}) — `{date_str}`")
                    st.caption(f"Logged by Author: **{row['Author']}**")
                    st.markdown(f"**Trigger:** {row['Trigger Incident']} | **Source:** {row['Intel / Source']}")
                    st.markdown(f"**Summary:**")
                    st.write(row['Community Concerns / Purpose'])
                with c2:
                    st.markdown("⚡ **Operational Specs**")
                    st.markdown(f"👥 **Engaged:** {row['Community Member Engaged']} neighbors")
                    st.markdown(f"👷‍♂️ **Staff:** {row['Staff Count Attended']} members")
                    st.markdown(f"⏳ **Duration:** {row['Total Hours Deployed']} hrs")

# --- TAB 3: SEARCH & MANAGE HISTORY ---
with tab3:
    st.header("Search & Manage Field History")
    if df_deployments.empty:
        st.info("No deployment history to manage.")
    else:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            sel_trigger = st.selectbox("Filter by Trigger", ["All"] + TRIGGER_OPTIONS)
        with f_col2:
            sel_intel = st.selectbox("Filter by Intel Source", ["All"] + INTEL_OPTIONS)
        with f_col3:
            search_query = st.text_input("Search Neighborhood/Keyword").strip().lower()

        filtered_df = df_deployments.copy()
        if sel_trigger != "All":
            filtered_df = filtered_df[filtered_df["Trigger Incident"] == sel_trigger]
        if sel_intel != "All":
            filtered_df = filtered_df[filtered_df["Intel / Source"] == sel_intel]
        if search_query:
            filtered_df = filtered_df[
                filtered_df["Neighborhood"].astype(str).str.lower().str.contains(search_query) |
                filtered_df["Community Concerns / Purpose"].astype(str).str.lower().str.contains(search_query)
            ]

        st.markdown("---")

        for idx, row in filtered_df.iterrows():
            formatted_date = row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else ''
            with st.expander(f"📍 {row['Location']} ({row['Neighborhood']}) — {formatted_date}"):
                with st.form(key=f"edit_form_{idx}"):
                    e_loc = st.selectbox("Location", LOCATION_OPTIONS, index=LOCATION_OPTIONS.index(row['Location']) if row['Location'] in LOCATION_OPTIONS else 0)
                    e_neigh = st.text_input("Neighborhood", value=row['Neighborhood'])
                    e_trigger = st.selectbox("Trigger Incident", TRIGGER_OPTIONS, index=TRIGGER_OPTIONS.index(row['Trigger Incident']) if row['Trigger Incident'] in TRIGGER_OPTIONS else 0)
                    e_intel = st.selectbox("Intel / Source", INTEL_OPTIONS, index=INTEL_OPTIONS.index(row['Intel / Source']) if row['Intel / Source'] in INTEL_OPTIONS else 0)
                    
                    ec1, ec2, ec3 = st.columns(3)
                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        e_engaged = st.number_input(
                            "Community Member Engaged", 
                            min_value=0, 
                            value=safe_int(row.get('Community Member Engaged', 0))
                        )
                    with ec2:
                        e_staff = st.number_input(
                            "Staff Count Attended", 
                            min_value=0, 
                            value=safe_int(row.get('Staff Count Attended', 0))
                        )
                    with ec3:
                        e_hours = st.number_input(
                            "Total Hours Deployed", 
                            min_value=0.0, 
                            step=0.5, 
                            value=safe_float(row.get('Total Hours Deployed', 0.0))
                        )
                    
                    
                    save_btn = st.form_submit_button("Update Data Row")
                    if save_btn:
                        df_deployments.at[idx, 'Location'] = e_loc
                        df_deployments.at[idx, 'Neighborhood'] = e_neigh
                        df_deployments.at[idx, 'Trigger Incident'] = e_trigger
                        df_deployments.at[idx, 'Intel / Source'] = e_intel
                        df_deployments.at[idx, 'Community Member Engaged'] = e_engaged
                        df_deployments.at[idx, 'Staff Count Attended'] = e_staff
                        df_deployments.at[idx, 'Total Hours Deployed'] = e_hours
                        df_deployments.at[idx, 'Community Concerns / Purpose'] = e_concerns
                        
                        if save_dataframe_to_gsheet(df_deployments):
                            st.cache_data.clear()
                            st.success("Google Sheets row synchronized successfully!")
                            st.rerun()
