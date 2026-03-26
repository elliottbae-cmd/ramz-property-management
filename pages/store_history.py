"""
Store History & Reports — Per-store and per-equipment repair history and spend tracking.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from database.supabase_client import (
    get_current_user, get_stores, get_store_spend_summary,
    get_equipment, get_equipment_history, get_tickets
)
from theme.branding import render_header, PRIMARY
from utils.helpers import format_currency, format_date_short


def render():
    render_header("Store History & Reports", "Repair history and spend tracking")

    user = get_current_user()
    if not user:
        return

    tab_overview, tab_store, tab_equipment = st.tabs(
        ["Overview", "Store Detail", "Equipment History"]
    )

    with tab_overview:
        _render_overview()

    with tab_store:
        _render_store_detail()

    with tab_equipment:
        _render_equipment_detail()


def _render_overview():
    """Render the high-level spend overview across all stores."""
    st.markdown("### Spend Overview")

    data = get_store_spend_summary()
    if not data:
        st.info("No completed tickets with cost data yet.")
        return

    df = pd.DataFrame(data)

    # Extract store info
    df["store_name"] = df["stores"].apply(lambda x: f"{x['store_number']} - {x['name']}" if x else "Unknown")
    df["year"] = pd.to_datetime(df["created_at"]).dt.year
    df["actual_cost"] = pd.to_numeric(df["actual_cost"], errors="coerce").fillna(0)

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Spend (All Time)", format_currency(df["actual_cost"].sum()))
    with col2:
        current_year = datetime.now().year
        year_spend = df[df["year"] == current_year]["actual_cost"].sum()
        st.metric(f"Spend This Year ({current_year})", format_currency(year_spend))
    with col3:
        st.metric("Total Completed Repairs", len(df))

    # Spend by store
    st.markdown("---")
    st.markdown("### Spend by Store")

    store_summary = (
        df.groupby("store_name")["actual_cost"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "Total Spend", "count": "Repairs"})
        .sort_values("Total Spend", ascending=False)
    )
    store_summary["Total Spend"] = store_summary["Total Spend"].apply(lambda x: format_currency(x))
    st.dataframe(store_summary, use_container_width=True)

    # Spend by year
    st.markdown("### Spend by Year")
    year_summary = (
        df.groupby("year")["actual_cost"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "Total Spend", "count": "Repairs"})
        .sort_index(ascending=False)
    )
    year_summary.index = year_summary.index.astype(int)
    year_summary["Total Spend"] = year_summary["Total Spend"].apply(lambda x: format_currency(x))
    st.dataframe(year_summary, use_container_width=True)

    # Chart
    st.markdown("### Spend Trend")
    chart_data = df.groupby("year")["actual_cost"].sum().reset_index()
    chart_data.columns = ["Year", "Spend"]
    st.bar_chart(chart_data.set_index("Year"))

    # Export
    st.markdown("---")
    csv = df[["store_name", "category", "actual_cost", "estimated_cost", "created_at"]].to_csv(index=False)
    st.download_button("Export to CSV", csv, "spend_summary.csv", "text/csv", use_container_width=True)


def _render_store_detail():
    """Render detailed view for a specific store."""
    stores = get_stores(active_only=False)
    if not stores:
        st.info("No stores found.")
        return

    store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
    selected_store = st.selectbox(
        "Select Store",
        list(store_options.keys()),
        format_func=lambda x: store_options[x],
        key="store_detail_select"
    )

    if not selected_store:
        return

    store = next((s for s in stores if s["id"] == selected_store), {})
    st.markdown(f"### {store.get('store_number', '')} - {store.get('name', '')}")
    st.caption(f"{store.get('address', '')} | {store.get('city', '')}, {store.get('state', '')} | Region: {store.get('region', '')}")

    # Get tickets for this store
    tickets = get_tickets({"store_id": selected_store})

    if not tickets:
        st.info("No tickets for this store yet.")
        return

    df = pd.DataFrame(tickets)
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

    # Spend by category
    st.markdown("### Spend by Category")
    cat_summary = (
        completed.groupby("category")["actual_cost"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "Total Spend", "count": "Repairs"})
        .sort_values("Total Spend", ascending=False)
    )
    cat_summary["Total Spend"] = cat_summary["Total Spend"].apply(lambda x: format_currency(x))
    st.dataframe(cat_summary, use_container_width=True)

    # Yearly breakdown
    st.markdown("### Yearly Breakdown")
    yearly = (
        completed.groupby("year")["actual_cost"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "Total Spend", "count": "Repairs"})
        .sort_index(ascending=False)
    )
    yearly.index = yearly.index.astype(int)
    yearly["Total Spend"] = yearly["Total Spend"].apply(lambda x: format_currency(x))
    st.dataframe(yearly, use_container_width=True)

    # Recent tickets
    st.markdown("### Recent Tickets")
    recent = df.head(20)
    display_df = recent[["ticket_number", "category", "urgency", "status", "estimated_cost", "actual_cost", "created_at"]].copy()
    display_df["created_at"] = display_df["created_at"].apply(lambda x: format_date_short(x))
    display_df["estimated_cost"] = display_df["estimated_cost"].apply(format_currency)
    display_df["actual_cost"] = display_df["actual_cost"].apply(format_currency)
    display_df.columns = ["#", "Category", "Urgency", "Status", "Est. Cost", "Actual Cost", "Date"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Export
    csv = df.to_csv(index=False)
    st.download_button(
        "Export Store Data to CSV",
        csv,
        f"store_{store.get('store_number', '')}_history.csv",
        "text/csv",
        use_container_width=True
    )


def _render_equipment_detail():
    """Render equipment repair history."""
    stores = get_stores()
    store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}

    selected_store = st.selectbox(
        "Select Store",
        list(store_options.keys()),
        format_func=lambda x: store_options[x],
        key="equip_store_select"
    )

    if not selected_store:
        return

    equipment = get_equipment(selected_store, active_only=False)
    if not equipment:
        st.info("No equipment registered for this store.")
        return

    equip_options = {e["id"]: f"{e['name']} (SN: {e.get('serial_number', 'N/A')})" for e in equipment}
    selected_equip = st.selectbox(
        "Select Equipment",
        list(equip_options.keys()),
        format_func=lambda x: equip_options[x],
        key="equip_select"
    )

    if not selected_equip:
        return

    equip = next((e for e in equipment if e["id"] == selected_equip), {})
    st.markdown(f"### {equip.get('name', '')}")
    st.caption(
        f"Serial: {equip.get('serial_number', 'N/A')} | "
        f"Category: {equip.get('category', 'N/A')} | "
        f"Installed: {format_date_short(equip.get('install_date', ''))}"
    )

    # Get repair history
    history = get_equipment_history(selected_equip)
    if not history:
        st.info("No repair history for this equipment.")
        return

    df = pd.DataFrame(history)
    df["actual_cost"] = pd.to_numeric(df.get("actual_cost", 0), errors="coerce").fillna(0)

    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Repairs", len(df))
    with col2:
        st.metric("Lifetime Cost", format_currency(df["actual_cost"].sum()))
    with col3:
        if len(df) > 0:
            st.metric("Last Repair", format_date_short(df.iloc[0].get("created_at", "")))

    # Repair timeline
    st.markdown("### Repair History")
    for _, row in df.iterrows():
        cost_str = format_currency(row.get("actual_cost")) if row.get("actual_cost") else "Pending"
        st.markdown(
            f"**{format_date_short(row.get('created_at', ''))}** — "
            f"{row.get('category', '')} | "
            f"Status: {row.get('status', '').replace('_', ' ').title()} | "
            f"Cost: {cost_str}"
        )
        if row.get("description"):
            st.caption(f"  {row['description'][:200]}")

        # Work orders for this ticket
        work_orders = row.get("work_orders", []) or []
        for wo in work_orders:
            contractor = wo.get("contractors", {}) or {}
            st.caption(
                f"  → Work Order: {contractor.get('company_name', 'N/A')} — "
                f"{format_currency(wo.get('amount'))} ({wo.get('status', '').replace('_', ' ').title()})"
            )
        st.markdown("")
