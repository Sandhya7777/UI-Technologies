import pandas as pd
import streamlit as st
import snowflake.connector
import requests
import os
import logging
from joblib import Memory
from datetime import datetime, date
from snid4.db.connect import dbclosing

# Environment variables and logging setup
os.environ['CIZDEV_MAINT_SNWFLK_CLNT_ID'] = "2288f876-e77f-4fc0-9bcd-d28b5ad43a4c"
os.environ['CIZDEV_MAINT_SNWFLK_CLNT_SECRET'] = "p9h8Q~ceoi8eCWxADeSsOOjWVQk0GYOzaPGaia5t"
file_name = "C:\\Schnieder\\gitdemo3\\logs\\streamlit.log"
connection_file = "C:\\Schnieder\\gitdemo3\\connect.snow"
logging.basicConfig(
    filename=file_name,
    encoding="utf-8",
    filemode="a",
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
)
logging.warning("Save me!")

# Set the page layout to wide
st.set_page_config(layout="wide")

# Accessing and printing environment variables
environment_variables = os.environ
print("Printing environment variables")
for key, value in environment_variables.items():
    print(f"{key}: {value}")
    logging.warning(f"{key}: {value}")

# Cache setup
memory = Memory("./cache_dir", verbose=0)

# Fetch data from Snowflake
@memory.cache
def fetch_data_from_snowflake():
    sql_query = "SELECT * FROM WRNTY_CLM_HEADER LIMIT 100"
    try:
        with dbclosing(connection_file) as conn:
            df = pd.read_sql(sql_query, conn)
        return df.drop(columns=['UNIT_ID'], errors='ignore')  # Drop unnecessary columns
    except Exception as e:
        logging.error(f"Failed to fetch data from Snowflake: {e}")
        raise RuntimeError(f"Failed to fetch data: {e}")

# Convert value helper function
def convert_value(val):
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return val

# Save row to Snowflake
def save_row_to_snowflake(row_data, primary_key_column, table_name="WRNTY_CLM_INPUTS"):
    print("Row data passed to save_row_to_snowflake:", row_data)

    if isinstance(row_data, pd.Series):
        row_keys = row_data.index
    elif isinstance(row_data, dict):
        row_keys = row_data.keys()
    else:
        raise ValueError("row_data must be a Pandas Series or dictionary")

    columns_to_update = [col for col in row_keys if col not in (primary_key_column, "Select")]

    update_query = f"""
        UPDATE {table_name}
        SET {', '.join([f'"{col}" = %s' for col in columns_to_update])}
        WHERE "{primary_key_column}" = %s
    """
    values = [convert_value(row_data[col]) for col in columns_to_update]
    values.append(convert_value(row_data[primary_key_column]))

    check_query = f"SELECT COUNT(*) FROM {table_name} WHERE \"{primary_key_column}\" = %s"
    try:
        with dbclosing(connection_file) as conn:
            with conn.cursor() as cur:
                cur.execute(check_query, [convert_value(row_data[primary_key_column])])
                row_exists = cur.fetchone()[0] > 0

                if row_exists:
                    cur.execute(update_query, values)
                    conn.commit()
                    logging.info(f"Row updated successfully in {table_name}: {row_data}")
                    print(f"Row updated successfully in {table_name}: {row_data}")
                else:
                    insert_query = f"""
                        INSERT INTO {table_name} ({', '.join([f'"{col}"' for col in row_data.keys() if col != "Select"])})
                        VALUES ({', '.join(['%s' for col in row_data.keys() if col != "Select"])})
                    """
                    insert_values = [convert_value(row_data[col]) for col in row_data.keys() if col != "Select"]
                    cur.execute(insert_query, insert_values)
                    conn.commit()
                    logging.info(f"Row inserted successfully in {table_name}: {row_data}")
                    print(f"Row inserted successfully in {table_name}: {row_data}")
    except Exception as e:
        st.error(f"Failed to save row: {e}")
        logging.error(f"Save failed: {e}")
        print(f"Save failed: {e}")
        raise RuntimeError(f"Failed to save row: {e}")

