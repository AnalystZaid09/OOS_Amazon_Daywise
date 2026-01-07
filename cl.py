import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Amazon OOS Daywise Analysis", layout="wide")

st.title("📊 Amazon OOS Daywise Analysis Dashboard")

# File upload section
st.sidebar.header("Upload Files")
max_days_file = st.sidebar.file_uploader("Upload 90 Days Sales File", type=['xlsx'])
min_days_file = st.sidebar.file_uploader("Upload 15 Days Sales File", type=['xlsx'])
inventory_file = st.sidebar.file_uploader("Upload Inventory File", type=['xlsx'])
pm_file = st.sidebar.file_uploader("Upload PM File", type=['xlsx'])

# Input parameters
st.sidebar.header("Parameters")
max_days = st.sidebar.number_input("Maximum Number of Days", min_value=1, value=90)
min_days = st.sidebar.number_input("Minimum Number of Days", min_value=1, value=15)

# Process button
process_data = st.sidebar.button("Process Data", type="primary")

def load_and_clean_sales_data(file, price_col='item-price'):
    """Load and clean sales data"""
    df = pd.read_excel(file)
    df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
    df = df[(df[price_col].notna()) & (df[price_col] != 0)]
    df.reset_index(drop=True, inplace=True)
    return df

def create_sales_report(day_max, day_min, PM, Inventory, max_days, min_days):
    """Create sales report dataframe"""
    # Create new dataframe with unique ASINs
    df_new = pd.DataFrame()
    df_new['ASIN'] = day_max['asin'].dropna().drop_duplicates().reset_index(drop=True)
    
    # Add Brand from PM
    df_pm_lookup = PM.iloc[:, [0, 6]].copy()
    df_pm_lookup.columns = ['ASIN', 'Brand']
    df_pm_lookup = df_pm_lookup.drop_duplicates(subset='ASIN', keep='first')
    df_new['Brand'] = df_new['ASIN'].map(df_pm_lookup.set_index('ASIN')['Brand'])
    
    # Add Product Name
    df_product_lookup = day_max[['asin', 'product-name']].dropna(subset=['asin']).drop_duplicates(subset='asin', keep='first')
    df_product_lookup.columns = ['ASIN', 'Product']
    df_new['Product'] = df_new['ASIN'].map(df_product_lookup.set_index('ASIN')['Product'])
    
    # Calculate Sales for Max days
    asin_qty_sum = day_max.groupby('asin', as_index=False)['quantity'].sum()
    df_new['Sale last Max days'] = df_new['ASIN'].map(asin_qty_sum.set_index('asin')['quantity'])
    df_new['Sale last Max days'] = pd.to_numeric(df_new['Sale last Max days'], errors='coerce').fillna(0)
    df_new['DRR Max days'] = df_new['Sale last Max days'] / max_days
    
    # Calculate Sales for Min days
    day_min['quantity'] = pd.to_numeric(day_min['quantity'], errors='coerce').fillna(0)
    asin_sales_sum = day_min.groupby('asin', as_index=False)['quantity'].sum()
    df_new['Sale last Min days'] = df_new['ASIN'].map(asin_sales_sum.set_index('asin')['quantity'])
    df_new['Sale last Min days'] = df_new['Sale last Min days'].fillna(0)
    df_new['Sale last Min days'] = pd.to_numeric(df_new['Sale last Min days'], errors='coerce').fillna(0)
    df_new['DRR Min days'] = df_new['Sale last Min days'] / min_days
    
    # Add Stock Information
    df_inventory_lookup = Inventory.iloc[:, [2, 10]].copy()
    df_inventory_lookup.columns = ['ASIN', 'SIH']
    df_inventory_lookup = df_inventory_lookup.drop_duplicates(subset='ASIN', keep='first')
    df_new['SIH'] = df_new['ASIN'].map(df_inventory_lookup.set_index('ASIN')['SIH'])
    
    df_inventory_lookup = Inventory.iloc[:, [2, 12]].copy()
    df_inventory_lookup.columns = ['ASIN', 'Reserved Stock']
    df_inventory_lookup = df_inventory_lookup.drop_duplicates(subset='ASIN', keep='first')
    df_new['Reserved Stock'] = df_new['ASIN'].map(df_inventory_lookup.set_index('ASIN')['Reserved Stock'])
    
    df_new['SIH'] = pd.to_numeric(df_new['SIH'], errors='coerce').fillna(0)
    df_new['Reserved Stock'] = pd.to_numeric(df_new['Reserved Stock'], errors='coerce').fillna(0)
    df_new['Total Stock'] = df_new['SIH'] + df_new['Reserved Stock']
    
    # Add CP
    df_pm_lookup = PM.iloc[:, [0, 9]].copy()
    df_pm_lookup.columns = ['ASIN', 'CP']
    df_pm_lookup = df_pm_lookup.drop_duplicates(subset='ASIN', keep='first')
    df_new['CP'] = df_new['ASIN'].map(df_pm_lookup.set_index('ASIN')['CP'])
    
    df_new['Total Value'] = df_new["Total Stock"] * df_new["CP"]
    
    # Add Manager
    df_pm_lookup_mgr = PM.iloc[:, [0, 4]].copy()
    df_pm_lookup_mgr.columns = ['ASIN', 'Manager']
    df_pm_lookup_mgr = df_pm_lookup_mgr.drop_duplicates(subset='ASIN', keep='first')
    df_new['Manager'] = df_new['ASIN'].map(df_pm_lookup_mgr.set_index('ASIN')['Manager'])
    
    return df_new

