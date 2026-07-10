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
    st.session_state.user_role = None  # Can be "Admin" or "Supervisor"

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

@st.cache_data(ttl=0)
def load_notes_data():
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
        notes_sheet = client.open_by_url(spreadsheet_url).worksheet("Notes")
        
        data = notes_sheet.get_all_records()
        return pd.DataFrame(data), notes_sheet
    except Exception as e:
        return pd.DataFrame(), None

# --- WRITE BACK VIA GSPREAD ---
def save_dataframe_to_gsheet(df_to_save):
    if sheet_api_client is not None:
        try:
            df_copy = df_to_save.copy()
            if 'outreach_date' in df_copy.columns:
                df_copy['outreach_date'] = df_copy['outreach_date'].dt.strftime('%Y-%m-%d')
            
            df_copy = df_copy.fillna("")
            sheet_api_client.clear()
            sheet_api_client.update(values=[df_copy.columns.values.tolist()] + df_copy.values.tolist())
            return True
        except Exception as e:
            st.error(f"Error updating deployment logs: {e}")
            return False
    return False

# --- FETCH DATA ---
df_deployments, sheet_api_client = load_data()
df_notes, sheet_notes_client = load_notes_data()

if not df_deployments.empty:
    if 'outreach_date' in df_deployments.columns:
        df_deployments['outreach_date'] = pd.to_datetime(df_deployments['outreach_date'], errors='coerce')

# --- DROPDOWN OPTIONS ---
RISK_OPTIONS = ["Gun Shot Wound (GSW)", "Assault", "Stabbing"]
INTEL_OPTIONS = ["ShotSpotter", "BPD Intel", "HBVI Intel", "Community Intelligence"]
NEIGHBORHOOD_OPTIONS = ["East Bakersfield", "Southeast Bakersfield", "Central Bakersfield", "Oildale", "Delano", "Other"]

def get_pill_html(text):
    colors = {
        "Gun Shot Wound (GSW)": {"bg": "#fee2e2", "text": "#991b1b"},
        "Assault": {"bg": "#fef9c3", "text": "#854d0e"},
        "Stabbing": {"bg": "#ffedd5", "text": "#c2410c"},
        "ShotSpotter": {"bg": "#e0f2fe", "text": "#0369a1"},
        "BPD Intel": {"bg": "#e0e7ff", "text": "#3730a3"},
        "HBVI Intel": {"bg": "#f3e8ff", "text": "#6b21a8"}
    }
    cfg = colors.get(text, {"bg": "#e2e8f0", "text": "#1e293b"})
    return f'<span style="background-color: {cfg["bg"]}; color: {cfg["text"]}; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-right: 4px; display: inline-block;">{text}</span>'


# =========================================================================
# 🔐 GATED INTERFACE CONTROL
# =========================================================================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 CVI Operational Gateway</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #6b7280;'>Please authenticate to open the intake sheets and tracker systems.</p>", unsafe_allow_html=True)
    
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
                    admin_pass, super_pass = "admin123", "super123" # Fallbacks for local environment
                
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
# 📊 APP MAIN DASHBOARD (UNLOCKED)
# =========================================================================
st.title("𝄃 CVI Strategic Outreach & Deployment Dashboard")
st.write("Coordinating community violence intervention street deployment metrics based on intelligence data grids.")

# --- METRICS HEADERS ---
st.markdown("### 📊 High-Impact Footprint Summary")
col1, col2, col3, col4 = st.columns(4)

if not df_deployments.empty:
    total_hot_zones = len(df_deployments['location'].dropna().unique())
    total_engaged = int(pd.to_numeric(df_deployments['members_engaged'], errors='coerce').sum())
    total_staff = int(pd.to_numeric(df_deployments['staff_count'], errors='coerce').sum())
    total_hours = float(pd.to_numeric(df_deployments['hours_deployed'], errors='coerce').sum())
else:
    total_hot_zones, total_engaged, total_staff, total_hours = 0, 0, 0, 0

