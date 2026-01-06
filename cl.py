# cl.py in github repo - changes.py in folder
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
            Inventory['afn-fulfillable-quantity'] = pd.to_numeric(Inventory['afn-fulfillable-quantity'], errors='coerce').fillna(0)
            Inventory['afn-reserved-quantity'] = pd.to_numeric(Inventory['afn-reserved-quantity'], errors='coerce').fillna(0)
            
            # Normalize ASINs
            for df_temp in [day_max, day_min, Inventory, PM]:
                asin_col = [c for c in df_temp.columns if c.lower() == 'asin'][0]
                df_temp[asin_col] = df_temp[asin_col].astype(str).str.strip().str.upper()

            asin1 = Inventory.loc[Inventory['afn-fulfillable-quantity'] != 0, 'asin'].dropna().unique().tolist()
            asin2 = Inventory.loc[Inventory['afn-reserved-quantity'] != 0, 'asin'].dropna().unique().tolist()

            filtered_asins = asin1 + [a for a in asin2 if a not in asin1]

            # Append ASIN to original column
            df_append = pd.DataFrame({'asin': filtered_asins})
            Inventory = pd.concat([Inventory, df_append], ignore_index=True)

            # Store for report
            st.session_state.filtered_asins = filtered_asins  # session me save

        st.success(f"✅ Inventory filtered! {len(filtered_asins)} new ASINs will be added to the report")

        # ---- Data Cleaning ---- #
        with st.spinner("Cleaning sales data..."):
            # Exclude Cancelled orders and ensure valid quantity
            day_max['item-price'] = pd.to_numeric(day_max['item-price'], errors='coerce')
            day_max = day_max[day_max['order-status'] != 'Cancelled']
            day_max = day_max[day_max['quantity'] > 0]

            day_min['item-price'] = pd.to_numeric(day_min['item-price'], errors='coerce')
            day_min = day_min[day_min['order-status'] != 'Cancelled']
            day_min = day_min[day_min['quantity'] > 0]

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
                
                # Unique ASINs from Sales + Inventory
                sales_asins = day_max['asin'].dropna().drop_duplicates().tolist()
                inventory_asins = st.session_state.filtered_asins
                all_asins = list(set(sales_asins + inventory_asins))

                df_new['ASIN'] = all_asins

                # Map Brand
                df_pm_brand = PM.iloc[:, [0, 6]].drop_duplicates(subset=PM.columns[0], keep='first')
                df_pm_brand.columns = ['ASIN', 'Brand']
                df_new['Brand'] = df_new['ASIN'].map(df_pm_brand.set_index('ASIN')['Brand'])

                # Comprehensive Product Name Mapping
                # 1. PM
                pm_names = PM.set_index(PM.columns[0])[PM.columns[7]].to_dict()
                # 2. day_max
                sales_names = day_max.set_index('asin')['product-name'].to_dict()
                # 3. Inventory
                inv_names = Inventory.set_index('asin')['product-name'].to_dict()
                
                # Combine (Priority: PM > Sales > Inventory)
                full_product_map = {**inv_names, **sales_names, **pm_names}
                df_new['Product'] = df_new['ASIN'].map(full_product_map)

                # Map CP first
                df_pm_cp = PM.iloc[:, [0, 9]].drop_duplicates(subset=PM.columns[0], keep='first')
                df_pm_cp.columns = ['ASIN', 'CP']
                df_new['CP'] = df_new['ASIN'].map(df_pm_cp.set_index('ASIN')['CP']).fillna(0)

                # Map Sales
                df_max_sales = day_max.groupby('asin')['quantity'].sum()
                df_new['Sale last Max days'] = df_new['ASIN'].map(df_max_sales).fillna(0)

                df_new['DRR Max days'] = (df_new['Sale last Max days'] / max_days).round(2)

                df_min_sales = day_min.groupby('asin')['quantity'].sum()
                df_new['Sale last Min days'] = df_new['ASIN'].map(df_min_sales).fillna(0)

                df_new['DRR Min days'] = (df_new['Sale last Min days'] / min_days).round(2)

                # Inventory stock lookup (no extra rows appended)
                inv = Inventory.drop_duplicates('asin').set_index('asin')
                df_new['SIH'] = df_new['ASIN'].map(inv.get('afn-fulfillable-quantity')).fillna(0)
                df_new['Reserved Stock'] = df_new['ASIN'].map(inv.get('afn-reserved-quantity')).fillna(0)
                df_new['Total Stock'] = df_new['SIH'] + df_new['Reserved Stock']

                # Calculate Total Value after CP is mapped
                df_new['Total Value'] = df_new['Total Stock'] * df_new['CP']

                # Map Manager
                df_pm_mgr = PM.iloc[:, [0, 4]].drop_duplicates(subset=PM.columns[0], keep='first')
                df_pm_mgr.columns = ['ASIN', 'Manager']
                df_new['Manager'] = df_new['ASIN'].map(df_pm_mgr.set_index('ASIN')['Manager'])

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
