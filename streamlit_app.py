import streamlit as st
import pandas as pd
import datetime
from google.oauth2.service_account import Credentials
import gspread

# --- APP CONFIGURATION ---
st.set_page_config(page_title="CVI Strategic Outreach Tracker", page_icon="🚓", layout="wide")

# --- DATABASE CONNECTION (Google Sheets via Dynamic Secrets & gspread) ---
@st.cache_data(ttl=0)  # Setting to 0 for instant testing updates!
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


def save_notes_to_gsheet(df_notes_to_save, notes_api_client):
    if notes_api_client is not None:
        try:
            notes_api_client.clear()
            notes_api_client.update([df_notes_to_save.columns.values.tolist()] + df_notes_to_save.values.tolist())
            return True
        except Exception as e:
            st.error(f"Error saving field logs: {e}")
            return False
    return False

# --- FETCH & PREPARE DATA ---
df_deployments, sheet_api_client = load_data()
df_notes, sheet_notes_client = load_notes_data()

# Clean and normalize columns
if not df_deployments.empty:
    if 'outreach_date' in df_deployments.columns:
        df_deployments['outreach_date'] = pd.to_datetime(df_deployments['outreach_date'], errors='coerce')

# --- WRITE BACK VIA GSPREAD ---
def save_dataframe_to_gsheet(df_to_save):
    if sheet_api_client is not None:
        try:
            df_copy = df_to_save.copy()
            if 'outreach_date' in df_copy.columns:
                df_copy['outreach_date'] = df_copy['outreach_date'].dt.strftime('%Y-%m-%d')
            
            sheet_api_client.clear()
            sheet_api_client.update(values=[df_copy.columns.values.tolist()] + df_copy.values.tolist())
            return True
        except Exception as e:
            st.error(f"Error updating deployment logs: {e}")
            return False
    return False

# --- SECURITY PORTAL ---
st.sidebar.title("🔐 Authentication Portal")
admin_password = st.sidebar.text_input("Enter Admin Password", type="password")
supervisor_password = st.sidebar.text_input("Enter Supervisor Password", type="password")

IS_ADMIN = False
IS_SUPERVISOR = False

if admin_password:
    try:
        if admin_password == st.secrets["ADMIN_PASSWORD"]:
            IS_ADMIN = True
            st.sidebar.success("👑 Admin Mode Active")
    except KeyError:
        if admin_password == "testpass":
            IS_ADMIN = True
            st.sidebar.success("Local Test Auth Active!")

if supervisor_password:
    try:
        if supervisor_password == st.secrets["SUPERVISOR_PASSWORD"]:
            IS_SUPERVISOR = True
            st.sidebar.success("📋 Supervisor Mode Active")
    except KeyError:
        if supervisor_password == "superpass":
            IS_SUPERVISOR = True
            st.sidebar.success("Local Test Supervisor Active!")

HAS_EDIT_ACCESS = IS_ADMIN or IS_SUPERVISOR

# --- UPDATED DROPDOWN CONTROLS (Based on Boss's Feedback) ---
RISK_OPTIONS = ["Gun Shot Wound (GSW)", "Assault", "Stabbing"]
INTEL_OPTIONS = ["ShotSpotter", "BPD Intel", "HBVI Intel", "Community Intelligence"]
NEIGHBORHOOD_OPTIONS = ["East Bakersfield", "Southeast Bakersfield", "Central Bakersfield", "Oildale", "Delano", "Other"]

# --- COLOR-CODED PILLS ---
def get_pill_html(text):
    colors = {
        "Gun Shot Wound (GSW)": {"bg": "#fee2e2", "text": "#991b1b"}, # Red
        "Assault": {"bg": "#fef9c3", "text": "#854d0e"},              # Yellow
        "Stabbing": {"bg": "#ffedd5", "text": "#c2410c"},             # Orange
        "ShotSpotter": {"bg": "#e0f2fe", "text": "#0369a1"},          # Blue
        "BPD Intel": {"bg": "#e0e7ff", "text": "#3730a3"},            # Indigo
        "HBVI Intel": {"bg": "#f3e8ff", "text": "#6b21a8"}            # Purple
    }
    cfg = colors.get(text, {"bg": "#e2e8f0", "text": "#1e293b"})
    return f'<span style="background-color: {cfg["bg"]}; color: {cfg["text"]}; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-right: 4px; display: inline-block;">{text}</span>'

# --- MAIN INTERFACE ---
st.title("𝄃 CVI Strategic Outreach & Deployment Dashboard")
st.write("Coordinating community violence intervention street deployment metrics based on intelligence data grids.")

# --- METRICS SECTION (Total Volume of Community Impact) ---
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

# --- TAB DEFINITIONS ---
tabs_list = ["🎯 Active Operational Views", "🔍 Detailed Search & Edit Logs"]
if IS_ADMIN:
    tabs_list.append("➕ Log New Deployment Zone")

tabs = st.tabs(tabs_list)
tab1, tab2 = tabs[0], tabs[1]
tab3 = tabs[2] if IS_ADMIN else None

# --- TAB 1: ACTIVE OPERATIONAL VIEWS ---
with tab1:
    st.header("Recent Intel Deployments")
    if df_deployments.empty:
        st.info("No deployments registered in the sheet.")
    else:
        # Sort by latest date
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

# --- TAB 2: DETAILED SEARCH & EDIT LOGS ---
with tab2:
    st.header("Search & Manage Field History")
    if df_deployments.empty:
        st.info("No deployment history to manage.")
    else:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            sel_risk = st.selectbox("Filter by Incident Type", ["All"] + RISK_OPTIONS)
        with f_col2:
            sel_intel = st.selectbox("Filter by Intel Trigger", ["All"] + INTEL_OPTIONS)
        with f_col3:
            search_query = st.text_input("Search Location/Keyword").strip().lower()

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
            with st.expander(f"📍 {row['location']} ({row['risk_type']}) — {row['outreach_date'].strftime('%Y-%m-%d') if pd.notna(row['outreach_date']) else ''}"):
                if HAS_EDIT_ACCESS:
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

# --- TAB 3: ADMIN CREATION TAB ---
if IS_ADMIN and tab3 is not None:
    with tab3:
        st.header("➕ Record New Deployment Entry")
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
            n_concerns = st.text_area("Why was outreach conducted? (Share services, listen to safety issues, resident counts, historical homicide worries)")
            
            submit_new = st.form_submit_button("Submit Deployment to Tracker")
            
            if submit_new and n_loc:
                next_id = int(df_deployments['id'].max() + 1) if not df_deployments.empty and 'id' in df_deployments.columns else 1
                new_row = {
                    "id": next_id,
                    "location": n_loc,
                    "risk_type": n_risk,
                    "outreach_date": n_date.strftime('%Y-%m-%d'),
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