col1.metric(label="Unique Hot Zones Addressed", value=total_hot_zones)
col2.metric(label="Community Members Engaged", value=total_engaged)
col3.metric(label="Staff Deployments (Cumulative)", value=total_staff)
col4.metric(label="Total Hours on the Block", value=f"{total_hours} hrs")

st.markdown("---")

# --- NEW TAB STRUCTURE ---
tab1, tab2, tab3 = st.tabs([
    "➕ Log New Deployment Zone", 
    "🎯 Recent Intel Deployments", 
    "🔍 Search & Manage Field History"
])

# --- TAB 1: FORM FIRST ---
with tab1:
    st.header("➕ Record New Deployment Entry")
    
    # Restrict form additions to Admin role if preferred, otherwise open to both
    if st.session_state.user_role in ["Admin", "Supervisor"]:
        with st.form("new_deployment_form", clear_on_submit=True):
            n_loc = st.text_input("Location / Neighborhood Street (e.g. Panorama Drive)")
            n_risk = st.selectbox("Triggering Risk Type", RISK_OPTIONS)
            n_intel = st.selectbox("Strategic Intel Source", INTEL_OPTIONS)
            
            nc1, nc2, nc3 = st.columns(3)
            with nc1:
                n_engaged = st.number_input("Community Members Engaged", min_value=0, value=0)
            with nc2:
                n_staff = st.number_input("Staff Members Attending", min_value=1, value=1)
            with nc3:
                n_hours = st.number_input("Hours Spent on Site", min_value=0.0, step=0.5, value=1.0)
            
            n_date = st.date_input("Deployment Date", datetime.date.today())
            n_concerns = st.text_area("Why was outreach conducted? (Share services, listen to safety issues, resident counts)")
            
            submit_new = st.form_submit_button("Submit Deployment to Tracker", use_container_width=True)
            
            if submit_new and n_loc:
                next_id = int(df_deployments['id'].max() + 1) if not df_deployments.empty and 'id' in df_deployments.columns else 1
                
                new_row = {
                    "id": next_id,
                    "location": n_loc,
                    "risk_type": n_risk,
                    "outreach_date": pd.to_datetime(n_date), 
                    "intel_source": n_intel,
                    "members_engaged": n_engaged,
                    "staff_count": n_staff,
                    "hours_deployed": n_hours,
                    "community_concerns": n_concerns
                }
                
                if df_deployments.empty:
                    updated_df = pd.DataFrame([new_row])
                else:
                    updated_df = pd.concat([df_deployments, pd.DataFrame([new_row])], ignore_index=True)
                
                if save_dataframe_to_gsheet(updated_df):
                    st.cache_data.clear()
                    st.success("New deployment successfully appended to Google Sheet!")
                    st.rerun()
    else:
        st.warning("Your credential clearance level does not authorize record appending access.")

# --- TAB 2: RECENT INTEL DEPLOYMENTS ---
with tab2:
    st.header("Recent Intel Deployments")
    if df_deployments.empty:
        st.info("No deployments registered in the sheet.")
    else:
        latest_deployments = df_deployments.sort_values(by="outreach_date", ascending=False).head(5)
        for idx, row in latest_deployments.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    date_str = row['outreach_date'].strftime('%b %d, %Y') if pd.notna(row['outreach_date']) else "Date Pending"
                    st.markdown(f"### {row['location']} — `{date_str}`")
                    
                    risk_pill = get_pill_html(row['risk_type'])
                    intel_pill = get_pill_html(row['intel_source'])
                    st.markdown(f"{risk_pill}{intel_pill}", unsafe_allow_html=True)
                    
                    st.markdown(f"**Community Concerns & Purpose Summary:**")
                    st.write(row['community_concerns'])
                with c2:
                    st.markdown("⚡ **Operational Specs**")
                    st.markdown(f"👥 **Engaged:** {row['members_engaged']} neighbors")
                    st.markdown(f"👷‍♂️ **Staff Attended:** {row['staff_count']} members")
                    st.markdown(f"⏳ **Duration:** {row['hours_deployed']} hrs")

