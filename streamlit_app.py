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


def save_dataframe_to_gsheet(df_to_save):
    """
    Handles appending brand new records to the Google Sheet (Tab 1).
    """
    if sheet_api_client is not None:
        try:
            # 1. Get all raw values from the first column (Id)
            raw_ids = sheet_api_client.col_values(1)
            
            # 2. Track the exact row index where the last numeric ID lives
            last_numeric_row = 1  # Defaults to row 1 (the header row)
            
            for idx, val in enumerate(raw_ids):
                cleaned = str(val).strip()
                if cleaned.isdigit():
                    last_numeric_row = idx + 1  # Sheets are 1-indexed

            # Target index is exactly 1 row after the last verified ID row
            insert_target_row = last_numeric_row + 1

            # 3. Grab the fresh data entry from memory
            fresh_entry = df_to_save.iloc[-1]
            
            # 4. Explicitly map fields to match exact headers order
            formatted_date = ""
            if 'Date' in fresh_entry and pd.notna(fresh_entry['Date']):
                formatted_date = f"'{pd.to_datetime(fresh_entry['Date']).strftime('%Y-%m-%d')}"

            # Build the clean payload row array explicitly
            new_row_payload = [
                int(fresh_entry.get('Id', 1)),
                str(fresh_entry.get('Location', '')),
                str(fresh_entry.get('Neighborhood', '')),
                formatted_date,  
                str(fresh_entry.get('Gang Affiliation', '')), 
                str(fresh_entry.get('Trigger Incident', '')),
                str(fresh_entry.get('Intel / Source', '')),
                int(fresh_entry.get('Community Member Engaged', 0)),
                int(fresh_entry.get('Staff Count Attended', 0)),
                float(fresh_entry.get('Total Hours Deployed', 0.0)),
                str(fresh_entry.get('Author', '')),
                str(fresh_entry.get('Community Concerns / Purpose', ''))
            ]
            
            # 5. Insert the new data row directly after the checked ID position
            sheet_api_client.insert_row(
                new_row_payload, 
                index=insert_target_row, 
                value_input_option="USER_ENTERED"
            )
            return True
            
        except Exception as e:
            st.error(f"Error updating deployment logs: {e}")
            return False
    return False


