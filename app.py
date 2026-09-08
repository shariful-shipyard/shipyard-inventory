from datetime import datetime
import sqlite3
import pandas as pd
import streamlit as st

# --- PAGE SETUP ---
st.set_page_config(
    page_title="Shipbuilding Project & Store Management System",
    page_icon="🚢",
    layout="wide",
)

# Custom CSS
st.markdown(
    """
    <style>
    .stApp { background-color: #f4f6f9; }
    div[data-testid="stHorizontalBlock"] { align-items: flex-end; }
    .stButton>button { width: 100%; border-radius: 4px; font-weight: bold; }
    </style>
""",
    unsafe_allow_html=True,
)


# --- DATABASE CONNECTION (SQLITE) ---
def get_connection():
    return sqlite3.connect("shipbuilding_store.db", check_same_thread=False)


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
        issued_to TEXT,
        remarks TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    conn.commit()
    conn.close()


init_db()


# --- HELPER FUNCTIONS ---
def get_yard_name():
    conn = get_connection()
    df = pd.read_sql(
        "SELECT value FROM settings WHERE key='yard_name'", conn
    )
    conn.close()
    return df.iloc[0]["value"] if not df.empty else "STORE CONTROL"


def save_yard_name(name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('yard_name', ?)",
        (name,),
    )
    conn.commit()
    conn.close()


# Session state for Issue Cart
if "cart" not in st.session_state:
    st.session_state.cart = []

# --- LIST DEFINITIONS ---
CATEGORY_LIST = [
    "Steel Plate",
    "Profile/Angle/ bulb plate",
    "Pipe & pipe fitting",
    "Gas & oxygen",
    "Paint & coating",
    "Hardware",
    "Electrical",
    "Others",
]

UNIT_LIST = [
    "Pcs",
    "Kg",
    "Ton",
    "Set",
    "Bottle",
    "Feet",
    "Meter",
    "Pkt",
    "Pot",
    "Ltr",
    "Drum",
]

# --- HEADER SECTION ---
st.title("Shipbuilding Project & Store Management System")

col_yard1, col_yard2, _ = st.columns([2, 1, 3])
with col_yard1:
    current_yard = get_yard_name()
    yard_name_input = st.text_input(
        "Shipyard Name:", value=current_yard, key="yard_input"
    )
with col_yard2:
    if st.button("💾 Save Yard Name"):
        save_yard_name(yard_name_input)
        st.success("Yard Name Saved!")

# NAVIGATION TABS
tab1, tab2 = st.tabs(
    ["📥 Operations (In / Out)", "📊 Project & Yard Reports"]
)

