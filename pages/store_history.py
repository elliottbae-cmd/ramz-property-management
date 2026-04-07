"""
Store History & Reports -- Per-store analytics, resolution times, and spend tracking.
Uses new multi-tenant module imports with plotly charts.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from database.supabase_client import get_current_user
from database.tenant import get_effective_client_id
from database.stores import get_stores
from database.reporting import (
    get_store_metrics, get_client_summary,
    get_resolution_times, get_urgency_breakdown,
)
from theme.branding import render_header
from utils.permissions import require_permission, can_view_reports
from utils.helpers import format_currency, format_date_short

try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


def render():
    render_header("Store History & Reports", "Analytics and spend tracking")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_view_reports, "You do not have access to reports.")

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected.")
        return

    tab_overview, tab_store, tab_resolution, tab_urgency = st.tabs(
        ["Overview", "Store Detail", "Resolution Times", "Urgency Breakdown"]
    )

    with tab_overview:
        _render_overview(client_id)

    with tab_store:
        _render_store_detail(client_id)

    with tab_resolution:
        _render_resolution_times(client_id)

    with tab_urgency:
        _render_urgency_breakdown(client_id)


def _render_overview(client_id: str):
    """Render the high-level client summary and metrics."""
    st.markdown("### Client Overview")

    # Date range filter
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=365),
            key="overview_start",
        )
    with col_end:
        end_date = st.date_input("End Date", value=datetime.now(), key="overview_end")

    date_range = (start_date.isoformat(), end_date.isoformat()) if start_date and end_date else None

    # Client summary metrics
    summary = get_client_summary(client_id, date_range)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tickets", summary["total_tickets"])
    with col2:
        st.metric("Open Tickets", summary["open_tickets"])
    with col3:
        st.metric("Total Spend", format_currency(summary["total_spend"]))
    with col4:
        st.metric("Avg Cost/Ticket", format_currency(summary["avg_cost"]))

    # Store-level breakdown
    st.markdown("---")
    st.markdown("### Spend by Store")

    metrics = get_store_metrics(client_id, date_range=date_range)
    if not metrics:
        st.info("No ticket data available for the selected date range.")
        return

    df = pd.DataFrame(metrics)
    df["store_name"] = df["stores"].apply(
        lambda x: f"{x['store_number']} - {x['name']}" if isinstance(x, dict) else "Unknown"
    )
    df["actual_cost"] = pd.to_numeric(df.get("actual_cost", 0), errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["created_at"]).dt.year

    # Store summary table
    store_summary = (
        df.groupby("store_name")["actual_cost"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "Total Spend", "count": "Tickets"})
        .sort_values("Total Spend", ascending=False)
    )
    store_summary["Total Spend"] = store_summary["Total Spend"].apply(format_currency)
    st.dataframe(store_summary, use_container_width=True)

    # Chart: Spend by store
    if HAS_PLOTLY:
        chart_df = (
            df.groupby("store_name")["actual_cost"]
            .sum()
            .reset_index()
            .sort_values("actual_cost", ascending=True)
        )
        fig = px.bar(
            chart_df, x="actual_cost", y="store_name",
            orientation="h",
            labels={"actual_cost": "Total Spend ($)", "store_name": "Store"},
            title="Spend by Store",
        )
        fig.update_layout(height=max(300, len(chart_df) * 35))
        st.plotly_chart(fig, use_container_width=True)
    else:
        # Fallback to Streamlit chart
        chart_data = df.groupby("store_name")["actual_cost"].sum().reset_index()
        chart_data.columns = ["Store", "Spend"]
        st.bar_chart(chart_data.set_index("Store"))

    # Spend by year
    st.markdown("### Spend by Year")
    year_summary = (
        df.groupby("year")["actual_cost"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "Total Spend", "count": "Tickets"})
        .sort_index(ascending=False)
    )
    year_summary.index = year_summary.index.astype(int)
    year_summary["Total Spend"] = year_summary["Total Spend"].apply(format_currency)
    st.dataframe(year_summary, use_container_width=True)

    # Export
    st.markdown("---")
    csv = df[["store_name", "status", "urgency", "actual_cost", "estimated_cost", "created_at"]].to_csv(index=False)
    st.download_button("Export to CSV", csv, "client_spend_summary.csv", "text/csv", use_container_width=True)


def _render_store_detail(client_id: str):
    """Render detailed view for a specific store."""
    stores = get_stores(client_id, active_only=False)
    if not stores:
        st.info("No stores found.")
        return

    store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
    selected_store = st.selectbox(
        "Select Store",
        list(store_options.keys()),
        format_func=lambda x: store_options[x],
        key="store_detail_select",
    )

    if not selected_store:
        return

    store = next((s for s in stores if s["id"] == selected_store), {})
    st.markdown(f"### {store.get('store_number', '')} - {store.get('name', '')}")
    st.caption(
        f"{store.get('address', '')} | "
        f"{store.get('city', '')}, {store.get('state', '')}"
    )

    # Get metrics for this specific store
    metrics = get_store_metrics(client_id, store_id=selected_store)

    if not metrics:
        st.info("No tickets for this store yet.")
        return

    df = pd.DataFrame(metrics)
    df["actual_cost"] = pd.to_numeric(df.get("actual_cost", 0), errors="coerce").fillna(0)
    df["estimated_cost"] = pd.to_numeric(df.get("estimated_cost", 0), errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["created_at"]).dt.year

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tickets", len(df))
    with col2:
        completed = df[df["status"].isin(["completed", "closed"])]
        st.metric("Total Spend", format_currency(completed["actual_cost"].sum()))
    with col3:
        current_year = datetime.now().year
        this_year = completed[completed["year"] == current_year]
        st.metric(f"Spend {current_year}", format_currency(this_year["actual_cost"].sum()))
    with col4:
        open_count = df[~df["status"].isin(["completed", "closed", "rejected"])].shape[0]
        st.metric("Open Tickets", open_count)

    # Spend by urgency for this store
    if HAS_PLOTLY:
        urgency_df = df.groupby("urgency")["actual_cost"].sum().reset_index()
        if not urgency_df.empty:
            fig = px.pie(
                urgency_df, values="actual_cost", names="urgency",
                title="Spend by Urgency Level",
            )
            st.plotly_chart(fig, use_container_width=True)

    # Export
    csv = df.to_csv(index=False)
    st.download_button(
        "Export Store Data to CSV",
        csv,
        f"store_{store.get('store_number', '')}_history.csv",
        "text/csv",
        use_container_width=True,
    )


def _render_resolution_times(client_id: str):
    """Render resolution time analytics."""
    st.markdown("### Resolution Time Analysis")

    data = get_resolution_times(client_id)
    if not data:
        st.info("No completed tickets with resolution data yet.")
        return

    df = pd.DataFrame(data)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["resolved_at"] = pd.to_datetime(df["resolved_at"])
    df["resolution_hours"] = (df["resolved_at"] - df["created_at"]).dt.total_seconds() / 3600
    df["resolution_days"] = df["resolution_hours"] / 24

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Avg Resolution Time", f"{df['resolution_hours'].mean():.1f} hrs")
    with col2:
        st.metric("Median Resolution Time", f"{df['resolution_hours'].median():.1f} hrs")
    with col3:
        st.metric("Resolved Tickets", len(df))

    # By category
    st.markdown("### By Category")
    cat_summary = (
        df.groupby("category")["resolution_hours"]
        .agg(["mean", "median", "count"])
        .rename(columns={"mean": "Avg Hours", "median": "Median Hours", "count": "Count"})
        .sort_values("Avg Hours", ascending=False)
    )
    cat_summary["Avg Hours"] = cat_summary["Avg Hours"].apply(lambda x: f"{x:.1f}")
    cat_summary["Median Hours"] = cat_summary["Median Hours"].apply(lambda x: f"{x:.1f}")
    st.dataframe(cat_summary, use_container_width=True)

    # By urgency
    st.markdown("### By Urgency Level")
    urg_summary = (
        df.groupby("urgency")["resolution_hours"]
        .agg(["mean", "median", "count"])
        .rename(columns={"mean": "Avg Hours", "median": "Median Hours", "count": "Count"})
        .sort_values("Avg Hours")
    )
    urg_summary["Avg Hours"] = urg_summary["Avg Hours"].apply(lambda x: f"{x:.1f}")
    urg_summary["Median Hours"] = urg_summary["Median Hours"].apply(lambda x: f"{x:.1f}")
    st.dataframe(urg_summary, use_container_width=True)

    # Chart
    if HAS_PLOTLY:
        fig = px.histogram(
            df, x="resolution_hours", nbins=20,
            title="Distribution of Resolution Times (Hours)",
            labels={"resolution_hours": "Resolution Time (Hours)", "count": "Tickets"},
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_urgency_breakdown(client_id: str):
    """Render urgency level breakdown."""
    st.markdown("### Urgency Breakdown")

    breakdown = get_urgency_breakdown(client_id)
    if not breakdown:
        st.info("No ticket data available.")
        return

    # Display as metrics
    cols = st.columns(len(breakdown))
    for i, (level, count) in enumerate(breakdown.items()):
        with cols[i]:
            st.metric(level, count)

    # Pie chart
    if HAS_PLOTLY:
        df = pd.DataFrame([
            {"Urgency": k, "Count": v} for k, v in breakdown.items()
        ])
        fig = px.pie(
            df, values="Count", names="Urgency",
            title="Tickets by Urgency Level",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Bar chart
    if HAS_PLOTLY:
        df = pd.DataFrame([
            {"Urgency": k, "Count": v} for k, v in breakdown.items()
        ])
        fig = px.bar(
            df, x="Urgency", y="Count",
            title="Ticket Count by Urgency Level",
        )
        st.plotly_chart(fig, use_container_width=True)
