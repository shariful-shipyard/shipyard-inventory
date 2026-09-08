from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- STREAMLIT PAGE SETUP ---
st.set_page_config(
    page_title="Shipbuilding Store & Project Management",
    page_icon="🚢",
    layout="wide",
)


# --- DATABASE SETUP (SQLITE) ---
def get_connection():
    conn = sqlite3.connect("shipbuilding_store.db", check_same_thread=False)
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        project_hull TEXT,
        item_code TEXT,
        category TEXT,
        material_spec TEXT,
        qty REAL,
        unit TEXT,
        transaction_type TEXT,
        remarks TEXT
    )
    """)
    conn.commit()
    conn.close()


init_db()

# --- MAIN APP UI ---
st.title("🚢 PROJECT-WISE INVENTORY MANAGEMENT")

# Navigation Tabs
tab1, tab2 = st.tabs(
    ["📥 Operations (In / Out)", "📊 Project & Yard Reports"]
)

# --- TAB 1: OPERATIONS ---
with tab1:
    st.header("Add / Receive Material to Project / Store")
    with st.form("entry_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            date_val = st.date_input("Date", datetime.today())
            project_hull = st.text_input(
                "Project / Hull (e.g., Hull-101, ALL YARD)"
            )
            item_code = st.text_input("Item Code")

        with col2:
            category = st.selectbox(
                "Category",
                ["Steel Plate", "Profile / Angle", "Pipe", "Electrode", "Other"],
            )
            material_spec = st.text_input("Material Spec / Name")
            qty = st.number_input("Qty", min_value=0.0, step=1.0)

        with col3:
            unit = st.selectbox("Unit", ["Pcs", "Kg", "Meter", "Pkt", "Ltr"])
            remarks = st.text_area("Remarks")

        btn_in = st.form_submit_button("Receive Material (IN)")
        btn_out = st.form_submit_button("Issue Material (OUT)")

        if btn_in or btn_out:
            trans_type = "IN" if btn_in else "OUT"
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
            INSERT INTO inventory (date, project_hull, item_code, category, material_spec, qty, unit, transaction_type, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(date_val),
                    project_hull,
                    item_code,
                    category,
                    material_spec,
                    qty,
                    unit,
                    trans_type,
                    remarks,
                ),
            )
            conn.commit()
            conn.close()
            st.success(f"Successfully recorded {trans_type} transaction!")

# --- TAB 2: REPORTS & BALANCE ---
with tab2:
    st.header("Report Options")
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()

    if not df.empty:
        # Separate IN and OUT transactions for Net Balance calculation
        in_df = (
            df[df["transaction_type"] == "IN"]
            .groupby(["project_hull", "item_code", "material_spec", "unit"])[
                "qty"
            ]
            .sum()
            .reset_index()
            .rename(columns={"qty": "Total_IN"})
        )

        out_df = (
            df[df["transaction_type"] == "OUT"]
            .groupby(["project_hull", "item_code", "material_spec", "unit"])[
                "qty"
            ]
            .sum()
            .reset_index()
            .rename(columns={"qty": "Total_OUT"})
        )

        # Merge IN and OUT data
        summary = pd.merge(
            in_df,
            out_df,
            on=["project_hull", "item_code", "material_spec", "unit"],
            how="outer",
        ).fillna(0)

        # Calculate Net Balance (Total IN - Total OUT)
        summary["Net_Balance"] = summary["Total_IN"] - summary["Total_OUT"]

        st.subheader("YARD STOCK SUMMARY")
        st.dataframe(summary, use_container_width=True)

        # PRINT / DOWNLOAD REPORT OPTION
        st.write("---")
        st.subheader("🖨️ Print Slip / Download Options")

        csv_data = summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📄 Download Report / Print Slip (CSV)",
            data=csv_data,
            file_name=f"Stock_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No transaction data available yet.")