# ==========================================
# TAB 1: OPERATIONS (IN / OUT)
# ==========================================
with tab1:
    st.markdown("### Add / Receive Material to Project / Store")
    with st.form("receive_form", clear_on_submit=True):
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(
            [1.2, 1.2, 1, 1.5, 1.3, 0.9, 0.8, 1]
        )
        with c1:
            rec_date = st.date_input("Date", datetime.today(), key="rec_date")
        with c2:
            rec_hull = st.text_input(
                "Project/Hull", value="Hull-101", key="rec_hull"
            )
        with c3:
            rec_code = st.text_input("Code", key="rec_code")
        with c4:
            rec_spec = st.text_input("Material Spec", key="rec_spec")
        with c5:
            rec_cat = st.selectbox("Category", CATEGORY_LIST, key="rec_cat")
        with c6:
            rec_unit = st.selectbox("Unit", UNIT_LIST, key="rec_unit")
        with c7:
            rec_qty = st.number_input(
                "Qty", min_value=0.0, step=1.0, key="rec_qty"
            )
        with c8:
            rec_btn = st.form_submit_button("Receive")

        if rec_btn:
            if rec_code and rec_qty > 0:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO inventory (date, project_hull, item_code, category, material_spec, qty, unit, transaction_type, issued_to, remarks)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'IN', '', '')
                """,
                    (
                        str(rec_date),
                        rec_hull,
                        rec_code,
                        rec_cat,
                        rec_spec,
                        rec_qty,
                        rec_unit,
                    ),
                )
                conn.commit()
                conn.close()
                st.success("Material Received Successfully!")
            else:
                st.error("Please provide Item Code and Qty.")

    st.divider()

    # FETCH CURRENT STOCK FOR DISPLAY & SELECTION
    conn = get_connection()
    df_all = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()

    stock_df = pd.DataFrame()
    item_options = []

    if not df_all.empty:
        in_df = (
            df_all[df_all["transaction_type"] == "IN"]
            .groupby(["item_code", "material_spec", "category", "unit"])[
                "qty"
            ]
            .sum()
            .reset_index()
            .rename(columns={"qty": "IN"})
        )
        out_df = (
            df_all[df_all["transaction_type"] == "OUT"]
            .groupby(["item_code", "material_spec", "category", "unit"])[
                "qty"
            ]
            .sum()
            .reset_index()
            .rename(columns={"qty": "OUT"})
        )

        stock_df = pd.merge(
            in_df,
            out_df,
            on=["item_code", "material_spec", "category", "unit"],
            how="outer",
        ).fillna(0)
        stock_df["Total Stock"] = stock_df["IN"] - stock_df["OUT"]
        stock_df["ID"] = stock_df.index + 1

        for idx, row in stock_df.iterrows():
            item_options.append(
                f"{row['item_code']} - {row['material_spec']} (Stock: {row['Total Stock']} {row['unit']})"
            )

    # MIDDLE SECTION: STOCK LEVEL & ISSUE CART
    left_col, right_col = st.columns([1.2, 1])

    # --- LEFT SIDE: OVERALL STOCK LEVEL ---
    with left_col:
        st.subheader("Overall Stock Level")
        search_query = st.text_input("Search Material:", "")

        if not stock_df.empty:
            display_df = stock_df[
                [
                    "ID",
                    "item_code",
                    "material_spec",
                    "category",
                    "unit",
                    "Total Stock",
                ]
            ].rename(
                columns={
                    "item_code": "Code",
                    "material_spec": "Material Description",
                    "category": "Category",
                    "unit": "Unit",
                }
            )

            if search_query:
                display_df = display_df[
                    display_df["Material Description"]
                    .str.contains(search_query, case=False, na=False)
                    | display_df["Code"].str.contains(
                        search_query, case=False, na=False
                    )
                ]

            st.dataframe(display_df, use_container_width=True, height=250)
        else:
            st.info("No stock available in store.")

    # --- RIGHT SIDE: MATERIAL ISSUE CART ---
    with right_col:
        col_cart_title, col_cart_del = st.columns([2, 1])
        with col_cart_title:
            st.subheader("Material Issue Cart")
        with col_cart_del:
            if st.button("🗑️ Delete Selected Item"):
                if st.session_state.cart:
                    st.session_state.cart.pop()
                    st.rerun()

        cart_df = pd.DataFrame(
            st.session_state.cart,
            columns=["Code", "Material Description", "Qty", "Unit"],
        )
        st.dataframe(cart_df, use_container_width=True, height=200)

    # --- BOTTOM SECTION: ISSUE MATERIAL TO SPECIFIC PROJECT ---
    st.markdown("### Material to Specific Project / Hull")

    c_iss_select, c_iss_qty = st.columns([3, 1])
    with c_iss_select:
        selected_item_str = st.selectbox(
            "Select Material from Stock to Issue:",
            options=item_options if item_options else ["No Material Available"],
            key="selected_item_str",
        )
    with c_iss_qty:
        iss_qty = st.number_input(
            "Issue Qty", min_value=0.0, step=1.0, key="iss_qty"
        )

    c_iss1, c_iss2, c_iss3, c_iss5, c_iss6, c_iss7 = st.columns(
        [1.2, 1.2, 1.5, 1, 1.3, 1]
    )

    with c_iss1:
        iss_date = st.date_input("Date", datetime.today(), key="iss_date")
    with c_iss2:
        iss_hull = st.text_input(
            "Project / Hull", value="Hull-101", key="iss_hull"
        )
    with c_iss3:
        iss_to = st.text_input("Issued To / Contractor", key="iss_to")

    with c_iss5:
        if st.button("🛒 Add to Cart"):
            if item_options and iss_qty > 0:
                selected_idx = item_options.index(selected_item_str)
                selected_row = stock_df.iloc[selected_idx]

                st.session_state.cart.append(
                    {
                        "Code": selected_row["item_code"],
                        "Material Description": selected_row["material_spec"],
                        "Qty": iss_qty,
                        "Unit": selected_row["unit"],
                        "Category": selected_row["category"],
                    }
                )
                st.rerun()
            else:
                st.warning("Select valid material and enter Qty > 0.")

    with c_iss6:
        if st.button("✅ Confirm Issue & Print"):
            if st.session_state.cart:
                conn = get_connection()
                cursor = conn.cursor()
                for item in st.session_state.cart:
                    cursor.execute(
                        """
                        INSERT INTO inventory (date, project_hull, item_code, category, material_spec, qty, unit, transaction_type, issued_to, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'OUT', ?, '')
                    """,
                        (
                            str(iss_date),
                            iss_hull,
                            item["Code"],
                            item["Category"],
                            item["Material Description"],
                            item["Qty"],
                            item["Unit"],
                            iss_to,
                        ),
                    )
                conn.commit()
                conn.close()
                st.session_state.cart = []
                st.success("Materials Issued Successfully!")
                st.rerun()
            else:
                st.warning("Cart is empty!")

    with c_iss7:
        if st.button("🧹 Clear Cart"):
            st.session_state.cart = []
            st.rerun()


# ==========================================
# TAB 2: PROJECT & YARD REPORTS
# ==========================================
with tab2:
    st.markdown("### Filter Report Options (By Date Range or Full Report)")

    f_col1, f_col2, f_col3 = st.columns([1.5, 1.2, 1.2])

    with f_col1:
        rep_hull = st.text_input(
            "Project/Hull Name:", value="", key="rep_hull"
        )
    with f_col2:
        from_date = st.date_input("From Date (YYYY-MM-DD)", datetime.today())
    with f_col3:
        to_date = st.date_input("To Date (YYYY-MM-DD)", datetime.today())

    st.write("")
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([1.5, 1.8, 1.5, 1.8])

    conn = get_connection()
    rep_df = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()

    if not rep_df.empty:
        rep_df["date_dt"] = pd.to_datetime(rep_df["date"])
        mask = (rep_df["date_dt"] >= pd.to_datetime(from_date)) & (
            rep_df["date_dt"] <= pd.to_datetime(to_date)
        )
        filtered_df = rep_df.loc[mask]

        if rep_hull:
            filtered_df = filtered_df[
                filtered_df["project_hull"]
                .str.contains(rep_hull, case=False, na=False)
            ]

        in_rep = (
            filtered_df[filtered_df["transaction_type"] == "IN"]
            .groupby(["date", "project_hull", "item_code", "material_spec"])[
                "qty"
            ]
            .sum()
            .reset_index()
            .rename(columns={"qty": "Total IN (Received)"})
        )
        out_rep = (
            filtered_df[filtered_df["transaction_type"] == "OUT"]
            .groupby(["date", "project_hull", "item_code", "material_spec"])[
                "qty"
            ]
            .sum()
            .reset_index()
            .rename(columns={"qty": "Total OUT (Issued)"})
        )

        summary_rep = pd.merge(
            in_rep,
            out_rep,
            on=["date", "project_hull", "item_code", "material_spec"],
            how="outer",
        ).fillna(0)
        summary_rep["Net Balance"] = (
            summary_rep["Total IN (Received)"]
            - summary_rep["Total OUT (Issued)"]
        )

        summary_rep = summary_rep.rename(
            columns={
                "date": "Date",
                "project_hull": "Project/Hull Name",
                "item_code": "Item Code",
                "material_spec": "Material Description",
            }
        )

        st.subheader("Report Table")
        st.dataframe(summary_rep, use_container_width=True)

        with btn_col4:
            csv_report = summary_rep.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="🖨️ Print / Export A4 Report",
                data=csv_report,
                file_name=f"Yard_Report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
    else:
        st.info("No records available to display.")
