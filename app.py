import justpy as jp
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- 1. DATA LOADING & PROCESSING ---
# (Standard robust data loading)

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


# --- 2. JUSTPY APPLICATION ---

async def education_dashboard():
    # Setup Page with Tailwind support
    wp = jp.QuasarPage(tailwind=True)
    wp.title = "Education Dashboard"
    wp.head_html = """
    <style>
        .card-purple { background: linear-gradient(45deg, #6a11cb 0%, #2575fc 100%); color: white; }
    </style>
    """

    # --- STATE MANAGEMENT ---
    # We attach state to the webpage object (wp) to keep it session-specific
    wp.state = {
        'grade': 'All',
        'level': 'All',
        'time': 'All',
        'subject': 'All',
        'view_mode': 'Quarter'
    }

    # --- HELPER FUNCTIONS ---
    def get_data(ignore_grade=False, ignore_level=False, ignore_time=False, ignore_subject=False):
        d = df.copy()
        s = wp.state
        if not ignore_grade and s['grade'] != 'All': d = d[d["Assessment_Grade"] == s['grade']]
        if not ignore_level and s['level'] != 'All': d = d[d["GradeLevel"] == s['level']]
        if not ignore_subject and s['subject'] != 'All': d = d[d["SubjectName"] == s['subject']]
        
        # Time Filter
        curr_time = s['time']
        if not ignore_time and curr_time != 'All':
            if 'Q' in curr_time: d = d[d["YearQuarterConcat"] == curr_time]
            else: d = d[d["YearMonthConcat"] == curr_time]
        return d

    # --- LAYOUT CONSTRUCTION ---
    
    main_div = jp.Div(classes="p-8 bg-gray-50 min-h-screen", a=wp)
    
    # 1. Header
    header = jp.Div(classes="flex justify-between items-center mb-6", a=main_div)
    jp.Div(text="Education Performance Analysis", classes="text-3xl font-bold text-gray-800", a=header)
    
    status_text = jp.Div(text="Filters Active", classes="text-blue-600 font-bold", a=header)
    
    async def reset_click(self, msg):
        wp.state = {'grade': 'All', 'level': 'All', 'time': 'All', 'subject': 'All', 'view_mode': 'Quarter'}
        await update_dashboard()
    
    jp.Button(text="Reset All Filters", classes="bg-gray-600 text-white px-4 py-2 rounded shadow hover:bg-gray-700 transition", click=reset_click, a=header)

    # 2. KPIs
    kpi_grid = jp.Div(classes="grid grid-cols-4 gap-6 mb-6", a=main_div)
    
    def create_kpi(title, start_val, is_purple=False, text_color="text-gray-800"):
        classes = "card-purple" if is_purple else "bg-white"
        card = jp.Div(classes=f"rounded-lg shadow p-6 {classes}", a=kpi_grid)
        jp.Div(text=title, classes=f"text-sm font-medium {'text-white opacity-80' if is_purple else 'text-gray-500'}", a=card)
        val_div = jp.Div(text=start_val, classes=f"text-3xl font-bold {'text-white' if is_purple else text_color}", a=card)
        return val_div

    kpi_avg = create_kpi("Average Score", "0.00", is_purple=True)
    kpi_weight = create_kpi("Weighted Avg", "0.00%", is_purple=True)
    kpi_pass = create_kpi("Pass Rate", "0.00%", text_color="text-green-600")
    kpi_perfect = create_kpi("Perfect Scores", "0.0%", text_color="text-blue-600")

    # 3. Charts Area
    chart_grid_1 = jp.Div(classes="grid grid-cols-2 gap-6 mb-6", a=main_div)
    
    # Chart Containers
    def create_chart_card(title, parent):
        card = jp.Div(classes="bg-white rounded-lg shadow p-4 h-96 flex flex-col", a=parent)
        header_row = jp.Div(classes="flex justify-between items-center mb-2", a=card)
        title_div = jp.Div(text=title, classes="font-bold text-gray-700", a=header_row)
        chart_div = jp.PlotlyChart(a=card, classes="w-full flex-grow", style="height: 100%")
        return chart_div, title_div, header_row

    chart_grade, _, _ = create_chart_card("Grade Distribution", chart_grid_1)
    chart_level, _, _ = create_chart_card("Level Distribution", chart_grid_1)

    chart_grid_2 = jp.Div(classes="grid grid-cols-2 gap-6", a=main_div)
    
    chart_time, title_time, header_time = create_chart_card("Performance Over Time", chart_grid_2)
    
    # View Toggle (Simple Buttons for JustPy)
    toggle_div = jp.Div(classes="flex space-x-2", a=header_time)
    btn_q = jp.Button(text="Quarter", classes="px-2 py-1 text-xs border rounded bg-blue-600 text-white", a=toggle_div)
    btn_m = jp.Button(text="Month", classes="px-2 py-1 text-xs border rounded bg-white text-gray-700", a=toggle_div)

    async def toggle_view(self, msg):
        mode = self.text
        wp.state['view_mode'] = mode
        
        # UI Update for buttons
        if mode == "Quarter":
            btn_q.set_classes("bg-blue-600 text-white")
            btn_q.remove_class("bg-white text-gray-700")
            btn_m.set_classes("bg-white text-gray-700")
            btn_m.remove_class("bg-blue-600 text-white")
        else:
            btn_m.set_classes("bg-blue-600 text-white")
            btn_m.remove_class("bg-white text-gray-700")
            btn_q.set_classes("bg-white text-gray-700")
            btn_q.remove_class("bg-blue-600 text-white")
        
        await update_dashboard()

    btn_q.on('click', toggle_view)
    btn_m.on('click', toggle_view)

    chart_subject, _, _ = create_chart_card("Score by Subject", chart_grid_2)

    # --- CALLBACKS & UPDATE LOGIC ---

    async def update_dashboard():
        s = wp.state
        
        # 1. Update Status
        status_text.text = f"Filters | Grade: {s['grade']} | Level: {s['level']} | Time: {s['time']} | Sub: {s['subject']}"

        # 2. KPIs
        d_kpi = get_data()
        if d_kpi.empty:
            kpi_avg.text, kpi_weight.text, kpi_pass.text, kpi_perfect.text = "0.00", "0.00%", "0.00%", "0%"
        else:
            kpi_avg.text = f"{d_kpi['Score'].mean():.2f}"
            w_sum = d_kpi["Weight"].sum()
            val_w = (d_kpi["WeightedScore"].sum() / w_sum) if w_sum > 0 else 0
            kpi_weight.text = f"{(val_w * 100 if val_w <= 1 else val_w):.2f}%"
            kpi_pass.text = f"{(len(d_kpi[d_kpi['PassedScore']=='Pass']) / len(d_kpi) * 100):.2f}%"
            target = 100 if df["Score"].max() > 1.0 else 1.0
            kpi_perfect.text = f"{(len(d_kpi[d_kpi['Score']==target]) / len(d_kpi) * 100):.1f}%"

        # 3. Grade Chart
        d_g = get_data(ignore_grade=True)
        if not d_g.empty:
            df_agg = d_g.groupby('Assessment_Grade', observed=False)['Score'].count().reset_index()
            fig = px.pie(df_agg, values='Score', names='Assessment_Grade', hole=0.6,
                color='Assessment_Grade', color_discrete_map={'A': '#2ca02c', 'B': '#1f77b4', 'C': '#ff7f0e', 'D': '#d62728', 'F': '#7f7f7f'})
            if s['grade'] != 'All':
                fig.update_traces(pull=[0.1 if x == s['grade'] else 0 for x in df_agg['Assessment_Grade']])
            fig.add_annotation(text=f"{len(d_kpi):,}<br>Tests", x=0.5, y=0.5, showarrow=False, font_size=16)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
            chart_grade.figure = fig
        else: chart_grade.figure = go.Figure()

        # 4. Level Chart
        d_l = get_data(ignore_level=True)
        if not d_l.empty:
            df_agg = d_l.groupby('GradeLevel', observed=False)['StudentID'].nunique().reset_index()
            fig = px.pie(df_agg, values='StudentID', names='GradeLevel', hole=0.6, color='GradeLevel')
            if s['level'] != 'All':
                fig.update_traces(pull=[0.1 if x == s['level'] else 0 for x in df_agg['GradeLevel']])
            fig.add_annotation(text=f"{d_kpi['StudentID'].nunique():,}<br>Students", x=0.5, y=0.5, showarrow=False, font_size=16)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
            chart_level.figure = fig
        else: chart_level.figure = go.Figure()

        # 5. Time Chart
        d_t = get_data(ignore_time=True)
        mode = s['view_mode']
        
        # Context
        if mode == "Month":
            if s['time'] != "All" and 'Q' in s['time']:
                d_t = d_t[d_t["YearQuarterConcat"] == s['time']]
            elif s['time'] != "All" and '-' in s['time']:
                matches = df[df["YearMonthConcat"] == s['time']]
                if not matches.empty:
                    parent = matches["YearQuarterConcat"].iloc[0]
                    d_t = d_t[d_t["YearQuarterConcat"] == parent]

        title_time.text = f"Monthly Breakdown for {s['time']}" if (mode == "Month" and 'Q' in s['time']) else "Performance Over Time"

        if not d_t.empty:
            col = "YearQuarterConcat" if mode == "Quarter" else "YearMonthConcat"
            df_bar = d_t.groupby(col)["Score"].mean().reset_index().sort_values(col)
            fig = px.bar(df_bar, x=col, y="Score", text_auto='.1f')
            
            # Force categorical to avoid date parse issues
            fig.update_xaxes(type='category')
            
            opacities = [1.0] * len(df_bar)
            if s['time'] != 'All':
                if not (mode == "Month" and 'Q' in s['time']):
                    opacities = [1.0 if x == s['time'] else 0.3 for x in df_bar[col]]
            
            fig.update_traces(marker=dict(opacity=opacities))
            glob_avg = get_data()['Score'].mean() if not get_data().empty else 0
            fig.add_hline(y=glob_avg, line_dash="dash", line_color="red")
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), xaxis_title=None, yaxis_title="Avg Score")
            chart_time.figure = fig
        else: chart_time.figure = go.Figure()

        # 6. Subject Chart
        d_s = get_data(ignore_subject=True)
        if not d_s.empty:
            df_bar = d_s.groupby("SubjectName")["Score"].mean().reset_index().sort_values("Score", ascending=False)
            fig = px.bar(df_bar, x="SubjectName", y="Score", text_auto='.1f')
            if s['subject'] != 'All':
                opacities = [1.0 if x == s['subject'] else 0.3 for x in df_bar["SubjectName"]]
                fig.update_traces(marker=dict(opacity=opacities))
            glob_avg = get_data()['Score'].mean() if not get_data().empty else 0
            fig.add_hline(y=glob_avg, line_dash="dash", line_color="red")
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), xaxis_title=None, yaxis_title="Avg Score")
            chart_subject.figure = fig
        else: chart_subject.figure = go.Figure()

        # IMPORTANT: In JustPy, after modifying components, we must ask the page to update
        await wp.update()

    # --- CLICK EVENT HANDLERS ---
    
    async def grade_click(self, msg):
        if msg.points:
            clicked = msg.points[0]['label']
            wp.state['grade'] = 'All' if wp.state['grade'] == clicked else clicked
            await update_dashboard()
            
    async def level_click(self, msg):
        if msg.points:
            clicked = msg.points[0]['label']
            wp.state['level'] = 'All' if wp.state['level'] == clicked else clicked
            await update_dashboard()

    async def subject_click(self, msg):
        if msg.points:
            clicked = msg.points[0]['x']
            wp.state['subject'] = 'All' if wp.state['subject'] == clicked else clicked
            await update_dashboard()

    async def time_click(self, msg):
        if msg.points:
            clicked = msg.points[0]['x']
            
            # Drill Down
            if wp.state['view_mode'] == 'Quarter':
                wp.state['time'] = clicked
                # We need to manually trigger the view toggle UI update here
                btn_m.text # Access button from closure
                # Simulate a click on Month button
                await toggle_view(btn_m, None)
            else:
                wp.state['time'] = 'All' if wp.state['time'] == clicked else clicked
            
            await update_dashboard()

    chart_grade.on('plotly_click', grade_click)
    chart_level.on('plotly_click', level_click)
    chart_time.on('plotly_click', time_click)
    chart_subject.on('plotly_click', subject_click)

    # Init
    await update_dashboard()
    return wp

# Run the app
jp.justpy(education_dashboard)