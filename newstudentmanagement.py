import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# ============================
# PAGE CONFIGURATION
# ============================
st.set_page_config(
    page_title="Student Management System",
    page_icon="🎓",
    layout="wide"
)

# ============================
# CONSTANTS
# ============================
# TODO: Replace these with your actual Google Sheet links
IELTS_SHEET_LINK = "YOUR_IELTS_SHEET_LINK_HERE"
APTIS_SHEET_LINK = "YOUR_APTIS_SHEET_LINK_HERE"

# ============================
# SESSION STATE INITIALIZATION
# ============================
if 'page' not in st.session_state:
    st.session_state.page = 'Home'
if 'selected_student' not in st.session_state:
    st.session_state.selected_student = None
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False

# ============================
# AUTHENTICATION
# ============================
@st.cache_resource
def get_gspread_client():
    """Initialize Google Sheets client"""
    try:
        # Check for credentials
        if 'gcp_service_account' not in st.secrets:
            st.error("❌ Missing Google Service Account credentials in secrets.toml")
            return None
        
        # Define scopes
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Get credentials
        creds_info = dict(st.secrets['gcp_service_account'])
        
        # Fix private key formatting
        if 'private_key' in creds_info:
            private_key = creds_info['private_key']
            if '\\n' in private_key:
                private_key = private_key.replace('\\n', '\n')
            creds_info['private_key'] = private_key
        
        # Create credentials
        credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        
        # Authorize client
        client = gspread.authorize(credentials)
        return client
        
    except Exception as e:
        st.error(f"❌ Authentication failed: {str(e)}")
        return None

# Initialize client
gc = get_gspread_client()

# ============================
# GOOGLE SHEETS FUNCTIONS
# ============================
def get_spreadsheet(batch_type):
    """Get spreadsheet by type"""
    if not gc:
        return None
    
    try:
        if batch_type == "IELTS":
            # TODO: Replace with your actual IELTS sheet link
            spreadsheet = gc.open_by_url(IELTS_SHEET_LINK)
        else:  # Aptis
            # TODO: Replace with your actual Aptis sheet link
            spreadsheet = gc.open_by_url(APTIS_SHEET_LINK)
        return spreadsheet
    except Exception as e:
        st.error(f"❌ Error accessing {batch_type} sheet: {str(e)}")
        return None

def get_all_batches():
    """Get all batches from both sheets"""
    all_batches = []
    
    if not gc:
        return all_batches
    
    for batch_type in ["IELTS", "Aptis"]:
        spreadsheet = get_spreadsheet(batch_type)
        if spreadsheet:
            try:
                worksheets = spreadsheet.worksheets()
                for ws in worksheets:
                    all_batches.append({
                        "name": ws.title,
                        "type": batch_type,
                        "worksheet": ws
                    })
            except:
                continue
    
    return all_batches

def get_batch_names():
    """Get just batch names for dropdowns"""
    batches = get_all_batches()
    return [batch["name"] for batch in batches]

def create_batch_worksheet(batch_name, batch_type, year, time_slot):
    """Create a new batch worksheet"""
    spreadsheet = get_spreadsheet(batch_type)
    if not spreadsheet:
        return False
    
    try:
        # Create new worksheet
        worksheet = spreadsheet.add_worksheet(title=batch_name, rows="1000", cols="10")
        
        # Add headers
        headers = [
            "Student Name", 
            "Student ID", 
            "Contact", 
            "Email", 
            "Batch", 
            "Type", 
            "Time",
            "Year",
            "Created Date",
            "Last Updated"
        ]
        worksheet.append_row(headers)
        
        # Format header
        worksheet.format('A1:J1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.8, 'alpha': 0.3}
        })
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error creating batch: {str(e)}")
        return False

def add_student_to_batch(student_data, batch_name):
    """Add student to a specific batch"""
    batches = get_all_batches()
    target_batch = None
    
    # Find the batch
    for batch in batches:
        if batch["name"] == batch_name:
            target_batch = batch
            break
    
    if not target_batch:
        st.error(f"❌ Batch '{batch_name}' not found")
        return False
    
    try:
        worksheet = target_batch["worksheet"]
        
        # Prepare student record
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = [
            student_data["name"],
            student_data["student_id"],
            student_data["contact"],
            student_data["email"],
            batch_name,
            target_batch["type"],
            student_data["time"],
            student_data.get("year", datetime.now().year),
            timestamp,  # Created Date
            timestamp   # Last Updated (same as created for new)
        ]
        
        # Add to worksheet
        worksheet.append_row(record)
        return True
        
    except Exception as e:
        st.error(f"❌ Error adding student: {str(e)}")
        return False

