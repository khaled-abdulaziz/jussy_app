import streamlit as st
import mysql.connector
import bcrypt
import pandas as pd
import plotly.express as px
from PIL import Image
import io

# ----------- Page config -----------
st.set_page_config(page_title="Jussy Dashboard", layout="wide")

# ----------- MySQL connection -----------
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["mysql"]["host"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
        database=st.secrets["mysql"]["database"]
    )


# ----------- Verify login credentials -----------
def check_login(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user and bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
            return True
        return False
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return False

# ----------- Logout -----------
def logout():
    st.session_state.logged_in = False
    st.session_state.username = ''
    st.rerun()

# ----------- Login page -----------
def login_page():
    st.title("Login to Jussy Dashboard")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username.strip() == "" or password.strip() == "":
            st.error("Please enter both username and password.")
        else:
            if check_login(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password")

# ----------- Dashboard page -----------
def dashboard():
    # Header with logout button
    col1, col2 = st.columns([9, 1])
    with col1:
        st.markdown(f"<h1 style='color:#2E86C1'>Welcome, {st.session_state.username}</h1>", unsafe_allow_html=True)
    with col2:
        if st.button("Logout"):
            logout()

    # Header logo + title
    col_logo, col_title, col_empty = st.columns([1, 6, 1])
    with col_logo:
        logo_path = "logo.png"
        try:
            logo = Image.open(logo_path)
            st.image(logo, width=80)
        except Exception:
            pass
    with col_title:
        st.markdown(
            "<h1 style='text-align: center; color: #2E86C1; margin: 0;'>Jussy Dashboard</h1>",
            unsafe_allow_html=True
        )

    # Custom file uploader styling
    st.markdown(
        """
        <style>
        div[data-testid="stFileUploader"] label {display:none;}
        div[data-testid="stFileUploader"] div[role="button"] {
            background-color: #2E86C1;
            color: white;
            padding: 8px 14px;
            border-radius: 8px;
            font-weight: 600;
        }
        div[data-testid="stFileUploader"] div[role="button"]:hover {opacity:0.9;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("", type=["xlsx", "xls", "csv"], label_visibility="collapsed")

    if uploaded_file:
        file_name = uploaded_file.name.lower()

        # --- Step 1: Handle CSV from SQL (split & take Table_6) ---
        if file_name.endswith(".csv"):
            tables = []
            current_csv = []
            content = uploaded_file.read().decode("utf-8").splitlines()

            for line in content:
                if line.startswith('"id"') and current_csv:
                    df = pd.read_csv(io.StringIO('\n'.join(current_csv)))
                    tables.append(df)
                    current_csv = [line]
                else:
                    current_csv.append(line)

            if current_csv:
                df = pd.read_csv(io.StringIO('\n'.join(current_csv)))
                tables.append(df)

            if len(tables) >= 6:
                df_original = tables[5].copy()

                # --- Step 2: Pre-clean Table_6 ---
                df_original.drop(columns=['user_id', 'id'], inplace=True, errors='ignore')
                df_original.reset_index(drop=True, inplace=True)
                df_original.index += 1
                df_original.index.name = "No"
                df_original.dropna(inplace=True)

                df_original.rename(columns={
                    'order_date': 'date',
                    'fruit_name': 'type'
                }, inplace=True)

                df_original['status'] = 'online'
                df_original['Location'] = 'Tuban'

                desired_order = ['date', 'type', 'quantity', 'total price', 'status', 'Location']
                df_original = df_original[desired_order]
                df_original.reset_index(inplace=True)

            else:
                st.error("Table_6 not found in uploaded CSV.")
                return

        # --- Step 3: Handle already-clean Excel/XLS ---
        elif file_name.endswith((".xlsx", ".xls")):
            df_original = pd.read_excel(uploaded_file)
            df_original.columns = df_original.columns.str.strip()

        else:
            st.error("Unsupported file format.")
            return

        # Show preview after initial cleaning
        st.subheader("📄 Data After Initial Cleaning (preview)")
        st.dataframe(df_original.head(10), use_container_width=True)
        with st.expander("Show full data after initial cleaning"):
            st.dataframe(df_original, use_container_width=True)

        # --- Continue with your existing cleaning logic ---
        df = df_original.copy()

        required_cols = {'date', 'type', 'quantity', 'total_price', 'status', 'Location'}
        missing = required_cols - set(df.columns)
        if missing:
            st.error(f"Missing required columns in the file: {', '.join(missing)}")
            return
        else:
            st.subheader("🧼 Cleaned Data (preview)")

            df['total_price'] = df['total_price'].astype(str).str.replace(r'[^\d]', '', regex=True)
            df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce').fillna(0).astype(int)

            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)

            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])

            df['day'] = df['date'].dt.day_name()
            df['month'] = df['date'].dt.to_period('M').astype(str)

            st.dataframe(df.head(10), use_container_width=True)
            with st.expander("Show full cleaned data"):
                st.dataframe(df, use_container_width=True)

            # Filters
            st.subheader("🔍 Filter Data")

            months = sorted(df['month'].unique().tolist())
            days = sorted(df['day'].unique().tolist())
            types = sorted(df['type'].unique().tolist())
            locations = sorted(df['Location'].unique().tolist())
            statuses = sorted(df['status'].unique().tolist())

            fcol1, fcol2 = st.columns(2)

            with fcol1:
                show_all_months = st.checkbox("Show All Months", value=True)
                if show_all_months:
                    selected_months = months
                else:
                    selected_month = st.selectbox("Select a Month", options=months)
                    selected_months = [selected_month]

                show_all_days = st.checkbox("Show All Days", value=True)
                if show_all_days:
                    selected_days = days
                else:
                    selected_day = st.selectbox("Select a Day", options=days)
                    selected_days = [selected_day]

                show_all_types = st.checkbox("Show All Drink Types", value=True)
                if show_all_types:
                    selected_types = types
                else:
                    selected_types = st.multiselect("Select Drink Type(s)", options=types, default=types)

            with fcol2:
                show_all_locations = st.checkbox("Show All Locations", value=True)
                if show_all_locations:
                    selected_locations = locations
                else:
                    selected_locations = st.multiselect("Select Location(s)", options=locations, default=locations)

                show_all_statuses = st.checkbox("Show All Statuses", value=True)
                if show_all_statuses:
                    selected_statuses = statuses
                else:
                    selected_statuses = st.multiselect("Select Status(es)", options=statuses, default=statuses)

            filtered_df = df[
                (df['month'].isin(selected_months)) &
                (df['day'].isin(selected_days)) &
                (df['type'].isin(selected_types)) &
                (df['Location'].isin(selected_locations)) &
                (df['status'].isin(selected_statuses))
            ]

            st.subheader("📊 Filtered Data (preview)")
            st.dataframe(filtered_df.head(10), use_container_width=True)
            with st.expander("Show full filtered data"):
                st.dataframe(filtered_df, use_container_width=True)

            st.subheader("📈 Sales Summary")
            total_sales = filtered_df['total_price'].sum()
            total_quantity = filtered_df['quantity'].sum()
            total_transactions = filtered_df.shape[0]

            mcol1, mcol2, mcol3 = st.columns(3)
            mcol1.metric("Total Sales (IDR)", f"{total_sales:,.0f}")
            mcol2.metric("Total Quantity Sold", f"{total_quantity:,}")
            mcol3.metric("Total Transactions", f"{total_transactions:,}")

            if filtered_df.empty:
                st.warning("No data available for the selected filters.")
            else:
                st.subheader("📊 Charts & Visualizations")

                min_date = filtered_df['date'].min().date()
                max_date = filtered_df['date'].max().date()

                dcol1, dcol2 = st.columns(2)
                with dcol1:
                    start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
                with dcol2:
                    end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

                if start_date > end_date:
                    st.error("⚠️ Start date must be before end date.")
                else:
                    chart_df = filtered_df[
                        (filtered_df['date'] >= pd.to_datetime(start_date)) &
                        (filtered_df['date'] <= pd.to_datetime(end_date))
                    ]

                    color_palette = px.colors.qualitative.Set2

                    sales_by_type = chart_df.groupby('type', as_index=False)['total_price'].sum().sort_values('total_price', ascending=False)
                    fig1 = px.bar(
                        sales_by_type,
                        x='type',
                        y='total_price',
                        title="Sales by Drink Type (Revenue)",
                        labels={'total_price': 'Total Sales (IDR)', 'type': 'Drink Type'},
                        color='type',
                        color_discrete_sequence=color_palette
                    )
                    st.plotly_chart(fig1, use_container_width=True)

                    sales_by_location = chart_df.groupby('Location', as_index=False)['total_price'].sum()
                    fig2 = px.pie(
                        sales_by_location,
                        names='Location',
                        values='total_price',
                        title="Sales by Location (Revenue)",
                        color_discrete_sequence=color_palette
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                    daily_sales = chart_df.groupby('date', as_index=False)['total_price'].sum().sort_values('date')
                    fig3 = px.line(
                        daily_sales,
                        x='date',
                        y='total_price',
                        title="Daily Sales Over Time",
                        labels={'total_price': 'Total Sales (IDR)', 'date': 'Date'}
                    )
                    st.plotly_chart(fig3, use_container_width=True)

                    monthly_sales = chart_df.groupby('month', as_index=False)['total_price'].sum()
                    monthly_sales['month_dt'] = pd.to_datetime(monthly_sales['month'] + "-01")
                    monthly_sales = monthly_sales.sort_values('month_dt')
                    fig4 = px.line(
                        monthly_sales,
                        x='month_dt',
                        y='total_price',
                        title="Monthly Sales Trend",
                        labels={'total_price': 'Total Sales (IDR)', 'month_dt': 'Month'}
                    )
                    fig4.update_xaxes(tickformat="%Y-%m")
                    st.plotly_chart(fig4, use_container_width=True)

                    best_by_qty = chart_df.groupby('type', as_index=False).agg({'quantity': 'sum', 'total_price': 'sum'})
                    best_by_qty = best_by_qty.sort_values('quantity', ascending=False).reset_index(drop=True)

                    st.subheader("🏆 Best Selling Type")
                    if not best_by_qty.empty:
                        top1 = best_by_qty.iloc[0]
                        st.write(f"**{top1['type']}** — {int(top1['quantity']):,} units sold — Revenue: Rp {int(top1['total_price']):,.0f}")
                    else:
                        st.write("No best-selling type available for selected filters.")

                    st.subheader("Top Types by Quantity Sold")
                    top_qty_chart = best_by_qty.head(10)
                    fig_qty = px.bar(
                        top_qty_chart,
                        x='type',
                        y='quantity',
                        title="Top 10 Types (by Quantity)",
                        labels={'quantity': 'Quantity Sold', 'type': 'Type'},
                        color='type',
                        color_discrete_sequence=color_palette
                    )
                    st.plotly_chart(fig_qty, use_container_width=True)

                    st.subheader("Top Types by Revenue")
                    top_rev_chart = chart_df.groupby('type', as_index=False)['total_price'].sum().sort_values('total_price', ascending=False).head(10)
                    fig_rev = px.bar(
                        top_rev_chart,
                        x='type',
                        y='total_price',
                        title="Top 10 Types (by Revenue)",
                        labels={'total_price': 'Total Sales (IDR)', 'type': 'Type'},
                        color='type',
                        color_discrete_sequence=color_palette
                    )
                    st.plotly_chart(fig_rev, use_container_width=True)

                    with st.expander("Show Top Types Table"):
                        st.dataframe(best_by_qty.head(50).assign(total_price=lambda d: d['total_price'].map('{:,.0f}'.format)), use_container_width=True)

# ----------- Initialize session state variables -----------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ''

# ----------- Main app logic -----------
if not st.session_state.logged_in:
    login_page()
else:
    dashboard()