# Load data from Snowflake
df = fetch_data_from_snowflake()

# Add a 'Select' column and move it to the start of the DataFrame
df.insert(0, 'Select', False)

# Initialize session state for search filters
if "filters" not in st.session_state:
    st.session_state.filters = {col: "" for col in df.columns}

# Initialize session state to manage the view
if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "selected_row_index" not in st.session_state:
    st.session_state.selected_row_index = None

# Define the column groups for each table
table_columns = {
    "Header": ["HEADER_NOTES", "STATUS", "ASSIGNMENT", "LOB", "CATEGORY_CLASS", "ESCALATED_TO", "RMD_FEEDBACK", "CANCEL_REASON", "COPY_CLAIM_1", "COPY_CLAIM_2", "LAST_UPDATED_DATE"],
    "After Market": ["WO_NO", "UNIT_NO", "SYSTEM", "JOB_ID", "JOB_STATUS", "JOB_REASON", "VIOLATION_FLOW", "JOB_DESCRIPTION", "UNIT", "VIN", "MAKE", "TECH_SPEC_DESC", "SERIAL_NO", "IN_SERV_DT", "MO_IN_SERV", "LABOR HRS", "LABOR", "PARTS", "COMM", "TRANSMISSION MODEL", "LTD", "METER", "OPEN_DT", "WO_CLOSE_DT", "COMPL_DT", "LOCATION", "BILLING_CODE"],
    "Vendor Details": ["VENDOR_NO", "NAME_SHORT", "CITY", "STATE", "PO_NO", "INV_NO"],
    "Notes": ["NOTE_TYPE", "SEQ", "NOTE"],
    "Parts Details": ["PART_NO", "DESCRIPTION", "QTY", "PART_COST", "PART_WARRENTY"]
}

# Define dropdown options for specific fields
dropdown_options = {
    "STATUS": ["No Status(Default)", "POLICY REVIEW", "CANCEL", "FOLLOW UP", "ESCALATED", "FILED", "QUEUE"],
    "ESCALATED_TO": ["No escalation(Default)", "Delco Remy Rep", "Truck Country", "Kenworth Rep", "Volvo Rep", "Brian Pasterski", "D'Anne Kozloski", "Wabco Rep Navistar Rep", "Chanelle", "Detroit Diesel Rep", "Navistar Rep", "Jason Gardner", "CUMMINS REP", "Conmet", "TMA", "Jeff Vanenkevort", "Blue Prism", "Steve Jarosinski", "Brian Lawniczak", "Jesse Goodreau", "Matt McCarty", "Collin Martin", "TA Rep", "Christine Vandenelzen", "Haldex Recall", "Lisa Fortun", "Bobbie Homburg", "Chris Elms", "Peterbilt Rep", "Freightliner Rep", "Jessica Payne"],
    "CANCEL_REASON": ["No Reason(Default)", "Out of Warranty by Mileage", "Driver Error", "Parts Not Available", "Parts Exchange Program", "Out of Warranty by Time", "Pre-Sublet Diagnostics", "Non-Authorized Repair Facility", "Excessive OTR Cost", "Accident/Non-Warranty Damage", "Insufficient Information", "No Problem Found/No repairs", "Towing Outside Of Coverage", "PDC Rebuilt Component", "Parts Not Retained", "Warranty Coverage Exclusion", "Modification/Cap Improvement", "Consumable Item", "Out Of Init Operating Period", "Excessive labor [20% over SRT]", "Previously Claimed", "Mechanic Error/Rework"],
    "RMD_FEEDBACK": ["No Feedback (Default)", "Multiple jobs with no reference in notes field", "No invoice Attached for Comm Charge", "labor above warranty SRT with justification", "labor above warranty SRT without justification", "Excessive Pre-Sublet Diagnostics", "Parts not charged out or charged out to wrong job", "Parts charged out but not justified in text", "Component Position/Wire", "Required serial", "Accident coded Gen Maint", "Gen Maint coded Accident", "Inprocessing coded Gen Maint", "Duplicate Service Bulletin/Campaign", "Insufficient Notes", "Improper Repair", "Job labor performed at or below standard SRT time", "Great notes in warranty note field with 3c’s", "Failed part not retained"],
    "CATEGORY_CLASS": ["DROPDOWN NAME", "BOX", "POWER", "SPRT PWR"]
}