def get_all_students(batch_filter=None):
    """Get all students from all batches, optionally filtered by batch"""
    all_students = []
    batches = get_all_batches()
    
    for batch in batches:
        if batch_filter and batch["name"] != batch_filter:
            continue
            
        try:
            worksheet = batch["worksheet"]
            records = worksheet.get_all_records()
            
            for i, record in enumerate(records, start=2):  # start=2 because row 1 is header
                if record.get("Student Name"):  # Skip empty rows
                    record["_row"] = i  # Store row number for editing
                    record["_batch_name"] = batch["name"]
                    record["_batch_type"] = batch["type"]
                    record["_worksheet"] = worksheet
                    all_students.append(record)
                    
        except Exception as e:
            continue
    
    return all_students

def update_student(row_index, worksheet, updated_data):
    """Update student information"""
    try:
        # Get current row
        row = worksheet.row_values(row_index)
        
        # Update fields
        updated_row = [
            updated_data.get("Student Name", row[0]),
            updated_data.get("Student ID", row[1]),
            updated_data.get("Contact", row[2]),
            updated_data.get("Email", row[3]),
            row[4],  # Batch name (don't change)
            row[5],  # Batch type (don't change)
            updated_data.get("Time", row[6]),
            updated_data.get("Year", row[7]),
            row[8],  # Created Date (don't change)
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Update timestamp
        ]
        
        # Update the row
        worksheet.update(f"A{row_index}:J{row_index}", [updated_row])
        return True
        
    except Exception as e:
        st.error(f"❌ Error updating student: {str(e)}")
        return False

def delete_student(row_index, worksheet):
    """Delete a student record"""
    try:
        # Clear the row (preserves formatting)
        worksheet.delete_rows(row_index)
        return True
    except Exception as e:
        st.error(f"❌ Error deleting student: {str(e)}")
        return False

# ============================
# UI COMPONENTS
# ============================
def show_navigation():
    """Show Home and Back buttons"""
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🏠 Home", key=f"home_{st.session_state.page}"):
            st.session_state.page = 'Home'
            st.session_state.edit_mode = False
            st.session_state.selected_student = None
            st.rerun()
    with col2:
        if st.button("⬅️ Back", key=f"back_{st.session_state.page}"):
            st.session_state.page = 'Home'
            st.session_state.edit_mode = False
            st.session_state.selected_student = None
            st.rerun()
    st.markdown("---")

# ============================
# PAGE: HOME
# ============================
def show_home_page():
    """Display home page"""
    st.title("🎓 Student Management System")
    st.markdown("### Welcome to the Student Management Portal")
    
    # Check connection
    if not gc:
        st.error("⚠️ Not connected to Google Sheets. Please check your configuration.")
        st.info("Make sure to:")
        st.info("1. Add your Google Service Account credentials to Streamlit secrets")
        st.info("2. Replace the sheet links in the code with your actual Google Sheet links")
        st.info("3. Share your Google Sheets with the service account email")
    
    # Quick stats
    if gc:
        try:
            batches = get_all_batches()
            students = get_all_students()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Batches", len(batches))
            with col2:
                st.metric("Total Students", len(students))
            with col3:
                ielts_count = len([b for b in batches if b["type"] == "IELTS"])
                st.metric("IELTS Batches", ielts_count)
        except:
            pass
    
    st.markdown("---")
    
    # Main options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📁 Create Batch", use_container_width=True):
            st.session_state.page = 'Create Batch'
            st.rerun()
    
    with col2:
        if st.button("➕ Add Student Information", use_container_width=True):
            st.session_state.page = 'Add Student'
            st.rerun()
    
    with col3:
        if st.button("🔍 Find Student", use_container_width=True):
            st.session_state.page = 'Find Student'
            st.rerun()
    
    # Recent activity
    if gc:
        st.markdown("---")
        st.subheader("📋 Recent Batches")
        batches = get_all_batches()
        if batches:
            recent_batches = batches[-5:]  # Show last 5 batches
            for batch in recent_batches:
                try:
                    student_count = len(get_all_students(batch["name"]))
                    st.text(f"• {batch['name']} ({batch['type']}) - {student_count} students")
                except:
                    st.text(f"• {batch['name']} ({batch['type']})")