def create_inventory_report(Inventory, PM, df_new, max_days, min_days):
    """Create inventory report dataframe"""
    # Create pivot table
    Inventory_pivot = Inventory.pivot_table(
        index=["asin", "sku"],
        values=["afn-fulfillable-quantity", "afn-reserved-quantity"],
        aggfunc="sum"
    )
    Inventory_pivot.reset_index(inplace=True)
    Inventory_pivot["Total Stock"] = Inventory_pivot["afn-fulfillable-quantity"] + Inventory_pivot["afn-reserved-quantity"]
    
    # Merge with PM data
    Inventory_pivot = Inventory_pivot.merge(PM, left_on="asin", right_on="ASIN", how="left")
    
    # Select relevant columns
    Inventory_pivot = Inventory_pivot[['asin', 'sku', 'Vendor SKU Codes', 'Brand Manager', 'Brand',
                                       'Product Name', 'afn-fulfillable-quantity', 'afn-reserved-quantity',
                                       'Total Stock', 'CP']]
    
    # Add sales data with Max days DRR
    df_new_indexed = df_new.set_index("ASIN")
    Inventory_pivot["Sales last Max days"] = Inventory_pivot["asin"].map(df_new_indexed["Sale last Max days"])
    Inventory_pivot["DRR Max"] = (Inventory_pivot["Sales last Max days"] / max_days).round(2)
    
    # Add sales data with Min days DRR
    Inventory_pivot["Sales last Min days"] = Inventory_pivot["asin"].map(df_new_indexed["Sale last Min days"])
    Inventory_pivot["DRR Min"] = (Inventory_pivot["Sales last Min days"] / min_days).round(2)
    
    return Inventory_pivot

def convert_df_to_excel(df):
    """Convert dataframe to Excel format for download"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()

# Main processing logic
if process_data and all([max_days_file, min_days_file, inventory_file, pm_file]):
    with st.spinner('Processing data...'):
        try:
            # Load data
            day_max = load_and_clean_sales_data(max_days_file)
            day_min = load_and_clean_sales_data(min_days_file)
            Inventory = pd.read_excel(inventory_file)
            PM = pd.read_excel(pm_file)
            
            # Create reports
            sales_report = create_sales_report(day_max, day_min, PM, Inventory, max_days, min_days)
            inventory_report = create_inventory_report(Inventory, PM, sales_report, max_days, min_days)
            
            # Store in session state
            st.session_state['sales_report'] = sales_report
            st.session_state['inventory_report'] = inventory_report
            st.session_state['processed'] = True
            
            st.success('✅ Data processed successfully!')
            
        except Exception as e:
            st.error(f'❌ Error processing data: {str(e)}')
            st.session_state['processed'] = False

elif process_data:
    st.warning('⚠️ Please upload all required files before processing.')

# Display results in tabs
if st.session_state.get('processed', False):
    tab1, tab2 = st.tabs(["📈 Sales Report", "📦 Inventory Report"])
    
    with tab1:
        st.header("Sales Report")
        sales_df = st.session_state['sales_report']
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Products", len(sales_df))
        with col2:
            st.metric("Total Sales (Max)", f"{sales_df['Sale last Max days'].sum():,.0f}")
        with col3:
            st.metric("Total Sales (Min)", f"{sales_df['Sale last Min days'].sum():,.0f}")
        with col4:
            st.metric("Total Stock Value", f"₹{sales_df['Total Value'].sum():,.2f}")
        
        # Display dataframe
        st.dataframe(sales_df, use_container_width=True, height=500)
        
        # Download button
        excel_data = convert_df_to_excel(sales_df)
        st.download_button(
            label="📥 Download Sales Report",
            data=excel_data,
            file_name="sales_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with tab2:
        st.header("Inventory Report")
        inventory_df = st.session_state['inventory_report']
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total SKUs", len(inventory_df))
        with col2:
            st.metric("Total Fulfillable", f"{inventory_df['afn-fulfillable-quantity'].sum():,.0f}")
        with col3:
            st.metric("Total Reserved", f"{inventory_df['afn-reserved-quantity'].sum():,.0f}")
        with col4:
            st.metric("Total Stock", f"{inventory_df['Total Stock'].sum():,.0f}")
        
        # Display dataframe
        st.dataframe(inventory_df, use_container_width=True, height=500)
        
        # Download button
        excel_data = convert_df_to_excel(inventory_df)
        st.download_button(
            label="📥 Download Inventory Report",
            data=excel_data,
            file_name="inventory_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("👆 Upload all required files and click 'Process Data' to generate reports.")
    
    # Show instructions
    with st.expander("ℹ️ Instructions"):
        st.markdown("""
        ### How to use this application:
        
        1. **Upload Files** (in the sidebar):
           - 90 Days Sales File
           - 15 Days Sales File
           - Inventory File
           - PM File
        
        2. **Set Parameters**:
           - Maximum Number of Days (default: 90) - used for DRR Max calculation
           - Minimum Number of Days (default: 15) - used for DRR Min calculation
        
        3. **Click 'Process Data'** to generate reports
        
        4. **View Results**:
           - Sales Report tab: View and download sales analysis
           - Inventory Report tab: View and download inventory analysis
        
        5. **Download Reports** using the download buttons in each tab
        """)