# --- TAB 3: SEARCH & MANAGE HISTORY ---
with tab3:
    st.header("Search & Manage Field History")
    if df_deployments.empty:
        st.info("No deployment history to manage.")
    else:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            sel_risk = st.selectbox("Filter by Incident Type", ["All"] + RISK_OPTIONS, key="filter_risk")
        with f_col2:
            sel_intel = st.selectbox("Filter by Intel Trigger", ["All"] + INTEL_OPTIONS, key="filter_intel")
        with f_col3:
            search_query = st.text_input("Search Location/Keyword", key="filter_search").strip().lower()

        filtered_df = df_deployments.copy()
        if sel_risk != "All":
            filtered_df = filtered_df[filtered_df["risk_type"] == sel_risk]
        if sel_intel != "All":
            filtered_df = filtered_df[filtered_df["intel_source"] == sel_intel]
        if search_query:
            filtered_df = filtered_df[
                filtered_df["location"].astype(str).str.lower().str.contains(search_query) |
                filtered_df["community_concerns"].astype(str).str.lower().str.contains(search_query)
            ]

        st.markdown("---")

        for idx, row in filtered_df.iterrows():
            formatted_date = row['outreach_date'].strftime('%Y-%m-%d') if pd.notna(row['outreach_date']) else ''
            with st.expander(f"📍 {row['location']} ({row['risk_type']}) — {formatted_date}"):
                
                # Both roles can edit logs based on the authorization rule
                if st.session_state.user_role in ["Admin", "Supervisor"]:
                    with st.form(key=f"edit_form_{idx}"):
                        e_loc = st.text_input("Location / Neighborhood", value=row['location'])
                        e_risk = st.selectbox("Incident Type (Risk Type)", RISK_OPTIONS, index=RISK_OPTIONS.index(row['risk_type']) if row['risk_type'] in RISK_OPTIONS else 0)
                        e_intel = st.selectbox("Intel Trigger Source", INTEL_OPTIONS, index=INTEL_OPTIONS.index(row['intel_source']) if row['intel_source'] in INTEL_OPTIONS else 0)
                        
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1:
                            e_engaged = st.number_input("Community Members Engaged", min_value=0, value=int(row['members_engaged']) if pd.notna(row['members_engaged']) else 0)
                        with ec2:
                            e_staff = st.number_input("Staff Count Attended", min_value=0, value=int(row['staff_count']) if pd.notna(row['staff_count']) else 0)
                        with ec3:
                            e_hours = st.number_input("Total Hours Deployed", min_value=0.0, step=0.5, value=float(row['hours_deployed']) if pd.notna(row['hours_deployed']) else 0.0)
                        
                        e_concerns = st.text_area("Community Concerns & Field Notes", value=row['community_concerns'])
                        
                        save_btn = st.form_submit_button("Update Data Row")
                        if save_btn:
                            df_deployments.at[idx, 'location'] = e_loc
                            df_deployments.at[idx, 'risk_type'] = e_risk
                            df_deployments.at[idx, 'intel_source'] = e_intel
                            df_deployments.at[idx, 'members_engaged'] = e_engaged
                            df_deployments.at[idx, 'staff_count'] = e_staff
                            df_deployments.at[idx, 'hours_deployed'] = e_hours
                            df_deployments.at[idx, 'community_concerns'] = e_concerns
                            
                            if save_dataframe_to_gsheet(df_deployments):
                                st.cache_data.clear()
                                st.success("Google Sheets entries synchronized!")
                                st.rerun()
                else:
                    st.markdown(f"**Intel Trigger:** {row['intel_source']}")
                    st.markdown(f"👥 **Engaged:** {row['members_engaged']} residents | 👷‍♂️ **Staff:** {row['staff_count']} members | ⏳ **Time:** {row['hours_deployed']} hrs")
                    st.info(f"**Field Log:** {row['community_concerns']}")