# ============================
# PAGE: CREATE BATCH
# ============================
def show_create_batch_page():
    """Display create batch page"""
    st.title("📁 Create New Batch")
    show_navigation()
    
    if not gc:
        st.error("⚠️ Not connected to Google Sheets")
        return
    
    with st.form("create_batch_form"):
        st.subheader("Batch Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            batch_name = st.text_input("Batch Name*", 
                                      placeholder="e.g., IELTS_Batch_1_2024",
                                      help="Unique name for this batch")
            
            batch_type = st.selectbox("Type*", ["IELTS", "Aptis"],
                                     help="IELTS batches go to IELTS sheet, Aptis to Aptis sheet")
        
        with col2:
            year = st.selectbox("Year*", 
                               range(2023, 2031),
                               index=2)  # Default to 2025
            
            time_slot = st.selectbox("Time*", ["4pm", "6pm"])
        
        st.markdown("**Note:** Each batch will be created as a separate worksheet in the respective Google Sheet.")
        st.markdown("**Required fields***")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col2:
            submit_button = st.form_submit_button("🚀 Create Now", type="primary", use_container_width=True)
        with col3:
            reset_button = st.form_submit_button("🔄 Reset", use_container_width=True)
        
        if submit_button:
            # Validation
            if not batch_name:
                st.error("Please enter a batch name")
                return
            
            # Check if batch already exists
            existing_batches = get_batch_names()
            if batch_name in existing_batches:
                st.error(f"Batch '{batch_name}' already exists. Please choose a different name.")
                return
            
            # Create batch
            with st.spinner(f"Creating batch '{batch_name}'..."):
                success = create_batch_worksheet(batch_name, batch_type, year, time_slot)
                
                if success:
                    st.success(f"✅ Batch '{batch_name}' created successfully!")
                    st.balloons()
                    
                    # Show next steps
                    with st.expander("🎯 Next Steps", expanded=True):
                        st.markdown(f"""
                        1. **Add Students**: Go to 'Add Student Information' page
                        2. **Batch Type**: {batch_type}
                        3. **Year**: {year}
                        4. **Time**: {time_slot}
                        
                        The batch has been created as a worksheet named **{batch_name}** in the {batch_type} Google Sheet.
                        """)
                    
                    # Auto-refresh after 3 seconds
                    time.sleep(3)
                    st.session_state.page = 'Home'
                    st.rerun()
        
        if reset_button:
            st.rerun()

# ============================
# PAGE: ADD STUDENT
# ============================
def show_add_student_page():
    """Display add student page"""
    st.title("➕ Add Student Information")
    show_navigation()
    
    if not gc:
        st.error("⚠️ Not connected to Google Sheets")
        return
    
    # Get available batches
    batch_names = get_batch_names()
    
    if not batch_names:
        st.warning("No batches found. Please create a batch first.")
        if st.button("📁 Create New Batch"):
            st.session_state.page = 'Create Batch'
            st.rerun()
        return
    
    with st.form("add_student_form"):
        st.subheader("Student Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            student_name = st.text_input("Name of Student*", 
                                        placeholder="John Smith")
            student_id = st.text_input("Student ID*", 
                                      placeholder="STU001")
        
        with col2:
            contact = st.text_input("Contact*", 
                                   placeholder="+1234567890")
            email = st.text_input("Email*", 
                                 placeholder="john@example.com")
        
        # Batch selection
        selected_batch = st.selectbox("Batch*", 
                                     batch_names,
                                     help="Select an existing batch")
        
        time_slot = st.selectbox("Time*", ["4pm", "6pm"])
        
        st.markdown("**Required fields***")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col2:
            submit_button = st.form_submit_button("💾 Submit Information", type="primary", use_container_width=True)
        with col3:
            reset_button = st.form_submit_button("🔄 Reset", use_container_width=True)
        
        if submit_button:
            # Validation
            if not all([student_name, student_id, contact, email]):
                st.error("Please fill all required fields")
                return
            
            # Email validation
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                st.error("Please enter a valid email address")
                return
            
            # Prepare student data
            student_data = {
                "name": student_name,
                "student_id": student_id,
                "contact": contact,
                "email": email,
                "time": time_slot,
                "year": datetime.now().year
            }
            
            # Add student to batch
            with st.spinner(f"Adding {student_name} to {selected_batch}..."):
                success = add_student_to_batch(student_data, selected_batch)
                
                if success:
                    st.success(f"✅ Student '{student_name}' added to '{selected_batch}' successfully!")
                    st.balloons()
                    
                    # Option to add another
                    if st.button("➕ Add Another Student"):
                        st.rerun()
                    
                    # Option to go home
                    if st.button("🏠 Go Home"):
                        st.session_state.page = 'Home'
                        st.rerun()
        
        if reset_button:
            st.rerun()

