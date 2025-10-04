import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# Page config
st.set_page_config(
    page_title="Villa 5 & 6 Manager",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

@st.cache_resource
def get_google_sheet_connection():
    """Connect to Google Sheets using service account"""
    try:
        # Use Streamlit secrets for credentials
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load data from Google Sheets"""
    try:
        client = get_google_sheet_connection()
        if not client:
            return pd.DataFrame()
        
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Clean data
        if not df.empty:
            df['PROGRESS_NUM'] = df['PROGRESS'].astype(str).str.rstrip('%').astype(float)
            df['START'] = pd.to_datetime(df['START_DATE'], format='%d/%m/%Y', errors='coerce')
            df['END'] = pd.to_datetime(df['END_DATE'], format='%d/%m/%Y', errors='coerce')
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def save_data(df):
    """Save data back to Google Sheets"""
    try:
        client = get_google_sheet_connection()
        if not client:
            return False
        
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        
        # Prepare data for upload
        df_upload = df.copy()
        df_upload['PROGRESS'] = df_upload['PROGRESS_NUM'].astype(str) + '%'
        df_upload = df_upload.drop(columns=['PROGRESS_NUM', 'START', 'END'], errors='ignore')
        
        # Clear and update
        sheet.clear()
        sheet.update([df_upload.columns.values.tolist()] + df_upload.values.tolist())
        return True
    except Exception as e:
        st.error(f"Error saving: {e}")
        return False

def create_timeline_chart(df):
    """Create Gantt chart timeline"""
    if df.empty or df['START'].isna().all():
        st.info("No timeline data available")
        return None
    
    df_valid = df.dropna(subset=['START', 'END'])
    
    fig = go.Figure()
    
    colors = {'Villa 5': '#3B82F6', 'Villa 6': '#10B981'}
    
    for project in df_valid['PROJECT'].unique():
        project_df = df_valid[df_valid['PROJECT'] == project].sort_values('START')
        
        for _, task in project_df.iterrows():
            fig.add_trace(go.Bar(
                name=task['TASK_NAME'],
                x=[task['END'] - task['START']],
                y=[f"{task['PROJECT']}: {task['TASK_NAME'][:40]}"],
                base=task['START'],
                orientation='h',
                marker_color=colors.get(project, '#6B7280'),
                text=f"{task['PROGRESS']}",
                textposition='inside',
                hovertemplate=f"<b>{task['TASK_NAME']}</b><br>" +
                             f"Start: {task['START'].strftime('%d/%m/%Y')}<br>" +
                             f"End: {task['END'].strftime('%d/%m/%Y')}<br>" +
                             f"Progress: {task['PROGRESS']}<br>" +
                             f"<extra></extra>",
                showlegend=False
            ))
    
    fig.update_layout(
        title="Project Timeline",
        xaxis_title="Date",
        height=max(400, len(df_valid) * 30),
        barmode='overlay',
        hovermode='closest'
    )
    
    return fig

def create_budget_chart(df):
    """Budget comparison"""
    budget_data = df.groupby('PROJECT').agg({
        'BUDGET': 'sum',
        'ACTUAL_COST': 'sum'
    }).reset_index()
    
    fig = go.Figure(data=[
        go.Bar(name='Budget', x=budget_data['PROJECT'], y=budget_data['BUDGET'], 
               marker_color='#3B82F6', text=budget_data['BUDGET'], textposition='outside'),
        go.Bar(name='Spent', x=budget_data['PROJECT'], y=budget_data['ACTUAL_COST'], 
               marker_color='#EF4444', text=budget_data['ACTUAL_COST'], textposition='outside')
    ])
    
    fig.update_layout(
        title='Budget Overview',
        barmode='group',
        height=400,
        yaxis_title='Amount ($)',
        hovermode='x unified'
    )
    
    return fig

def create_progress_chart(df):
    """Progress by project"""
    progress_data = df.groupby('PROJECT')['PROGRESS_NUM'].mean().reset_index()
    
    fig = go.Figure(data=[
        go.Bar(
            x=progress_data['PROJECT'],
            y=progress_data['PROGRESS_NUM'],
            marker_color='#10B981',
            text=progress_data['PROGRESS_NUM'].round(1).astype(str) + '%',
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title='Overall Progress by Project',
        yaxis_range=[0, 110],
        yaxis_title='Progress (%)',
        height=400
    )
    
    return fig

def create_status_chart(df):
    """Task status distribution"""
    status_counts = df.groupby(['PROJECT', 'STATUS']).size().reset_index(name='count')
    
    fig = go.Figure()
    
    for project in status_counts['PROJECT'].unique():
        project_data = status_counts[status_counts['PROJECT'] == project]
        fig.add_trace(go.Bar(
            name=project,
            x=project_data['STATUS'],
            y=project_data['count'],
            text=project_data['count'],
            textposition='outside'
        ))
    
    fig.update_layout(
        title='Task Status by Project',
        barmode='group',
        height=400,
        yaxis_title='Number of Tasks'
    )
    
    return fig

def main():
    # Sidebar
    with st.sidebar:
        st.markdown("### 🏗️ Villa Projects")
        st.markdown("---")
        
        # User role selection
        role = st.selectbox(
            "Your Role",
            ["Project Manager", "Site Manager", "Purchaser", "Assistant", "Client"],
            help="Select your role to customize the view"
        )
        
        st.markdown("---")
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Filters")
        
        # Load data for filters
        df = load_data()
        
        if not df.empty:
            project_filter = st.selectbox(
                "Project",
                ["All"] + df['PROJECT'].unique().tolist()
            )
            
            type_filter = st.multiselect(
                "Task Type",
                df['TYPE'].unique().tolist(),
                default=df['TYPE'].unique().tolist()
            )
            
            status_filter = st.multiselect(
                "Status",
                df['STATUS'].unique().tolist(),
                default=df['STATUS'].unique().tolist()
            )
    
    # Main content
    st.markdown('<p class="main-header">🏗️ Villa 5 & Villa 6 Project Manager</p>', unsafe_allow_html=True)
    
    # Load and filter data
    df = load_data()
    
    if df.empty:
        st.error("No data loaded. Check your Google Sheets connection in Streamlit secrets.")
        st.stop()
    
    # Apply filters
    if project_filter != "All":
        df = df[df['PROJECT'] == project_filter]
    df = df[df['TYPE'].isin(type_filter)]
    df = df[df['STATUS'].isin(status_filter)]
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    villa5 = df[df['PROJECT'] == 'Villa 5']
    villa6 = df[df['PROJECT'] == 'Villa 6']
    
    with col1:
        v5_progress = villa5['PROGRESS_NUM'].mean() if len(villa5) > 0 else 0
        st.metric("Villa 5 Progress", f"{v5_progress:.1f}%", 
                 delta=f"{len(villa5[villa5['STATUS']=='Complete'])} tasks done")
    
    with col2:
        v6_progress = villa6['PROGRESS_NUM'].mean() if len(villa6) > 0 else 0
        st.metric("Villa 6 Progress", f"{v6_progress:.1f}%",
                 delta=f"{len(villa6[villa6['STATUS']=='Complete'])} tasks done")
    
    with col3:
        total_budget = df['BUDGET'].sum()
        total_spent = df['ACTUAL_COST'].sum()
        st.metric("Total Budget", f"${total_budget:,.0f}",
                 delta=f"${total_spent:,.0f} spent")
    
    with col4:
        critical_tasks = len(df[df['PRIORITY'].isin(['Critical', 'High'])])
        st.metric("Critical Tasks", critical_tasks,
                 delta=f"{len(df[df['STATUS']!='Complete'])} pending")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "✏️ Update", "📋 Tasks", "📄 Reports"])
    
    with tab1:
        st.markdown("### Project Overview")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = create_progress_chart(df)
            st.plotly_chart(fig, use_container_width=True)
            
            fig = create_budget_chart(df)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = create_status_chart(df)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### Timeline")
        fig = create_timeline_chart(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        if role in ["Project Manager", "Site Manager", "Assistant"]:
            st.markdown("### Update Task Progress")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                task_options = df['TASK_ID'].tolist()
                selected_task = st.selectbox(
                    "Select Task",
                    task_options,
                    format_func=lambda x: f"{x} - {df[df['TASK_ID']==x]['TASK_NAME'].values[0]}"
                )
            
            with col2:
                new_progress = st.slider("New Progress (%)", 0, 100, 0, 5)
            
            if st.button("Update Progress", type="primary"):
                df.loc[df['TASK_ID'] == selected_task, 'PROGRESS_NUM'] = new_progress
                df.loc[df['TASK_ID'] == selected_task, 'PROGRESS'] = f"{new_progress}%"
                
                if new_progress == 100:
                    df.loc[df['TASK_ID'] == selected_task, 'STATUS'] = 'Complete'
                elif new_progress > 0:
                    df.loc[df['TASK_ID'] == selected_task, 'STATUS'] = 'In Progress'
                
                if save_data(df):
                    st.success(f"Updated {selected_task} to {new_progress}%!")
                    st.cache_data.clear()
                    st.rerun()
        
        if role in ["Project Manager", "Purchaser", "Assistant"]:
            st.markdown("---")
            st.markdown("### Update Actual Cost")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                cost_task = st.selectbox(
                    "Select Task for Cost",
                    df['TASK_ID'].tolist(),
                    format_func=lambda x: f"{x} - {df[df['TASK_ID']==x]['TASK_NAME'].values[0]}",
                    key="cost_task"
                )
            
            with col2:
                new_cost = st.number_input("Actual Cost ($)", min_value=0, step=1000)
            
            if st.button("Update Cost", type="primary"):
                df.loc[df['TASK_ID'] == cost_task, 'ACTUAL_COST'] = new_cost
                
                if save_data(df):
                    st.success(f"Updated cost for {cost_task}!")
                    st.cache_data.clear()
                    st.rerun()
    
    with tab3:
        st.markdown("### All Tasks")
        
        # Display columns selection
        display_cols = ['PROJECT', 'TASK_ID', 'TASK_NAME', 'TYPE', 'ASSIGNED_TO', 
                       'START_DATE', 'END_DATE', 'PROGRESS', 'STATUS', 'PRIORITY', 'BUDGET', 'ACTUAL_COST']
        
        st.dataframe(
            df[display_cols],
            use_container_width=True,
            height=600,
            hide_index=True
        )
        
        # Export button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"project_data_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with tab4:
        if role in ["Project Manager", "Assistant"]:
            st.markdown("### Weekly Report")
            
            if st.button("Generate Report", type="primary"):
                report = f"""
# Weekly Project Report
**Generated:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

## Villa 5
- **Progress:** {villa5['PROGRESS_NUM'].mean():.1f}%
- **Completed:** {len(villa5[villa5['STATUS']=='Complete'])} tasks
- **In Progress:** {len(villa5[villa5['STATUS']=='In Progress'])} tasks
- **Budget:** ${villa5['BUDGET'].sum():,.0f}
- **Spent:** ${villa5['ACTUAL_COST'].sum():,.0f}

## Villa 6
- **Progress:** {villa6['PROGRESS_NUM'].mean():.1f}%
- **Completed:** {len(villa6[villa6['STATUS']=='Complete'])} tasks
- **In Progress:** {len(villa6[villa6['STATUS']=='In Progress'])} tasks
- **Budget:** ${villa6['BUDGET'].sum():,.0f}
- **Spent:** ${villa6['ACTUAL_COST'].sum():,.0f}

## Critical Tasks
"""
                critical = df[(df['PRIORITY'].isin(['Critical', 'High'])) & (df['STATUS'] != 'Complete')]
                for _, task in critical.iterrows():
                    report += f"- **{task['PROJECT']}:** {task['TASK_NAME']} ({task['PROGRESS']})\n"
                
                st.markdown(report)
                
                # Download report
                st.download_button(
                    "📥 Download Report",
                    report,
                    file_name=f"weekly_report_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown"
                )

if __name__ == "__main__":
    main()
