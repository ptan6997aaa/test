from nicegui import ui, app
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- 1. DATA LOADING & PROCESSING ---
# (Same robust logic as previous versions)

try:
    df_fact = pd.read_excel("FactPerformance.xlsx", sheet_name="Sheet1")
    df_dimStu = pd.read_excel("DimStudents.xlsx", sheet_name="Sheet1")
    df_dimCal = pd.read_excel("DimCalendar.xlsx", sheet_name="Date")
    df_dimSub = pd.read_excel("DimSubjects.xlsx", sheet_name="DimSubjects")
except FileNotFoundError:
    print("Data files not found. Using Dummy Data.")
    n_rows = 1000
    df_fact = pd.DataFrame({
        'StudentID': np.random.randint(1, 20, n_rows),
        'DateKey': np.random.choice(range(20220101, 20220330), n_rows),
        'SubjectID': np.random.randint(1, 5, n_rows),
        'Score': np.random.randint(50, 100, n_rows)
    })
    df_dimStu = pd.DataFrame({'StudentID': range(1, 21), 'GradeLevel': np.random.choice([9, 10, 11, 12], 20)})
    dates = pd.date_range(start='2022-01-01', periods=90)
    df_dimCal = pd.DataFrame({
        'DateKey': [int(d.strftime('%Y%m%d')) for d in dates],
        'Year': dates.year, 'QuarterNumber': dates.quarter, 'Month': dates.month
    })
    df_dimSub = pd.DataFrame({'SubjectID': [1, 2, 3, 4], 'SubjectName': ['Math', 'Science', 'English', 'History']})

# Joins
df = pd.merge(df_fact, df_dimStu[["StudentID", "GradeLevel"]], on="StudentID", how="left")
df = pd.merge(df, df_dimSub[["SubjectID", "SubjectName"]], on="SubjectID", how="left")

# Transformations
df_dimCal["YearQuarterConcat"] = df_dimCal["Year"].astype(str) + " " + df_dimCal["QuarterNumber"].apply(lambda x: f"Q{x}")
df_dimCal["YearMonthConcat"] = df_dimCal["Year"].astype(str) + "-" + df_dimCal["Month"].apply(lambda x: f"{x:02d}")
df = pd.merge(df, df_dimCal[["DateKey", "YearQuarterConcat", "YearMonthConcat", "QuarterNumber", "Year"]], on="DateKey", how="left")

if "Weight" not in df.columns: df["Weight"] = 1
if "WeightedScore" not in df.columns: df["WeightedScore"] = df["Score"] * df["Weight"]
df["PassedScore"] = df["Score"].apply(lambda x: "Pass" if x >= 55 else "Fail")

def get_grade(score):
    if score > 84: return "A"
    if score > 74: return "B"
    if score > 64: return "C"
    if score > 54: return "D"
    return "F"

df["Assessment_Grade"] = df["Score"].apply(get_grade)
grade_order = ['A', 'B', 'C', 'D', 'F']
df['Assessment_Grade'] = pd.Categorical(df['Assessment_Grade'], categories=grade_order, ordered=True)
if "GradeLevel" in df.columns:
    df = df.sort_values(['GradeLevel', 'Assessment_Grade'])


# --- 2. DASHBOARD LOGIC ---

# State Dictionary
state = {
    'grade': 'All',
    'level': 'All',
    'time': 'All',
    'subject': 'All',
    'view_mode': 'Quarter'
}

def get_data(ignore_grade=False, ignore_level=False, ignore_time=False, ignore_subject=False):
    """Filter the dataframe based on current state."""
    d = df.copy()
    if not ignore_grade and state['grade'] != 'All': 
        d = d[d["Assessment_Grade"] == state['grade']]
    if not ignore_level and state['level'] != 'All': 
        d = d[d["GradeLevel"] == state['level']]
    if not ignore_subject and state['subject'] != 'All': 
        d = d[d["SubjectName"] == state['subject']]
    
    # Time Filter
    curr_time = state['time']
    if not ignore_time and curr_time != 'All':
        if 'Q' in curr_time: d = d[d["YearQuarterConcat"] == curr_time]
        else: d = d[d["YearMonthConcat"] == curr_time]
    return d

# --- 3. UI BUILDER ---