# ============================
# PAGE: FIND STUDENT
# ============================
def show_find_student_page():
    """Display find student page with edit/delete functionality"""
    st.title("🔍 Find Student")
    show_navigation()
    
    if not gc:
        st.error("⚠️ Not connected to Google Sheets")
        return
    
    # Search and filter section
    st.subheader("Search & Filter")
    
    col1, col2 = st.columns(2)
    
    with col1:
        search_query = st.text_input("Search by Name or Student ID", 
                                    placeholder="Enter name or ID...",
                                    key="search_input")
    
    with col2:
        batch_filter = st.selectbox("Filter by Batch", 
                                   ["All Batches"] + get_batch_names(),
                                   key="batch_filter")
    
    # Get all students
    students = get_all_students()
    
    if not students:
        st.info("No students found in the system.")
        return
    
    # Convert to DataFrame for display
    df = pd.DataFrame(students)
    
    # Apply filters
    if search_query:
        mask = (df['Student Name'].str.contains(search_query, case=False, na=False) | 
                df['Student ID'].str.contains(search_query, case=False, na=False))
        df = df[mask]
    
    if batch_filter != "All Batches":
        df = df[df['_batch_name'] == batch_filter]
    
    # Display results
    if len(df) > 0:
        st.success(f"Found {len(df)} student(s)")
        
        # Display table (without internal columns)
        display_cols = ['Student Name', 'Student ID', 'Contact', 'Email', 
                       'Batch', 'Type', 'Time', 'Year', 'Last Updated']
        
        # Filter to available columns
        available_cols = [col for col in display_cols if col in df.columns]
        display_df = df[available_cols]
        
        # Create selection
        if 'selected_index' not in st.session_state:
            st.session_state.selected_index = 0
        
        # Display with selection
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )
        
        # Student selection for editing
        st.subheader("📝 Student Actions")
        
        if len(df) > 0:
            student_options = [f"{row['Student Name']} ({row['Student ID']}) - {row['Batch']}" 
                              for _, row in df.iterrows()]
            
            selected_student = st.selectbox(
                "Select a student to edit/delete:",
                student_options,
                key="student_selector"
            )
            
            # Get selected student data
            if selected_student:
                selected_idx = student_options.index(selected_student)
                selected_row = df.iloc[selected_idx]
                
                # Action buttons
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button("➕ Add New Student", use_container_width=True):
                        st.session_state.page = 'Add Student'
                        st.rerun()
                
                with col2:
                    if st.button("✏️ Edit Selected", type="secondary", use_container_width=True):
                        st.session_state.selected_student = selected_row.to_dict()
                        st.session_state.edit_mode = True
                        st.session_state.page = 'Edit Student'
                        st.rerun()
                
                with col3:
                    if st.button("🗑️ Delete Selected", type="secondary", use_container_width=True):
                        # Confirm deletion
                        st.warning(f"Are you sure you want to delete {selected_row['Student Name']}?")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Yes, Delete", type="primary"):
                                success = delete_student(
                                    selected_row['_row'],
                                    selected_row['_worksheet']
                                )
                                if success:
                                    st.success(f"✅ Student '{selected_row['Student Name']}' deleted successfully!")
                                    time.sleep(2)
                                    st.rerun()
                        with col2:
                            if st.button("❌ Cancel"):
                                st.rerun()
                
                with col4:
                    if st.button("📥 Export Data", use_container_width=True):
                        csv = display_df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"students_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="export_csv"
                        )
        else:
            st.info("No students match your search criteria.")
            if st.button("➕ Add New Student"):
                st.session_state.page = 'Add Student'
                st.rerun()
    
    else:
        st.info("No students found matching your criteria.")
        if st.button("➕ Add New Student"):
            st.session_state.page = 'Add Student'
            st.rerun()