# Add a single search input field
search_query = st.text_input("Search:", value="", help="Search across all columns")

# Apply the search filter to the DataFrame
filtered_df = df.copy()
if search_query:
    filtered_df = filtered_df[
        filtered_df.apply(lambda row: row.astype(str).str.contains(search_query, case=False, na=False).any(), axis=1)
    ]

# Limit rows displayed in the editor
max_rows = 50
filtered_df = df.head(max_rows)

if not st.session_state.show_form:
    # Display the data editor with only the 'Select' column editable
    disabled_columns = [col for col in filtered_df.columns if col != 'Select']
    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        disabled=disabled_columns,
        key="data_editor_main"
    )

    # Check if any row is selected
    selected_rows = edited_df[edited_df['Select'] == True]

    if not selected_rows.empty:
        # Get the index of the first selected row
        st.session_state.selected_row_index = selected_rows.index[0]
        st.session_state.show_form = True
        st.rerun()

else:
    selected_row = df.loc[st.session_state.selected_row_index]
    updated_row = selected_row.copy()
    with st.form("edit_form"):
        for table_name, columns in table_columns.items():
            st.subheader(table_name)
            for i, col_name in enumerate(columns):
                if i % 5 == 0:
                    table_cols = st.columns(5)
                if col_name == "LAST_UPDATED_DATE":
                    updated_row[col_name] = table_cols[i % 5].date_input(
                        f"{col_name}:", value=selected_row.get(col_name, datetime.now())
                    )
                elif col_name in dropdown_options:
                    current_value = selected_row.get(col_name, dropdown_options[col_name][0])
                    if current_value not in dropdown_options[col_name]:
                        current_value = dropdown_options[col_name][0]
                    updated_row[col_name] = table_cols[i % 5].selectbox(
                        f"{col_name}:",
                        dropdown_options[col_name],
                        index=dropdown_options[col_name].index(current_value),
                    )
                elif table_name == "Header":
                    if isinstance(selected_row, pd.Series):
                        updated_row[col_name] = table_cols[i % 5].text_input(f"{col_name}:", value=selected_row.get(col_name, ""))
                    elif isinstance(selected_row, dict):
                        updated_row[col_name] = table_cols[i % 5].text_input(f"{col_name}:", value=selected_row.get(col_name, ""))
                    else:
                        raise ValueError("selected_row must be a Pandas Series or dictionary")
                else:
                    table_cols[i % 5].text_input(
                        f"{col_name}:", value=selected_row.get(col_name, ""), disabled=True
                    )
        st.markdown(
            """
            <style>
            .button-container {
                display: flex;
                justify-content: space-between;
                margin-top: 20px;
            }
            .submit-button {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
            }
            .submit-button:hover {
                background-color: #218838;
            }
            .back-button {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
            }
            .back-button:hover {
                background-color: #c82333;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Submit", help="Submit your changes", type="primary")
        with col2:
            if st.form_submit_button("Back", help="Go back to the table view"):
                st.session_state.show_form = False
                st.session_state.selected_row_index = None
                st.rerun()

        if submitted:
            print("Submitting updated row...")
            print(f"Updated row data: {updated_row}")
            logging.info(f"Submitting updated row: {updated_row}")

            save_row_to_snowflake(updated_row, primary_key_column="WO_NO", table_name="WRNTY_CLM_INPUTS")
            st.success("Changes submitted and saved to Snowflake!")

            try:
                print("Fetching updated data from Snowflake...")
                df = fetch_data_from_snowflake()
                print("Updated data fetched successfully.")
                st.session_state.show_form = False
                st.session_state.selected_row_index = None
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Failed to reload data: {e}")
                logging.error(f"Data reload failed: {e}")
                print(f"Data reload failed: {e}")