def update_gsheet_row(row_idx, updated_row_series):
    """
    Handles row-specific edits in place (Tab 3).
    Maps Pandas index to the corresponding Google Sheets row and updates it.
    """
    if sheet_api_client is not None:
        try:
            # Sheets are 1-indexed and have a header row. Pandas index 0 is Row 2 in Sheets.
            sheet_row_number = int(row_idx) + 2 
            
            formatted_date = ""
            if 'Date' in updated_row_series and pd.notna(updated_row_series['Date']):
                formatted_date = f"'{pd.to_datetime(updated_row_series['Date']).strftime('%Y-%m-%d')}"

            update_payload = [
                int(updated_row_series.get('Id', 1)),
                str(updated_row_series.get('Location', '')),
                str(updated_row_series.get('Neighborhood', '')),
                formatted_date,
                str(updated_row_series.get('Gang Affiliation', 'N/A')), 
                str(updated_row_series.get('Trigger Incident', '')),
                str(updated_row_series.get('Intel / Source', '')),
                int(updated_row_series.get('Community Member Engaged', 0)),
                int(updated_row_series.get('Staff Count Attended', 0)),
                float(updated_row_series.get('Total Hours Deployed', 0.0)),
                str(updated_row_series.get('Author', '')),
                str(updated_row_series.get('Community Concerns / Purpose', ''))
            ]
            
            # Select A through L range for this row
            range_to_update = f"A{sheet_row_number}:L{sheet_row_number}"
            sheet_api_client.update(range_to_update, [update_payload], value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            st.error(f"Error updating Google Sheet row {sheet_row_number}: {e}")
            return False
    return False


def safe_col(row, col, default=""):
    try:
        val = row.get(col, default)
    except Exception:
        val = default
    if pd.isna(val):
        return default
    return val


# --- FETCH DATA ---
df_deployments, sheet_api_client = load_data()

if not df_deployments.empty:
    # Clean up hidden spaces from headers
    df_deployments.columns = df_deployments.columns.str.strip()
    
    EXPECTED_COLUMNS = [
        "Id", "Location", "Neighborhood", "Date", "Gang Affiliation", "Trigger Incident",
        "Intel / Source", "Community Member Engaged", "Staff Count Attended",
        "Total Hours Deployed", "Author", "Community Concerns / Purpose"
    ]
    for col in EXPECTED_COLUMNS:
        if col not in df_deployments.columns:
            df_deployments[col] = pd.NA

    id_series = df_deployments['Id'].astype(str).str.strip().str.upper()
    
    if "END" in id_series.values:
        end_index = id_series[id_series == "END"].index[0]
        df_deployments = df_deployments.iloc[:end_index]
    
    df_deployments = df_deployments[
        (df_deployments['Location'].astype(str).str.strip() != "") & 
        (df_deployments['Location'].notna())
    ]
    
    if 'Date' in df_deployments.columns:
        df_deployments['Date'] = pd.to_datetime(df_deployments['Date'], errors='coerce')


# --- DROPDOWN OPTIONS ---
LOCATION_OPTIONS = ["East Bakersfield", "Southeast Bakersfield", "Central Bakersfield", "West Bakersfield", "Oildale", "Delano", "Wasco", "Arvin", "Lamont", "Other (Specify in Neighborhood)"]
TRIGGER_OPTIONS = ["Gun Shot Wound (GSW)", "Assault", "Stabbing", "Shooting", "Community Tension", "Retaliatory Conflict"]
GANG_OPTIONS = ["N/A", "Disputed Territory", "Colonia", "Eastside Bakers", "Loma Bakers", "Lomita Bakers", "Los Primos", "Okie Bakers", "Rexland Parque", "Southside Bakers", "Uptown Bakers", "Varrio Bakers", "Westside Bakers", "Westside Norte", "Country Boy Crip", "Eastside Crip", "Westside Crip", "Peckerwood"]
INTEL_OPTIONS = ["ShotSpotter", "BPD Intel", "HBVI Intel", "Community Intelligence", "Social Media"]


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

tab1, tab2, tab3 = st.tabs([
    "➕ Log New Deployment Zone", 
    "🎯 Recent Intel Deployments", 
    "🔍 Search & Manage Field History"
])

# --- TAB 1: NEW ENTRY FORM ---
with tab1:
    st.markdown("## 📝 Record a New Deployment Entry")
    st.markdown("---")
    
    # Large, friendly instructions at the top
    st.markdown(
        """
        ### Welcome! 
        Please fill out the fields below to log a new deployment. 
        When you are done, click the large green **'Save'** button at the bottom.
        """
    )
    
    with st.form("new_deployment_form", clear_on_submit=True):
        
        # --- SECTION 1: WHERE & WHEN ---
        st.markdown("### 📍 Step 1: Where and when did this happen?")
        col_where1, col_where2 = st.columns(2)
        
        with col_where1:
            n_loc = st.selectbox(
                "Select the General Location:", 
                LOCATION_OPTIONS,
                help="Click to open the list and select the city or region where the deployment occurred."
            )
            st.caption("ℹ️ *Choose the closest region from the dropdown menu above.*")
            
            n_neigh = st.text_input(
                "Type the Specific Neighborhood or Street:",
                placeholder="e.g., Cottonwood Road, MLK Blvd, etc.",
                help="Type the exact street name, block number, or neighborhood name here."
            )
            st.caption("ℹ️ *This helps us pin down the exact location.*")
            
        with col_where2:
            n_date = st.date_input(
                "Select the Date of the Incident:", 
                datetime.date.today(),
                help="Click the calendar to choose the date this took place. It defaults to today."
            )
            st.caption("ℹ️ *If this happened on a previous day, click above to change it.*")

        st.markdown("---")

        # --- SECTION 2: INTEL & BACKGROUND ---
        st.markdown("### 🔍 Step 2: What triggered the deployment?")
        col_intel1, col_intel2 = st.columns(2)
        
        with col_intel1:
            n_trigger = st.selectbox(
                "Select the Trigger Incident:", 
                TRIGGER_OPTIONS,
                help="What specific event or incident caused us to deploy to this area?"
            )
            st.caption("ℹ️ *Choose the primary reason for this deployment.*")
            
            n_intel = st.selectbox(
                "Select the Information Source:", 
                INTEL_OPTIONS,
                help="Where did we get the information about this incident?"
            )
            st.caption("ℹ️ *Identify how our team was alerted.*")
            
        with col_intel2:
            n_gang = st.selectbox(
                "Is there a Gang Affiliation involved?", 
                GANG_OPTIONS,
                help="If this incident is tied to a specific gang territory or group, select it here. If not, choose N/A."
            )
            st.caption("ℹ️ *Select 'N/A' if gang affiliation is unknown or not applicable.*")

        st.markdown("---")

        # --- SECTION 3: NUMBERS & STAFFING ---
        st.markdown("### 👥 **Step 3**: Who was involved?")
        col_num1, col_num2, col_num3 = st.columns(3)
        
        with col_num1:
            n_engaged = st.number_input(
                "Number of Community Members Engaged:", 
                min_value=0, 
                value=0, 
                step=1,
                help="How many local residents or neighbors did our staff talk to or connect with during this shift?"
            )
            st.caption("ℹ️ *Type in a number or use the + and - buttons.*")
            
        with col_num2:
            n_staff = st.number_input(
                "Number of Staff Members Present:", 
                min_value=1, 
                value=1, 
                step=1,
                help="How many of our team members deployed to this location?"
            )
            st.caption("ℹ️ *At least 1 staff member must be logged.*")
            
        with col_num3:
            n_hours = st.number_input(
                "Total Hours Spent on the Block:", 
                min_value=0.0, 
                step=0.5, 
                value=1.0,
                help="How long was our team deployed in this specific zone? (You can use decimals, e.g., 1.5 for an hour and a half)"
            )
            st.caption("ℹ️ *Use 0.5 for half an hour increments.*")

        st.markdown("---")

        # --- SECTION 4: NOTES ---
        st.markdown("### 📝 Step 4: Summary & Community Concerns")
        n_concerns = st.text_area(
            "Write a brief summary of community concerns or the purpose of deployment:",
            placeholder="Type your field notes here. Explain what the neighbors are saying, what tensions exist, and what our team did on the ground.",
            help="Provide a clear, detailed summary of your shift here so other team members can easily understand what happened."
        )
        st.caption("ℹ️ *Take your time writing this out. Be as detailed as needed.*")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- SUBMIT BUTTON ---
        # Styled to be big, bold, green, and highly visible
        submit_new = st.form_submit_button(
            "💾 Click Here to Save This Deployment to the Tracker", 
            use_container_width=True
        )

        if submit_new:
            # Calculate next numeric ID based on active deployments
            next_id = int(df_deployments['Id'].max() + 1) if not df_deployments.empty and 'Id' in df_deployments.columns else 1
            
            new_row = {
                "Id": next_id,
                "Location": n_loc,
                "Neighborhood": n_neigh,
                "Date": pd.to_datetime(n_date), 
                "Gang Affiliation": n_gang, 
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
            
            # Save and refresh
            with st.spinner("Saving your data securely... please wait a moment."):
                if save_dataframe_to_gsheet(updated_df):
                    st.cache_data.clear()
                    st.balloons()  # Fun, visual celebration to let them know it worked!
                    st.success("✅ Success! Your new deployment entry has been safely saved to the system.")
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
                    
                    # 🎯 FIXED: Direct extraction of gang affiliation with proper visual formatting
                    gang_val = str(row.get('Gang Affiliation', 'N/A')).strip()
                    if gang_val == "" or pd.isna(row.get('Gang Affiliation')):
                        gang_val = "N/A"
                    
                    st.markdown(f"**Trigger:** {row['Trigger Incident']} | **Source:** {row['Intel / Source']} | **Gang:** `{gang_val}`")
                    st.markdown(f"**Summary:**")
                    st.write(row['Community Concerns / Purpose'])
                with c2:
                    st.markdown("⚡ **Operational Specs**")
                    st.markdown(f"👥 **Engaged:** {row['Community Member Engaged']} neighbors")
                    st.markdown(f"👷‍♂️ **Staff:** {row['Staff Count Attended']} members")
                    st.markdown(f"⏳ **Duration:** {row['Total Hours Deployed']} hrs")


# --- TAB 3: SEARCH & MANAGE HISTORY (REVAMPED & CONDENSED) ---
with tab3:
    st.header("Search & Manage Field History")
    if df_deployments.empty:
        st.info("No deployment history to manage.")
    else:
        # Filter Strip
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            sel_trigger = st.selectbox("Filter by Trigger", ["All"] + TRIGGER_OPTIONS)
        with f_col2:
            sel_intel = st.selectbox("Filter by Intel Source", ["All"] + INTEL_OPTIONS)
        with f_col3:
            sel_gang = st.selectbox("Filter by Gang Affiliation", ["All"] + GANG_OPTIONS) 
        with f_col4:
            search_query = st.text_input("Search Neighborhood/Keyword").strip().lower()

        filtered_df = df_deployments.copy()
        
        if sel_trigger != "All":
            filtered_df = filtered_df[filtered_df["Trigger Incident"] == sel_trigger]
        if sel_intel != "All":
            filtered_df = filtered_df[filtered_df["Intel / Source"] == sel_intel]
        if sel_gang != "All":
            filtered_df = filtered_df[filtered_df["Gang Affiliation"].astype(str).str.strip() == sel_gang] 
        if search_query:
            filtered_df = filtered_df[
                filtered_df["Neighborhood"].astype(str).str.lower().str.contains(search_query) |
                filtered_df["Community Concerns / Purpose"].astype(str).str.lower().str.contains(search_query)
            ]

        st.markdown(f"**Showing {len(filtered_df)} matches**")
        st.markdown("---")

        for idx, row in filtered_df.iterrows():
            formatted_date = row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'No Date'
            gang_tag = str(row.get('Gang Affiliation', 'N/A')).strip()
            if gang_tag == "" or pd.isna(row.get('Gang Affiliation')):
                gang_tag = "N/A"
            
            # Condensed visual accordion header with immediate status tags
            header_label = f"📍 {row['Location']} ({row['Neighborhood']}) | Date: {formatted_date} | Gang: {gang_tag}"
            
            with st.expander(header_label):
                with st.form(key=f"edit_form_{idx}"):
                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        e_loc = st.selectbox("Location", LOCATION_OPTIONS, index=LOCATION_OPTIONS.index(row['Location']) if row['Location'] in LOCATION_OPTIONS else 0, key=f"loc_edit_{idx}")
                        e_neigh = st.text_input("Neighborhood", value=row['Neighborhood'], key=f"neigh_edit_{idx}")
                        current_date_val = row['Date'].date() if pd.notna(row['Date']) else datetime.date.today()
                        e_date = st.date_input("Date of Incident", value=current_date_val, key=f"date_edit_{idx}")
                    with ec2:
                        e_trigger = st.selectbox("Trigger Incident", TRIGGER_OPTIONS, index=TRIGGER_OPTIONS.index(row['Trigger Incident']) if row['Trigger Incident'] in TRIGGER_OPTIONS else 0, key=f"trig_edit_{idx}")
                        e_intel = st.selectbox("Intel / Source", INTEL_OPTIONS, index=INTEL_OPTIONS.index(row['Intel / Source']) if row['Intel / Source'] in INTEL_OPTIONS else 0, key=f"intel_edit_{idx}")
                        
                        curr_gang = str(row.get('Gang Affiliation', 'N/A')).strip()
                        if pd.isna(row.get('Gang Affiliation')) or curr_gang == "":
                            curr_gang = "N/A"
                        gang_idx = GANG_OPTIONS.index(curr_gang) if curr_gang in GANG_OPTIONS else 0
                        e_gang = st.selectbox("Gang Affiliation", GANG_OPTIONS, index=gang_idx, key=f"gang_edit_{idx}")
                    with ec3:
                        e_engaged = st.number_input("Community Engaged", min_value=0, value=safe_int(row.get('Community Member Engaged', 0)), key=f"engaged_edit_{idx}")
                        e_staff = st.number_input("Staff Attended", min_value=0, value=safe_int(row.get('Staff Count Attended', 0)), key=f"staff_edit_{idx}")
                        e_hours = st.number_input("Hours Deployed", min_value=0.0, step=0.5, value=safe_float(row.get('Total Hours Deployed', 0.0)), key=f"hours_edit_{idx}")
                    
                    e_concerns = st.text_area("Community Concerns / Purpose", value=row.get('Community Concerns / Purpose', ''), key=f"concerns_edit_{idx}")
                    
                    save_btn = st.form_submit_button("💾 Save Updates to Row")
                    
                    if save_btn:
                        df_deployments.at[idx, 'Location'] = e_loc
                        df_deployments.at[idx, 'Neighborhood'] = e_neigh
                        df_deployments.at[idx, 'Date'] = pd.to_datetime(e_date)
                        df_deployments.at[idx, 'Gang Affiliation'] = e_gang 
                        df_deployments.at[idx, 'Trigger Incident'] = e_trigger
                        df_deployments.at[idx, 'Intel / Source'] = e_intel
                        df_deployments.at[idx, 'Community Member Engaged'] = e_engaged
                        df_deployments.at[idx, 'Staff Count Attended'] = e_staff
                        df_deployments.at[idx, 'Total Hours Deployed'] = e_hours
                        df_deployments.at[idx, 'Community Concerns / Purpose'] = e_concerns
                        
                        # 🎯 FIXED: Call targeted, index-specific row updater
                        if update_gsheet_row(idx, df_deployments.loc[idx]):
                            st.cache_data.clear()
                            st.success("Google Sheets row synchronized successfully!")
                            st.rerun()
