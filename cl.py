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
    file_max_days = st.file_uploader("Upload Max Days Sales Data (Excel)", type=['xlsx'], key='maxdays', 
                                      help="Upload sales data for the longer period (e.g., 90, 100 days)")
    file_min_days = st.file_uploader("Upload Min Days Sales Data (Excel)", type=['xlsx'], key='mindays',
                                      help="Upload sales data for the shorter period (e.g., 15, 30 days)")

with col2:
    file_inventory = st.file_uploader("Upload Inventory Data (Excel)", type=['xlsx'], key='inventory')
    file_pm = st.file_uploader("Upload Product Master (PM) Data (Excel)", type=['xlsx'], key='pm')

# Process data when all files are uploaded
if file_max_days and file_min_days and file_inventory and file_pm:
    
    try:
        # Read the files
        with st.spinner("Reading files..."):
            day_max = pd.read_excel(file_max_days)
            day_min = pd.read_excel(file_min_days)
            Inventory = pd.read_excel(file_inventory)
            PM = pd.read_excel(file_pm)
        
        st.success("✅ All files loaded successfully!")
        
        # Show data info
        with st.expander("📋 View Data Summary"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Max Days Records (Raw)", day_max.shape[0])
            with col2:
                st.metric("Min Days Records (Raw)", day_min.shape[0])
            with col3:
                st.metric("Inventory Items", Inventory.shape[0])
            with col4:
                st.metric("Product Master Items", PM.shape[0])
        
        # Data cleaning
        with st.spinner("Cleaning data..."):
            # Clean day_max
            day_max['item-price'] = pd.to_numeric(day_max['item-price'], errors='coerce')
            day_max = day_max[(day_max['item-price'].notna()) & (day_max['item-price'] != 0)]
            day_max.reset_index(drop=True, inplace=True)
            
            # Clean day_min
            day_min['item-price'] = pd.to_numeric(day_min['item-price'], errors='coerce')
            day_min = day_min[(day_min['item-price'].notna()) & (day_min['item-price'] != 0)]
            day_min.reset_index(drop=True, inplace=True)
        
        st.success(f"✅ Data cleaned! {day_max.shape[0]} records in max days, {day_min.shape[0]} records in min days")
        
        # Input for days
        st.header("⚙️ Configuration")
        st.info("💡 Enter the number of days corresponding to your uploaded sales data files")
        
        col1, col2 = st.columns(2)
        
        with col1:
            max_days = st.number_input("Enter Maximum Number of Days", 
                                       min_value=1, 
                                       value=90, 
                                       step=1,
                                       help="Number of days in your max days sales file (e.g., 90, 100, 120)")
        
        with col2:
            min_days = st.number_input("Enter Minimum Number of Days", 
                                       min_value=1, 
                                       value=15, 
                                       step=1,
                                       help="Number of days in your min days sales file (e.g., 15, 30, 45)")
        
        if st.button("🚀 Generate Analysis", type="primary"):
            with st.spinner("Processing analysis..."):
                
                # Create new dataframe
                df_new = pd.DataFrame()
                df_new['ASIN'] = (
                    day_max['asin']
                    .dropna()
                    .drop_duplicates()
                    .reset_index(drop=True)
                )
                
                # Brand lookup
                df_pm_lookup = PM.iloc[:, [0, 6]].copy()
                df_pm_lookup.columns = ['ASIN', 'Brand']
                df_pm_lookup = df_pm_lookup.drop_duplicates(subset='ASIN', keep='first')
                df_new['Brand'] = df_new['ASIN'].map(df_pm_lookup.set_index('ASIN')['Brand'])
                
                # Product lookup
                df_product_lookup = (
                    day_max[['asin', 'product-name']]
                    .dropna(subset=['asin'])
                    .drop_duplicates(subset='asin', keep='first')
                )
                df_product_lookup.columns = ['ASIN', 'Product']
                df_new['Product'] = df_new['ASIN'].map(df_product_lookup.set_index('ASIN')['Product'])
                
                # Sale last Max days
                asin_qty_sum = (
                    day_max
                    .groupby('asin', as_index=False)['quantity']
                    .sum()
                )
                df_new['Sale last Max days'] = df_new['ASIN'].map(
                    asin_qty_sum.set_index('asin')['quantity']
                )
                df_new['Sale last Max days'] = pd.to_numeric(df_new['Sale last Max days'], errors='coerce').fillna(0)
                
                # DRR Max days
                df_new['DRR Max days'] = df_new['Sale last Max days'] / max_days
                
                # Sale last Min days
                day_min['quantity'] = pd.to_numeric(day_min['quantity'], errors='coerce').fillna(0)
                asin_sales_sum = (
                    day_min
                    .groupby('asin', as_index=False)['quantity']
                    .sum()
                )
                df_new['Sale last Min days'] = df_new['ASIN'].map(
                    asin_sales_sum.set_index('asin')['quantity']
                )
                df_new['Sale last Min days'] = df_new['Sale last Min days'].fillna(0)
                df_new['Sale last Min days'] = pd.to_numeric(df_new['Sale last Min days'], errors='coerce').fillna(0)
                
                # DRR Min days
                df_new['DRR Min days'] = df_new['Sale last Min days'] / min_days
                
                # SIH lookup
                df_inventory_lookup = Inventory.iloc[:, [2, 10]].copy()
                df_inventory_lookup.columns = ['ASIN', 'SIH']
                df_inventory_lookup = df_inventory_lookup.drop_duplicates(subset='ASIN', keep='first')
                df_new['SIH'] = df_new['ASIN'].map(df_inventory_lookup.set_index('ASIN')['SIH'])
                
                # Reserved Stock lookup
                df_inventory_lookup = Inventory.iloc[:, [2, 12]].copy()
                df_inventory_lookup.columns = ['ASIN', 'Reserved Stock']
                df_inventory_lookup = df_inventory_lookup.drop_duplicates(subset='ASIN', keep='first')
                df_new['Reserved Stock'] = df_new['ASIN'].map(
                    df_inventory_lookup.set_index('ASIN')['Reserved Stock']
                )
                
                # Total Stock - Convert to numeric first
                df_new['SIH'] = pd.to_numeric(df_new['SIH'], errors='coerce').fillna(0)
                df_new['Reserved Stock'] = pd.to_numeric(df_new['Reserved Stock'], errors='coerce').fillna(0)
                df_new['Total Stock'] = df_new['SIH'] + df_new['Reserved Stock']
                
                # CP lookup - Convert to numeric
                df_pm_lookup = PM.iloc[:, [0, 9]].copy()
                df_pm_lookup.columns = ['ASIN', 'CP']
                df_pm_lookup = df_pm_lookup.drop_duplicates(subset='ASIN', keep='first')
                # Convert CP to numeric
                df_pm_lookup['CP'] = pd.to_numeric(df_pm_lookup['CP'], errors='coerce')
                df_new['CP'] = df_new['ASIN'].map(df_pm_lookup.set_index('ASIN')['CP'])
                df_new['CP'] = pd.to_numeric(df_new['CP'], errors='coerce').fillna(0)
                
                # Total Value - Ensure numeric calculation
                df_new['Total Value'] = pd.to_numeric(df_new['Total Stock'], errors='coerce').fillna(0) * pd.to_numeric(df_new['CP'], errors='coerce').fillna(0)
                
                # Manager lookup
                df_pm_lookup_mgr = PM.iloc[:, [0, 4]].copy()
                df_pm_lookup_mgr.columns = ['ASIN', 'Manager']
                df_pm_lookup_mgr = df_pm_lookup_mgr.drop_duplicates(subset='ASIN', keep='first')
                df_new['Manager'] = df_new['ASIN'].map(
                    df_pm_lookup_mgr.set_index('ASIN')['Manager']
                )
                
                # Ensure all numeric columns are properly typed
                numeric_columns = ['Sale last Max days', 'DRR Max days', 'Sale last Min days', 
                                   'DRR Min days', 'SIH', 'Reserved Stock', 'Total Stock', 'CP', 'Total Value']
                for col in numeric_columns:
                    df_new[col] = pd.to_numeric(df_new[col], errors='coerce').fillna(0)
                
                st.success("✅ Analysis completed successfully!")
                
                # Display results
                st.header("📈 Analysis Results")
                
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Products", len(df_new))
                with col2:
                    total_value = df_new['Total Value'].sum()
                    st.metric("Total Stock Value", f"₹{total_value:,.2f}")
                with col3:
                    total_stock = df_new['Total Stock'].sum()
                    st.metric("Total Stock Units", f"{total_stock:,.0f}")
                with col4:
                    avg_drr = df_new['DRR Max days'].mean()
                    st.metric("Avg DRR (Max)", f"{avg_drr:.2f}")
                
                # Display dataframe with formatted numbers
                st.subheader("📊 Detailed Analysis Table")
                
                # Format the display dataframe
                df_display = df_new.copy()
                df_display['DRR Max days'] = df_display['DRR Max days'].round(2)
                df_display['DRR Min days'] = df_display['DRR Min days'].round(2)
                df_display['CP'] = df_display['CP'].round(2)
                df_display['Total Value'] = df_display['Total Value'].round(2)
                
                st.dataframe(df_display, use_container_width=True, height=400)
                
                # Download button
                st.subheader("💾 Download Results")
                
                # Convert dataframe to Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_new.to_excel(writer, index=False, sheet_name='Analysis')
                
                st.download_button(
                    label="📥 Download Excel Report",
                    data=output.getvalue(),
                    file_name="sales_inventory_analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Additional insights
                st.header("🔍 Quick Insights")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Top 10 Products by DRR (Max Days)")
                    top_drr = df_new.nlargest(10, 'DRR Max days')[['ASIN', 'Product', 'Brand', 'DRR Max days']].copy()
                    top_drr['DRR Max days'] = top_drr['DRR Max days'].round(2)
                    st.dataframe(top_drr, use_container_width=True)
                
                with col2:
                    st.subheader("Top 10 Products by Total Stock Value")
                    top_value = df_new.nlargest(10, 'Total Value')[['ASIN', 'Product', 'Brand', 'Total Value']].copy()
                    top_value['Total Value'] = top_value['Total Value'].round(2)
                    st.dataframe(top_value, use_container_width=True)
                
                # Brand-wise summary
                st.subheader("📊 Brand-wise Summary")
                brand_summary = df_new.groupby('Brand').agg({
                    'ASIN': 'count',
                    'Total Stock': 'sum',
                    'Total Value': 'sum',
                    'DRR Max days': 'mean'
                }).round(2)
                brand_summary.columns = ['Product Count', 'Total Stock', 'Total Value', 'Avg DRR Max']
                brand_summary = brand_summary.sort_values('Total Value', ascending=False)
                st.dataframe(brand_summary, use_container_width=True)
                
                # Manager-wise summary (if Manager data exists)
                if 'Manager' in df_new.columns and df_new['Manager'].notna().any():
                    st.subheader("👤 Manager-wise Summary")
                    manager_summary = df_new.groupby('Manager').agg({
                        'ASIN': 'count',
                        'Total Stock': 'sum',
                        'Total Value': 'sum',
                        'DRR Max days': 'mean'
                    }).round(2)
                    manager_summary.columns = ['Product Count', 'Total Stock', 'Total Value', 'Avg DRR Max']
                    manager_summary = manager_summary.sort_values('Total Value', ascending=False)
                    st.dataframe(manager_summary, use_container_width=True)
                
    except Exception as e:
        st.error(f"❌ An error occurred: {str(e)}")
        st.exception(e)
        st.info("Please ensure all files are in the correct format and contain the required columns.")

else:
    st.info("👆 Please upload all four required files to begin the analysis.")
    
    with st.expander("ℹ️ Required File Formats"):
        st.markdown("""
        ### Expected Files:
        1. **Max Days Sales Data**: Sales data for longer period (e.g., 30, 45, 90, 100 days)
           - Should contain columns: 'asin', 'product-name', 'quantity', 'item-price'
        
        2. **Min Days Sales Data**: Sales data for shorter period (e.g., 15, 30, 45 days)
           - Should contain columns: 'asin', 'product-name', 'quantity', 'item-price'
        
        3. **Inventory Data**: Current stock information
           - Should contain columns for ASIN (column 3), SIH (column 11), Reserved Stock (column 13)
        
        4. **Product Master (PM)**: Product details and pricing
           - Should contain ASIN (column 1), Brand (column 7), CP/Cost Price (column 10), Manager (column 5)
        
        **Note:** All files should be in Excel (.xlsx) format.
        
        **Important:** The number of days you enter should match the actual period covered by your sales data files.
        """)