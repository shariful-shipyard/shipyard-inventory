import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# Streamlit Page Setup
st.set_page_config(
    page_title="Shipbuilding Store & Project Management",
    page_icon="🚢",
    layout="wide",
)


# --- DATABASE SETUP ---
def get_connection():
  conn = sqlite3.connect("shipbuilding_store.db", check_same_thread=False)
  return conn


def init_db():
  conn = get_connection()
  cursor = conn.cursor()

  # Master Inventory Table
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS store_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT UNIQUE,
        item_name TEXT,
        category TEXT,
        unit TEXT,
        stock REAL DEFAULT 0
    )
    """)

  # Project Ledger Table
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS project_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT,
        item_code TEXT,
        txn_type TEXT,
        qty REAL,
        person_or_ref TEXT,
        txn_date TEXT
    )
    """)

  # App Settings Table
  cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
  conn.commit()


init_db()


# --- HELPER FUNCTIONS ---
def get_yard_name():
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("SELECT value FROM app_settings WHERE key = 'yard_name'")
  row = cursor.fetchone()
  return row[0] if row and row[0] else "SHIPYARD STORE CONTROL"


def set_yard_name(name):
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute(
      """INSERT INTO app_settings (key, value) VALUES ('yard_name', ?)
                     ON CONFLICT(key) DO UPDATE SET value = ?""",
      (name, name),
  )
  conn.commit()


# Initialize Cart in Session State
if "cart" not in st.session_state:
  st.session_state.cart = []

# --- TOP HEADER PANEL ---
col_yard, col_title = st.columns([1, 2])

with col_yard:
  current_yard = get_yard_name()
  new_yard_name = st.text_input(
      "Shipyard Name", value=current_yard, key="yard_input"
  )
  if st.button("💾 Save Yard Name"):
    set_yard_name(new_yard_name)
    st.success("Shipyard Name updated successfully!")
    st.rerun()

with col_title:
  st.markdown(
      f"<h2 style='text-align: right; color: #f39c12;'>PROJECT-WISE INVENTORY"
      f" MANAGEMENT</h2><p style='text-align: right; font-weight:"
      f" bold;'>{get_yard_name()}</p>",
      unsafe_allow_html=True,
  )

st.markdown("---")

# Navigation Tabs
tab_ops, tab_reps = st.tabs(
    ["📦 Operations (In / Out)", "📊 Project & Yard Reports"]
)