# ============================
# PAGE: EDIT STUDENT
# ============================
def show_edit_student_page():
    """Display edit student page"""
    st.title("✏️ Edit Student Information")
    show_navigation()
    
    if not st.session_state.selected_student:
        st.error("No student selected for editing")
        st.button("🔙 Back to Find Student", on_click=lambda: setattr(st.session_state, 'page', 'Find Student'))
        return
    
    student = st.session_state.selected_student
    
    with st.form("edit_student_form"):
        st.subheader(f"Editing: {student.get('Student Name', 'Unknown')}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            student_name = st.text_input("Name of Student*", 
                                        value=student.get('Student Name', ''))
            student_id = st.text_input("Student ID*", 
                                      value=student.get('Student ID', ''))
        
        with col2:
            contact = st.text_input("Contact*", 
                                   value=student.get('Contact', ''))
            email = st.text_input("Email*", 
                                 value=student.get('Email', ''))
        
        # Display batch info (read-only)
        st.text_input("Batch", 
                     value=student.get('Batch', ''),
                     disabled=True)
        
        time_slot = st.selectbox("Time*", 
                                ["4pm", "6pm"],
                                index=0 if student.get('Time') == '4pm' else 1)
        
        st.markdown("**Required fields***")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            submit_button = st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True)
        with col2:
            cancel_button = st.form_submit_button("❌ Cancel", use_container_width=True)
        with col3:
            delete_button = st.form_submit_button("🗑️ Delete Student", use_container_width=True)
        
        if submit_button:
            # Validation
            if not all([student_name, student_id, contact, email]):
                st.error("Please fill all required fields")
                return
            
            # Email validation
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                st.error("Please enter a valid email address")
                return
            
            # Prepare updated data
            updated_data = {
                "Student Name": student_name,
                "Student ID": student_id,
                "Contact": contact,
                "Email": email,
                "Time": time_slot
            }
            
            # Update student
            with st.spinner("Saving changes..."):
                success = update_student(
                    student['_row'],
                    student['_worksheet'],
                    updated_data
                )
                
                if success:
                    st.success("✅ Student information updated successfully!")
                    time.sleep(2)
                    st.session_state.page = 'Find Student'
                    st.session_state.selected_student = None
                    st.session_state.edit_mode = False
                    st.rerun()
        
        if cancel_button:
            st.session_state.page = 'Find Student'
            st.session_state.selected_student = None
            st.session_state.edit_mode = False
            st.rerun()
        
        if delete_button:
            # Confirm deletion
            st.warning(f"Are you sure you want to delete {student.get('Student Name', 'this student')}?")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, Delete", type="primary"):
                    success = delete_student(
                        student['_row'],
                        student['_worksheet']
                    )
                    if success:
                        st.success(f"✅ Student deleted successfully!")
                        time.sleep(2)
                        st.session_state.page = 'Find Student'
                        st.session_state.selected_student = None
                        st.session_state.edit_mode = False
                        st.rerun()
            with col2:
                if st.button("❌ Cancel"):
                    st.rerun()

# ============================
# MAIN APP ROUTER
# ============================
def main():
    """Main application router"""
    
    # Route to correct page
    if st.session_state.page == 'Home':
        show_home_page()
    elif st.session_state.page == 'Create Batch':
        show_create_batch_page()
    elif st.session_state.page == 'Add Student':
        show_add_student_page()
    elif st.session_state.page == 'Find Student':
        show_find_student_page()
    elif st.session_state.page == 'Edit Student':
        show_edit_student_page()
    else:
        show_home_page()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>🎓 Student Management System • v1.0</div>",
        unsafe_allow_html=True
    )

# ============================
# RUN THE APPLICATION
# ============================
if __name__ == "__main__":
    main()