@ui.page('/')
def index():
    # --- STYLING ---
    # Custom CSS for that "Purple Gradient" look
    ui.add_head_html('''
        <style>
            .card-purple { 
                background: linear-gradient(45deg, #6a11cb 0%, #2575fc 100%); 
                color: white; 
            }
            .kpi-title { opacity: 0.8; font-size: 0.9rem; font-weight: 500; }
            .kpi-value { font-size: 2rem; font-weight: bold; }
        </style>
    ''')

    # --- HEADER ---
    with ui.row().classes('w-full items-center justify-between mb-4'):
        ui.label('Education Performance Analysis').classes('text-2xl font-bold text-gray-800')
        
        # Status Label (Updates automatically)
        status_label = ui.label()
        
        ui.button('Reset All Filters', on_click=lambda: reset_filters()).classes('bg-gray-500 text-white')

    # --- KPI ROW ---
    with ui.grid(columns=4).classes('w-full gap-4 mb-6'):
        # We store references to labels to update them later
        with ui.card().classes('card-purple'):
            ui.label('Average Score').classes('kpi-title')
            kpi_avg = ui.label('0.00').classes('kpi-value')
            
        with ui.card().classes('card-purple'):
            ui.label('Weighted Avg').classes('kpi-title')
            kpi_weighted = ui.label('0.00%').classes('kpi-value')
            
        with ui.card():
            ui.label('Pass Rate').classes('text-green-600 font-medium')
            kpi_pass = ui.label('0.00%').classes('text-green-600 text-3xl font-bold')
            
        with ui.card():
            ui.label('Perfect Scores').classes('text-blue-600 font-medium')
            kpi_perfect = ui.label('0.0%').classes('text-blue-600 text-3xl font-bold')

    # --- CHART PLACEHOLDERS ---
    with ui.grid(columns=2).classes('w-full gap-6 mb-6'):
        # Chart 1: Grade
        with ui.card().classes('w-full h-80'):
            ui.label('Grade Distribution').classes('font-bold text-gray-700 mb-2')
            plot_grade = ui.plotly({}).classes('w-full h-full')

        # Chart 2: Level
        with ui.card().classes('w-full h-80'):
            ui.label('Level Distribution').classes('font-bold text-gray-700 mb-2')
            plot_level = ui.plotly({}).classes('w-full h-full')

    # --- ROW 2 Charts ---
    with ui.grid(columns=2).classes('w-full gap-6'):
        
        # Chart 3: Time
        with ui.card().classes('w-full h-96'):
            with ui.row().classes('w-full items-center justify-between'):
                time_title_label = ui.label('Performance Over Time').classes('font-bold text-gray-700')
                # Toggle for View Mode
                view_toggle = ui.toggle(['Quarter', 'Month'], value='Quarter', on_change=lambda: update_dashboard()).props('no-caps')
            
            plot_time = ui.plotly({}).classes('w-full h-full')

        # Chart 4: Subject
        with ui.card().classes('w-full h-96'):
            ui.label('Score by Subject (Click to Filter)').classes('font-bold text-gray-700 mb-2')
            plot_subject = ui.plotly({}).classes('w-full h-full')

    # --- LOGIC & UPDATES ---

    def update_dashboard():
        """Recalculate all data and update widgets."""
        
        # 1. Update Status Text
        status_label.set_text(f"Filters | Grade: {state['grade']} | Level: {state['level']} | Time: {state['time']} | Sub: {state['subject']}")

        # 2. KPIs
        d_kpi = get_data() # Apply all filters
        if d_kpi.empty:
            kpi_avg.set_text("0.00")
            kpi_weighted.set_text("0.00%")
            kpi_pass.set_text("0.00%")
            kpi_perfect.set_text("0.0%")
        else:
            kpi_avg.set_text(f"{d_kpi['Score'].mean():.2f}")
            
            w_sum = d_kpi["Weight"].sum()
            val_w = (d_kpi["WeightedScore"].sum() / w_sum) if w_sum > 0 else 0
            kpi_weighted.set_text(f"{(val_w * 100 if val_w <= 1 else val_w):.2f}%")
            
            kpi_pass.set_text(f"{(len(d_kpi[d_kpi['PassedScore']=='Pass']) / len(d_kpi) * 100):.2f}%")
            
            target = 100 if df["Score"].max() > 1.0 else 1.0
            kpi_perfect.set_text(f"{(len(d_kpi[d_kpi['Score']==target]) / len(d_kpi) * 100):.1f}%")

        # 3. Grade Chart
        d_grade = get_data(ignore_grade=True)
        if not d_grade.empty:
            df_agg = d_grade.groupby('Assessment_Grade', observed=False)['Score'].count().reset_index()
            fig = px.pie(
                df_agg, values='Score', names='Assessment_Grade', hole=0.6,
                color='Assessment_Grade', 
                color_discrete_map={'A': '#2ca02c', 'B': '#1f77b4', 'C': '#ff7f0e', 'D': '#d62728', 'F': '#7f7f7f'}
            )
            if state['grade'] != 'All':
                fig.update_traces(pull=[0.1 if x == state['grade'] else 0 for x in df_agg['Assessment_Grade']])
            
            # Center Text
            fig.add_annotation(text=f"{len(d_kpi):,}<br>Tests", x=0.5, y=0.5, showarrow=False, font_size=16)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
            plot_grade.update_figure(fig)
        else:
            plot_grade.update_figure(go.Figure())

        # 4. Level Chart
        d_level = get_data(ignore_level=True)
        if not d_level.empty:
            df_agg = d_level.groupby('GradeLevel', observed=False)['StudentID'].nunique().reset_index()
            fig = px.pie(df_agg, values='StudentID', names='GradeLevel', hole=0.6, color='GradeLevel')
            if state['level'] != 'All':
                fig.update_traces(pull=[0.1 if x == state['level'] else 0 for x in df_agg['GradeLevel']])
            
            fig.add_annotation(text=f"{d_kpi['StudentID'].nunique():,}<br>Students", x=0.5, y=0.5, showarrow=False, font_size=16)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
            plot_level.update_figure(fig)
        else:
            plot_level.update_figure(go.Figure())

        # 5. Time Chart
        d_time = get_data(ignore_time=True)
        mode = state['view_mode']
        
        # Context Logic
        if mode == "Month":
            if state['time'] != "All" and 'Q' in state['time']:
                d_time = d_time[d_time["YearQuarterConcat"] == state['time']]
            elif state['time'] != "All" and '-' in state['time']:
                parent = df[df["YearMonthConcat"] == state['time']]["YearQuarterConcat"].iloc[0]
                d_time = d_time[d_time["YearQuarterConcat"] == parent]
                
        # Update Title
        if mode == "Month" and 'Q' in state['time']:
             time_title_label.set_text(f"Monthly Breakdown for {state['time']}")
        else:
             time_title_label.set_text("Performance Over Time")

        if not d_time.empty:
            col_group = "YearQuarterConcat" if mode == "Quarter" else "YearMonthConcat"
            df_bar = d_time.groupby(col_group)["Score"].mean().reset_index().sort_values(col_group)
            fig = px.bar(df_bar, x=col_group, y="Score", text_auto='.1f')
            
            opacities = [1.0] * len(df_bar)
            if state['time'] != 'All':
                 # Highlight logic: If drilling down (Q selected, Month view), keep all opaque
                 if not (mode == "Month" and 'Q' in state['time']):
                    opacities = [1.0 if x == state['time'] else 0.3 for x in df_bar[col_group]]

            fig.update_traces(marker=dict(opacity=opacities))
            glob_avg = get_data()['Score'].mean() if not get_data().empty else 0
            fig.add_hline(y=glob_avg, line_dash="dash", line_color="red")
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), xaxis_title=None, yaxis_title="Avg Score")
            plot_time.update_figure(fig)
        else:
            plot_time.update_figure(go.Figure())

        # 6. Subject Chart
        d_sub = get_data(ignore_subject=True)
        if not d_sub.empty:
            df_bar = d_sub.groupby("SubjectName")["Score"].mean().reset_index().sort_values("Score", ascending=False)
            fig = px.bar(df_bar, x="SubjectName", y="Score", text_auto='.1f')
            if state['subject'] != 'All':
                opacities = [1.0 if x == state['subject'] else 0.3 for x in df_bar["SubjectName"]]
                fig.update_traces(marker=dict(opacity=opacities))
            
            glob_avg = get_data()['Score'].mean() if not get_data().empty else 0
            fig.add_hline(y=glob_avg, line_dash="dash", line_color="red")
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), xaxis_title=None, yaxis_title="Avg Score")
            plot_subject.update_figure(fig)
        else:
            plot_subject.update_figure(go.Figure())

    # --- EVENT HANDLERS ---

    def reset_filters():
        state['grade'] = 'All'
        state['level'] = 'All'
        state['time'] = 'All'
        state['subject'] = 'All'
        state['view_mode'] = 'Quarter'
        
        # Update Toggle UI programmatically
        view_toggle.value = 'Quarter'
        update_dashboard()

    def handle_click_grade(e):
        if e.args and 'points' in e.args:
            clicked = e.args['points'][0]['label']
            state['grade'] = 'All' if state['grade'] == clicked else clicked
            update_dashboard()

    def handle_click_level(e):
        if e.args and 'points' in e.args:
            clicked = e.args['points'][0]['label']
            state['level'] = 'All' if state['level'] == clicked else clicked
            update_dashboard()

    def handle_click_time(e):
        if e.args and 'points' in e.args:
            clicked = e.args['points'][0]['x']
            
            # Drill Down
            if state['view_mode'] == 'Quarter':
                state['time'] = clicked
                state['view_mode'] = 'Month'
                # Programmatically update toggle
                view_toggle.value = 'Month'
            else:
                state['time'] = 'All' if state['time'] == clicked else clicked
            
            update_dashboard()

    def handle_click_subject(e):
        if e.args and 'points' in e.args:
            clicked = e.args['points'][0]['x']
            state['subject'] = 'All' if state['subject'] == clicked else clicked
            update_dashboard()

    # Bind Events
    plot_grade.on('plotly_click', handle_click_grade)
    plot_level.on('plotly_click', handle_click_level)
    plot_time.on('plotly_click', handle_click_time)
    plot_subject.on('plotly_click', handle_click_subject)
    
    # Sync view mode changes from toggle
    def on_view_change(e):
        state['view_mode'] = e.value
        update_dashboard()
    
    view_toggle.on_value_change(on_view_change)

    # Initial Draw
    update_dashboard()

ui.run(title="Education Dashboard", port=8080)