# ==========================================
# TAB 1: OPERATIONS (IN / OUT)
# ==========================================
with tab_ops:
  st.subheader("📥 Add / Receive Material to Project / Store")

  with st.form("receive_form", clear_on_submit=True):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
      rec_date = st.date_input("Date", value=datetime.now())
      rec_project = st.text_input("Project / Hull", value="Hull-101")

    with col2:
      rec_code = st.text_input("Item Code")
      rec_name = st.text_input("Material Spec / Name")

    with col3:
      rec_cat = st.selectbox(
          "Category",
          [
              "Steel Plate",
              "Profile/Angle/Bulb",
              "Welding & Gas",
              "Pipe & Fitting",
              "Paint & Coating",
              "Hardware",
              "Electrical",
          ],
      )
      rec_unit = st.selectbox(
          "Unit",
          [
              "Pcs",
              "Kg",
              "Ton",
              "Meter",
              "Ltr",
              "Set",
              "Pkt",
              "Bottle",
              "Feet",
              "Pot",
              "Drum",
          ],
      )

    with col4:
      rec_qty = st.number_input("Qty", min_value=0.0, step=1.0)
      st.markdown("<br>", unsafe_allow_html=True)
      submit_rec = st.form_submit_button("Receive Material 🟢")

    if submit_rec:
      if not rec_code or not rec_name or rec_qty <= 0:
        st.error(
            "Please fill in Item Code, Material Name, and a valid Qty!"
        )
      else:
        conn = get_connection()
        cursor = conn.cursor()
        date_str = rec_date.strftime("%Y-%m-%d")

        cursor.execute(
            """INSERT INTO store_inventory (item_code, item_name, category, unit, stock) 
                           VALUES (?, ?, ?, ?, ?) 
                           ON CONFLICT(item_code) DO UPDATE SET stock = stock + ?""",
            (rec_code, rec_name, rec_cat, rec_unit, rec_qty, rec_qty),
        )

        cursor.execute(
            """INSERT INTO project_ledger (project_name, item_code, txn_type, qty, person_or_ref, txn_date)
                           VALUES (?, ?, 'IN', ?, 'Supplier/Store Receive', ?)""",
            (rec_project, rec_code, rec_qty, date_str),
        )
        conn.commit()
        st.success(
            f"Material Received on {date_str} for Project '{rec_project}'!"
        )
        st.rerun()

  st.markdown("---")

  # Middle Section: Inventory Table & Cart
  col_inv, col_cart = st.columns([3, 2])

  with col_inv:
    st.subheader("🏢 Yard Overall Stock Level")
    search_q = st.text_input("🔍 Search Material (Code / Name / Category)")

    conn = get_connection()
    if search_q:
      df_inv = pd.read_sql_query(
          "SELECT id, item_code as Code, item_name as Name, category as"
          " Category, unit as Unit, stock as Stock FROM store_inventory WHERE"
          " item_code LIKE ? OR item_name LIKE ? OR category LIKE ?",
          conn,
          params=(f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"),
      )
    else:
      df_inv = pd.read_sql_query(
          "SELECT id, item_code as Code, item_name as Name, category as"
          " Category, unit as Unit, stock as Stock FROM store_inventory",
          conn,
      )

    st.dataframe(df_inv, use_container_width=True, hide_index=True)

    # Delete Selected Item Option
    if not df_inv.empty:
      del_id = st.selectbox(
          "Select Item ID to Delete",
          options=df_inv["id"].tolist(),
          key="del_select",
      )
      if st.button("🗑️ Delete Selected Item", type="secondary"):
        cursor = conn.cursor()
        item_code_res = cursor.execute(
            "SELECT item_code FROM store_inventory WHERE id = ?", (del_id,)
        ).fetchone()
        if item_code_res:
          code_to_del = item_code_res[0]
          cursor.execute(
              "DELETE FROM store_inventory WHERE id = ?", (del_id,)
          )
          cursor.execute(
              "DELETE FROM project_ledger WHERE item_code = ?", (code_to_del,)
          )
          conn.commit()
          st.success("Item and its history deleted successfully!")
          st.rerun()

  with col_cart:
    st.subheader("🛒 Material Issue Cart")
    if st.session_state.cart:
      df_cart = pd.DataFrame(st.session_state.cart)
      st.dataframe(
          df_cart[["code", "name", "qty", "unit"]],
          use_container_width=True,
          hide_index=True,
      )

      if st.button("Clear Cart ❌"):
        st.session_state.cart = []
        st.rerun()
    else:
      st.info("Cart is currently empty. Add materials below.")

  # Bottom Section: Issue Material Control Panel
  st.markdown("---")
  st.subheader("📤 Issue Material to Specific Project / Hull")

  col_iss1, col_iss2, col_iss3 = st.columns(3)

  with col_iss1:
    iss_date = st.date_input("Issue Date", value=datetime.now(), key="iss_date")
    iss_project = st.text_input(
        "Project / Hull", value="Hull-101", key="iss_proj"
    )

  with col_iss2:
    iss_to = st.text_input("Issued To / Contractor", key="iss_to")

    # Item Picker from Stock
    conn = get_connection()
    stock_items = pd.read_sql_query(
        "SELECT id, item_code, item_name, unit, stock FROM store_inventory"
        " WHERE stock > 0",
        conn,
    )

    if not stock_items.empty:
      item_options = stock_items.apply(
          lambda row: (
              f"{row['item_code']} - {row['item_name']} (Stock:"
              f" {row['stock']} {row['unit']})"
          ),
          axis=1,
      ).tolist()
      selected_item_str = st.selectbox("Select Material", options=item_options)
      selected_index = item_options.index(selected_item_str)
      selected_row = stock_items.iloc[selected_index]
    else:
      st.warning("No materials available in stock!")
      selected_row = None

  with col_iss3:
    iss_qty = st.number_input(
        "Issue Qty", min_value=0.0, step=1.0, key="iss_qty"
    )

    if st.button("Add to Cart ➕"):
      if selected_row is not None and iss_qty > 0:
        if iss_qty > selected_row["stock"]:
          st.error(f"Insufficient stock! Available: {selected_row['stock']}")
        else:
          st.session_state.cart.append({
              "id": selected_row["id"],
              "code": selected_row["item_code"],
              "name": selected_row["item_name"],
              "qty": iss_qty,
              "unit": selected_row["unit"],
          })
          st.success(f"Added {selected_row['item_name']} to cart!")
          st.rerun()
      else:
        st.warning("Enter a valid quantity!")

  st.markdown("<br>", unsafe_allow_html=True)
  if st.button("🔵 Confirm Issue & Generate Slip", type="primary"):
    if not st.session_state.cart:
      st.warning("Issue list is empty!")
    elif not iss_to or not iss_project:
      st.warning("Please specify Project/Hull Name and Contractor Name!")
    else:
      conn = get_connection()
      cursor = conn.cursor()
      date_str = iss_date.strftime("%Y-%m-%d")

      for item in st.session_state.cart:
        cursor.execute(
            "UPDATE store_inventory SET stock = stock - ? WHERE id = ?",
            (item["qty"], item["id"]),
        )
        cursor.execute(
            """INSERT INTO project_ledger (project_name, item_code, txn_type, qty, person_or_ref, txn_date)
                           VALUES (?, ?, 'OUT', ?, ?, ?)""",
            (iss_project, item["code"], item["qty"], iss_to, date_str),
        )

      conn.commit()

      # Generate Issue Slip Text Preview
      slip_text = f"""
================================================
          {get_yard_name().center(32)}
             MATERIAL ISSUE SLIP
================================================
Issue Date  : {date_str}
Project/Hull: {iss_project}
Issued To   : {iss_to}
------------------------------------------------
Code     Description        Qty    Unit
------------------------------------------------\n"""
      for item in st.session_state.cart:
        slip_text += f"{item['code']:<8} {item['name'][:18]:<18} {item['qty']:<6} {item['unit']:<6}\n"

      slip_text += """------------------------------------------------
Approved By: _______________   Received By: _______________
================================================
Software created by MD SHARIFUL ISLAM
"""
      st.session_state.cart = []
      st.success("Material issued successfully!")
      st.code(slip_text, language="text")

# ==========================================
# TAB 2: PROJECT & YARD REPORTS
# ==========================================
with tab_reps:
  st.subheader(
      "📄 Filter Report Options (By Date Range or Full Project Ledger)"
  )

  col_r1, col_r2, col_r3 = st.columns(3)
  with col_r1:
    rep_project = st.text_input("Project / Hull Name", value="Hull-101")
  with col_r2:
    start_date = st.date_input(
        "From Date", value=datetime.now().replace(day=1)
    )
  with col_r3:
    end_date = st.date_input("To Date", value=datetime.now())

  col_b1, col_b2, col_b3 = st.columns(3)
  with col_b1:
    btn_proj_rep = st.button("Show Project Ledger 📊")
  with col_b2:
    btn_yard_rep = st.button("Show Total Yard Summary 🏬")
  with col_b3:
    btn_full_rep = st.button("Show Full Report (All Time) 📜")

  conn = get_connection()
  query = ""
  params = ()
  report_title = "REPORT SUMMARY"

  s_str = start_date.strftime("%Y-%m-%d")
  e_str = end_date.strftime("%Y-%m-%d")

  if btn_proj_rep:
    report_title = (
        f"PROJECT LEDGER ({rep_project.upper()}) [{s_str} TO {e_str}]"
    )
    query = """
        SELECT 
            DATE(p.txn_date) as Date,
            p.project_name as Project,
            p.item_code as Code,
            i.item_name as Description,
            SUM(CASE WHEN p.txn_type = 'IN' THEN p.qty ELSE 0 END) as Total_IN,
            SUM(CASE WHEN p.txn_type = 'OUT' THEN p.qty ELSE 0 END) as Total_OUT,
            (SUM(CASE WHEN p.txn_type = 'IN' THEN p.qty ELSE 0 END) - SUM(CASE WHEN p.txn_type = 'OUT' THEN p.qty ELSE 0 END)) as Net_Balance,
            i.unit as Unit
        FROM project_ledger p
        LEFT JOIN store_inventory i ON p.item_code = i.item_code
        WHERE p.project_name LIKE ? AND DATE(p.txn_date) BETWEEN DATE(?) AND DATE(?)
        GROUP BY DATE(p.txn_date), p.project_name, p.item_code
        ORDER BY DATE(p.txn_date) DESC
        """
    params = (f"%{rep_project}%", s_str, e_str)

  elif btn_yard_rep:
    report_title = f"TOTAL YARD STOCK SUMMARY [{s_str} TO {e_str}]"
    query = """
        SELECT 
            COALESCE(DATE(p.txn_date), 'All Time') as Date,
            'ALL YARD' as Project,
            i.item_code as Code,
            i.item_name as Description,
            COALESCE(SUM(CASE WHEN p.txn_type = 'IN' THEN p.qty ELSE 0 END), 0) as Total_IN,
            COALESCE(SUM(CASE WHEN p.txn_type = 'OUT' THEN p.qty ELSE 0 END), 0) as Total_OUT,
            i.stock as Net_Balance,
            i.unit as Unit
        FROM store_inventory i
        LEFT JOIN project_ledger p ON i.item_code = p.item_code AND DATE(p.txn_date) BETWEEN DATE(?) AND DATE(?)
        GROUP BY DATE(p.txn_date), i.item_code
        ORDER BY DATE(p.txn_date) DESC
        """
    params = (s_str, e_str)

  elif btn_full_rep:
    report_title = f"FULL ALL-TIME REPORT ({rep_project.upper()})"
    query = """
        SELECT 
            DATE(p.txn_date) as Date,
            p.project_name as Project,
            p.item_code as Code,
            i.item_name as Description,
            SUM(CASE WHEN p.txn_type = 'IN' THEN p.qty ELSE 0 END) as Total_IN,
            SUM(CASE WHEN p.txn_type = 'OUT' THEN p.qty ELSE 0 END) as Total_OUT,
            (SUM(CASE WHEN p.txn_type = 'IN' THEN p.qty ELSE 0 END) - SUM(CASE WHEN p.txn_type = 'OUT' THEN p.qty ELSE 0 END)) as Net_Balance,
            i.unit as Unit
        FROM project_ledger p
        LEFT JOIN store_inventory i ON p.item_code = i.item_code
        WHERE p.project_name LIKE ?
        GROUP BY DATE(p.txn_date), p.project_name, p.item_code
        ORDER BY DATE(p.txn_date) DESC
        """
    params = (f"%{rep_project}%",)

  if query:
    df_rep = pd.read_sql_query(query, conn, params=params)
    st.markdown(f"### {report_title}")
    st.dataframe(df_rep, use_container_width=True, hide_index=True)

    # Printable A4 Text Format Preview
    st.markdown("---")
    st.subheader("🖨️ Printable A4 Format Text")

    current_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    yard_name_str = get_yard_name().upper()

    report_lines = f"{'Date':<11} {'Project/Hull':<12} {'Code':<8} {'Material Spec':<18} {'Total IN':<9} {'Total OUT':<9} {'Balance':<9} {'Unit':<5}\n"
    report_lines += "-" * 88 + "\n"

    for _, row in df_rep.iterrows():
      p_date = str(row["Date"])[:10]
      p_name = str(row["Project"])[:11]
      p_code = str(row["Code"])[:7]
      p_desc = str(row["Description"])[:17]
      p_in = str(row["Total_IN"])
      p_out = str(row["Total_OUT"])
      p_bal = str(row["Net_Balance"])
      p_unit = str(row["Unit"])
      report_lines += f"{p_date:<11} {p_name:<12} {p_code:<8} {p_desc:<18} {p_in:<9} {p_out:<9} {p_bal:<9} {p_unit:<5}\n"

    a4_memo = f"""
==========================================================================================
                               {yard_name_str.center(45)}
                         {report_title.center(45)}
==========================================================================================
Date/Time Generated: {current_time}                                    Page Layout: A4
------------------------------------------------------------------------------------------
{report_lines}------------------------------------------------------------------------------------------
Printed By: Store Department                                          Approved By: 
==========================================================================================
Software created by MD SHARIFUL ISLAM
"""
    st.code(a4_memo, language="text")