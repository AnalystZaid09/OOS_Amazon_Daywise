import streamlit as st
import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Sales & Inventory Analysis", layout="wide")

st.title("📊 Sales & Inventory Analysis Dashboard")
st.markdown("---")

# File upload section
st.header("📁 Upload Your Data Files")

col1, col2 = st.columns(2)

with col1:
    file_max_days = st.file_uploader("Upload Max Days Sales Data (Excel)", type=['xlsx'], key='maxdays')
    file_min_days = st.file_uploader("Upload Min Days Sales Data (Excel)", type=['xlsx'], key='mindays')

with col2:
    file_inventory = st.file_uploader("Upload Inventory Data (Excel)", type=['xlsx'], key='inventory')
    file_pm = st.file_uploader("Upload Product Master (PM) Data (Excel)", type=['xlsx'], key='pm')

# Process data when all files are uploaded
if file_max_days and file_min_days and file_inventory and file_pm:
    try:
        with st.spinner("Reading files..."):
            day_max = pd.read_excel(file_max_days)
            day_min = pd.read_excel(file_min_days)
            Inventory = pd.read_excel(file_inventory)
            PM = pd.read_excel(file_pm)

        st.success("✅ All files loaded successfully!")

        # ---- Inventory Filtering & New ASIN Append Logic ---- #
        with st.spinner("Filtering inventory stock..."):
            Inventory.iloc[:, 10] = pd.to_numeric(Inventory.iloc[:, 10], errors='coerce').fillna(0)  # fulfillable qty
            Inventory.iloc[:, 12] = pd.to_numeric(Inventory.iloc[:, 12], errors='coerce').fillna(0)  # reserved qty

            asin_fulfillable = Inventory.loc[Inventory.iloc[:, 10] != 0, Inventory.columns[2]].dropna().unique().tolist()
            asin_reserved = Inventory.loc[Inventory.iloc[:, 12] != 0, Inventory.columns[2]].dropna().unique().tolist()

            asin_inventory_filtered = list(set(asin_fulfillable) | set(asin_reserved))
            sales_asins = day_max['asin'].dropna().unique().tolist()
            new_asins = [a for a in asin_inventory_filtered if a not in sales_asins]

            df_inventory_new = Inventory[Inventory.iloc[:, 2].isin(new_asins)].drop_duplicates(subset=Inventory.columns[2], keep='first')
            df_inventory_new = df_inventory_new.iloc[:, [2, 10, 12]].copy()
            df_inventory_new.columns = ['ASIN', 'SIH', 'Reserved Stock']

        st.success(f"✅ Inventory filtered! {len(new_asins)} new ASINs will be added to the report")

        # ---- Data Cleaning ---- #
        with st.spinner("Cleaning sales data..."):
            day_max['item-price'] = pd.to_numeric(day_max['item-price'], errors='coerce')
            day_max = day_max[(day_max['item-price'].notna()) & (day_max['item-price'] != 0)]

            day_min['item-price'] = pd.to_numeric(day_min['item-price'], errors='coerce')
            day_min = day_min[(day_min['item-price'].notna()) & (day_min['item-price'] != 0)]

            day_max.reset_index(drop=True, inplace=True)
            day_min.reset_index(drop=True, inplace=True)

        st.success("✅ Sales data cleaned!")

        # ---- Configuration Inputs ---- #
        st.header("⚙️ Configuration")
        col1, col2 = st.columns(2)

        with col1:
            max_days = st.number_input("Enter Maximum Number of Days", min_value=1, value=90, step=1)
        with col2:
            min_days = st.number_input("Enter Minimum Number of Days", min_value=1, value=15, step=1)

        # ---- Generate Analysis ---- #
        if st.button("🚀 Generate Analysis", type="primary"):
            with st.spinner("Generating report..."):
                df_new = pd.DataFrame()
                df_new['ASIN'] = day_max['asin'].dropna().drop_duplicates().reset_index(drop=True)

                df_pm_brand = PM.iloc[:, [0, 6]].drop_duplicates(subset=PM.columns[0], keep='first')
                df_pm_brand.columns = ['ASIN', 'Brand']
                df_new['Brand'] = df_new['ASIN'].map(df_pm_brand.set_index('ASIN')['Brand'])

                df_pm_product = day_max[['asin', 'product-name']].drop_duplicates(subset='asin', keep='first')
                df_pm_product.columns = ['ASIN', 'Product']
                df_new['Product'] = df_new['ASIN'].map(df_pm_product.set_index('ASIN')['Product'])

                df_max_sales = day_max.groupby('asin')['quantity'].sum()
                df_new['Sale last Max days'] = df_new['ASIN'].map(df_max_sales).fillna(0)

                df_new['DRR Max days'] = (df_new['Sale last Max days'] / max_days).round(2)
                df_min_sales = day_min.groupby('asin')['quantity'].sum()
                df_new['Sale last Min days'] = df_new['ASIN'].map(df_min_sales).fillna(0)

                df_new['DRR Min days'] = (df_new['Sale last Min days'] / min_days).round(2)

                df_inventory_main = Inventory.iloc[:, [2, 10]].drop_duplicates(subset=Inventory.columns[2], keep='first')
                df_inventory_main.columns = ['ASIN', 'SIH']
                df_new['SIH'] = df_new['ASIN'].map(df_inventory_main.set_index('ASIN')['SIH'])

                df_inventory_reserved = Inventory.iloc[:, [2, 12]].drop_duplicates(subset=Inventory.columns[2], keep='first')
                df_inventory_reserved.columns = ['ASIN', 'Reserved Stock']
                df_new['Reserved Stock'] = df_new['ASIN'].map(df_inventory_reserved.set_index('ASIN')['Reserved Stock'])

                df_new['SIH'] = pd.to_numeric(df_new['SIH'], errors='coerce').fillna(0)
                df_new['Reserved Stock'] = pd.to_numeric(df_new['Reserved Stock'], errors='coerce').fillna(0)
                df_new['Total Stock'] = df_new['SIH'] + df_new['Reserved Stock']

                df_pm_cp = PM.iloc[:, [0, 9]].drop_duplicates(subset=PM.columns[0], keep='first')
                df_pm_cp.columns = ['ASIN', 'CP']
                df_new['CP'] = df_new['ASIN'].map(df_pm_cp.set_index('ASIN')['CP']).fillna(0)

                df_new['Total Value'] = df_new['Total Stock'] * df_new['CP']

                df_pm_mgr = PM.iloc[:, [0, 4]].drop_duplicates(subset=PM.columns[0], keep='first')
                df_pm_mgr.columns = ['ASIN', 'Manager']
                df_new['Manager'] = df_new['ASIN'].map(df_pm_mgr.set_index('ASIN')['Manager'])

                df_new = pd.concat([df_new, df_inventory_new], ignore_index=True)
                df_new['Total Value'] = df_new['Total Stock'] * df_new['CP']

            st.success("✅ Report generated!")

            st.dataframe(df_new, use_container_width=True, height=400)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_new.to_excel(writer, index=False, sheet_name='Analysis')

            st.download_button(
                label="📥 Download Excel Report",
                data=output.getvalue(),
                file_name="sales_inventory_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error("❌ Error in processing")
        st.exception(e)
