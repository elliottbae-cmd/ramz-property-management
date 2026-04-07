"""
Equipment Inventory -- Track and manage equipment across all locations.
Provides filtering, summary metrics, detail views, and repair history.
"""

import streamlit as st
from datetime import datetime, date

from database.supabase_client import get_current_user, get_client
from database.tenant import get_effective_client_id
from database.stores import get_stores
from database.equipment import (
    get_equipment_for_client,
    get_equipment_with_details,
    get_active_warranties_bulk,
    get_repair_history,
    get_warranties,
    create_equipment,
    update_equipment,
)
from theme.branding import render_header
from utils.permissions import require_permission, can_manage_tickets
from utils.helpers import format_currency, format_date_short


# ------------------------------------------------------------------
# Equipment categories
# ------------------------------------------------------------------
EQUIPMENT_CATEGORIES = [
    "BOH",
    "FOH",
    "HVAC",
    "Roof",
    "Parking Lot",
    "Building Exterior",
    "Lighting",
    "Landscaping",
    "Plumbing",
    "Electrical",
    "Signage",
    "Other",
]


@st.cache_data(ttl=120)
def _batch_ticket_stats(equipment_ids: tuple | list) -> tuple[dict[str, int], dict[str, float]]:
    """Fetch open ticket counts AND total repair costs in a single query.

    Returns (open_counts, repair_costs) — both keyed by equipment_id.
    Replaces two separate Supabase round trips with one.
    """
    if not equipment_ids:
        return {}, {}
    try:
        sb = get_client()
        result = (
            sb.table("tickets")
            .select("equipment_id, actual_cost, status")
            .in_("equipment_id", equipment_ids)
            .execute()
        )
        open_counts: dict[str, int] = {}
        repair_costs: dict[str, float] = {}
        closed_statuses = {"completed", "closed", "rejected"}
        for row in (result.data or []):
            eid = row.get("equipment_id")
            if not eid:
                continue
            status = row.get("status") or ""
            if status not in closed_statuses:
                open_counts[eid] = open_counts.get(eid, 0) + 1
            cost = row.get("actual_cost")
            if cost:
                repair_costs[eid] = repair_costs.get(eid, 0) + float(cost)
        return open_counts, repair_costs
    except Exception:
        return {}, {}


def render():
    render_header("Equipment Inventory", "Track and manage equipment across all locations")

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_manage_tickets, "You do not have access to this page.")

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("No client context selected. Please select a client first.")
        return

    # Load stores
    stores = get_stores(client_id)
    if not stores:
        st.warning("No stores found for this client.")
        return

    # ------------------------------------------------------------------
    # Search bar — prominent, full width at top
    # ------------------------------------------------------------------
    search_text = st.text_input(
        "🔍 Search Equipment",
        placeholder="Search by name, serial number, manufacturer, model, or category...",
        key="eq_search",
    )

    # ------------------------------------------------------------------
    # Filters row
    # ------------------------------------------------------------------
    col_store, col_brand, col_cat, col_warranty = st.columns(4)

    with col_store:
        store_options = {"all": "All Stores"}
        for s in sorted(stores, key=lambda x: x.get("store_number", "")):
            store_options[s["id"]] = f"{s['store_number']} – {s['name']}"
        selected_store = st.selectbox(
            "Store",
            options=list(store_options.keys()),
            format_func=lambda x: store_options[x],
            key="eq_store_filter",
        )

    with col_brand:
        brands = sorted(set(s.get("brand", "") for s in stores if s.get("brand")))
        brand_options = ["All Brands"] + brands
        selected_brand = st.selectbox("Brand", brand_options, key="eq_brand_filter")

    with col_cat:
        cat_options = ["All Categories"] + EQUIPMENT_CATEGORIES
        selected_category = st.selectbox("Category", cat_options, key="eq_cat_filter")

    with col_warranty:
        warranty_filter = st.selectbox(
            "Warranty",
            ["All", "Active Warranty", "No Warranty"],
            key="eq_warranty_filter",
        )

    # ------------------------------------------------------------------
    # Load equipment data
    # ------------------------------------------------------------------
    if selected_store != "all":
        all_equipment = get_equipment_with_details(selected_store)
        store_obj = next((s for s in stores if s["id"] == selected_store), {})
        for item in all_equipment:
            item["stores"] = {
                "id": store_obj.get("id"),
                "store_number": store_obj.get("store_number", ""),
                "name": store_obj.get("name", ""),
                "brand": store_obj.get("brand", ""),
            }
    else:
        all_equipment = get_equipment_for_client(client_id)

    # Bulk-fetch ticket stats (open counts + repair costs) in ONE query
    # and active warranties in ONE query — replaces N+2 round trips with 2.
    # Use tuple so @st.cache_data hashing is fast and deterministic.
    equipment_ids = tuple(item["id"] for item in all_equipment)
    open_counts, repair_costs = _batch_ticket_stats(equipment_ids)
    warranty_map = get_active_warranties_bulk(equipment_ids)
    for item in all_equipment:
        item["open_ticket_count"] = open_counts.get(item["id"], 0)
        item["_total_repair_cost"] = repair_costs.get(item["id"], 0)
        if "active_warranty" not in item:
            item["active_warranty"] = warranty_map.get(item["id"])

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    filtered = all_equipment

    if selected_brand != "All Brands":
        filtered = [
            e for e in filtered
            if (e.get("stores") or {}).get("brand", "") == selected_brand
        ]

    if selected_category != "All Categories":
        filtered = [
            e for e in filtered
            if (e.get("category") or "").upper().startswith(selected_category.upper())
               or (e.get("category") or "") == selected_category
        ]

    if warranty_filter == "Active Warranty":
        filtered = [e for e in filtered if e.get("active_warranty")]
    elif warranty_filter == "No Warranty":
        filtered = [e for e in filtered if not e.get("active_warranty")]

    if search_text:
        q = search_text.lower().strip()
        filtered = [
            e for e in filtered
            if q in (e.get("name") or "").lower()
            or q in (e.get("serial_number") or "").lower()
            or q in (e.get("manufacturer") or "").lower()
            or q in (e.get("model") or "").lower()
            or q in (e.get("category") or "").lower()
            or q in (e.get("notes") or "").lower()
            or q in ((e.get("stores") or {}).get("name", "")).lower()
            or q in ((e.get("stores") or {}).get("store_number", "")).lower()
        ]

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------
    total_count = len(filtered)
    under_warranty = sum(1 for e in filtered if e.get("active_warranty"))
    needs_attention = sum(1 for e in filtered if (e.get("open_ticket_count") or 0) > 0)

    ages = []
    for e in filtered:
        install = e.get("install_date")
        if install:
            try:
                install_dt = datetime.fromisoformat(str(install)).date()
                ages.append((date.today() - install_dt).days / 365.25)
            except Exception:
                pass
    avg_age = sum(ages) / len(ages) if ages else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Equipment", total_count)
    with col2:
        st.metric("Under Warranty", under_warranty)
    with col3:
        st.metric("Needs Attention", needs_attention)
    with col4:
        st.metric("Avg Age", f"{avg_age:.1f} yrs" if ages else "N/A")

    # Show active search/filter notice
    active_filters = []
    if search_text:
        active_filters.append(f'🔍 "{search_text}"')
    if selected_store != "all":
        active_filters.append(store_options[selected_store])
    if selected_brand != "All Brands":
        active_filters.append(selected_brand)
    if selected_category != "All Categories":
        active_filters.append(selected_category)
    if warranty_filter != "All":
        active_filters.append(warranty_filter)
    if active_filters:
        st.caption(f"Showing {total_count} item{'s' if total_count != 1 else ''} — filtered by: {' · '.join(active_filters)}")

    st.markdown("---")

    # ------------------------------------------------------------------
    # Grouped view: by store → by category
    # ------------------------------------------------------------------
    if selected_store != "all":
        _render_store_equipment_view(filtered, selected_store, stores, search_text)
    else:
        _render_all_stores_grouped(filtered, stores, search_text)

    # ------------------------------------------------------------------
    # Add Equipment button
    # ------------------------------------------------------------------
    st.markdown("---")
    _render_add_equipment_form(stores, client_id)


# ------------------------------------------------------------------
# All-stores grouped view: store → category
# ------------------------------------------------------------------

def _render_all_stores_grouped(equipment: list[dict], stores: list[dict], search_text: str = ""):
    """Render equipment grouped first by store, then by category within each store."""
    if not equipment:
        st.info("No equipment found matching your filters.")
        return

    # Build a lookup: store_id → store record
    store_map = {s["id"]: s for s in stores}

    # Group equipment by store_id
    by_store: dict[str, list[dict]] = {}
    for item in equipment:
        store_info = item.get("stores") or {}
        sid = store_info.get("id") or item.get("store_id") or "unknown"
        by_store.setdefault(sid, []).append(item)

    # Sort stores by store_number
    def _store_sort_key(sid):
        s = store_map.get(sid) or {}
        return s.get("store_number", "ZZZ")

    for sid in sorted(by_store.keys(), key=_store_sort_key):
        items = by_store[sid]
        store_rec = store_map.get(sid) or (items[0].get("stores") or {})
        store_num = store_rec.get("store_number", "?")
        store_name = store_rec.get("name", "Unknown")
        brand = store_rec.get("brand", "")

        under_warranty = sum(1 for i in items if i.get("active_warranty"))
        open_tickets_total = sum(i.get("open_ticket_count", 0) for i in items)

        # Store section header
        badge_parts = [f"{len(items)} items"]
        if under_warranty:
            badge_parts.append(f"{under_warranty} under warranty")
        if open_tickets_total:
            badge_parts.append(f"⚠️ {open_tickets_total} open ticket{'s' if open_tickets_total != 1 else ''}")
        badge_text = " · ".join(badge_parts)

        store_label = f"**{store_num} — {store_name}**"
        if brand:
            store_label += f"  ·  {brand}"

        st.markdown(f"### 🏪 {store_num} — {store_name}" + (f" ({brand})" if brand else ""))
        st.caption(badge_text)

        # Group by category within this store
        by_cat: dict[str, list[dict]] = {}
        for item in items:
            cat = item.get("category") or "Uncategorized"
            by_cat.setdefault(cat, []).append(item)

        for cat_name in sorted(by_cat.keys()):
            cat_items = by_cat[cat_name]
            st.markdown(f"#### {cat_name} ({len(cat_items)})")

            for item in cat_items:
                warranty = item.get("active_warranty")
                open_cnt = item.get("open_ticket_count", 0)
                name = item.get("name", "Unknown")
                mfr = item.get("manufacturer") or ""
                serial = item.get("serial_number") or ""
                total_repair_cost = item.get("_total_repair_cost", 0)

                # Highlight search term in label
                label_parts = [f"**{name}**"]
                if mfr:
                    label_parts.append(mfr)
                if serial:
                    label_parts.append(f"S/N: {serial}")
                label = " | ".join(label_parts)

                indicators = []
                if warranty:
                    indicators.append("✅ Warranty")
                if open_cnt > 0:
                    indicators.append(f"⚠️ {open_cnt} open")
                if total_repair_cost > 0:
                    indicators.append(format_currency(total_repair_cost) + " spent")
                indicator_str = "  ·  ".join(indicators)
                if indicator_str:
                    label += f"   —   {indicator_str}"

                with st.expander(label):
                    _render_equipment_detail(item)

        st.markdown("---")


def _render_equipment_detail(item: dict):
    """Render expanded detail view for a single equipment item."""
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Equipment Details**")
        st.write(f"**Name:** {item.get('name', 'N/A')}")
        st.write(f"**Category:** {item.get('category', 'N/A')}")
        st.write(f"**Manufacturer:** {item.get('manufacturer', 'N/A')}")
        st.write(f"**Model:** {item.get('model', 'N/A')}")
        st.write(f"**Serial Number:** {item.get('serial_number', 'N/A')}")
        install = item.get("install_date")
        if install:
            st.write(f"**Install Date:** {format_date_short(str(install))}")
        else:
            st.write("**Install Date:** N/A")
        if item.get("notes"):
            st.write(f"**Notes:** {item['notes']}")

    with col_b:
        st.markdown("**Warranty Information**")
        warranty = item.get("active_warranty")
        if warranty:
            st.markdown(
                '<span style="background-color: #4CAF50; color: white; padding: 2px 10px; '
                'border-radius: 12px; font-size: 0.85rem;">Active Warranty</span>',
                unsafe_allow_html=True,
            )
            st.write(f"**Provider:** {warranty.get('warranty_provider', 'N/A')}")
            st.write(f"**Start:** {format_date_short(str(warranty.get('start_date', '')))}")
            st.write(f"**End:** {format_date_short(str(warranty.get('end_date', '')))}")
            if warranty.get("coverage_description"):
                st.write(f"**Coverage:** {warranty['coverage_description']}")
            if warranty.get("contact_phone"):
                st.write(f"**Phone:** {warranty['contact_phone']}")
            if warranty.get("contact_email"):
                st.write(f"**Email:** {warranty['contact_email']}")
        else:
            # Check for expired warranties
            all_warranties = get_warranties(item["id"])
            if all_warranties:
                st.markdown(
                    '<span style="background-color: #F44336; color: white; padding: 2px 10px; '
                    'border-radius: 12px; font-size: 0.85rem;">Warranty Expired</span>',
                    unsafe_allow_html=True,
                )
                latest = all_warranties[0]
                st.write(f"**Last Provider:** {latest.get('warranty_provider', 'N/A')}")
                st.write(f"**Expired:** {format_date_short(str(latest.get('end_date', '')))}")
            else:
                st.markdown(
                    '<span style="background-color: #9E9E9E; color: white; padding: 2px 10px; '
                    'border-radius: 12px; font-size: 0.85rem;">No Warranty</span>',
                    unsafe_allow_html=True,
                )

    # Repair history
    st.markdown("---")
    st.markdown("**Repair History**")
    repairs = get_repair_history(item["id"])

    if repairs:
        total_spent = sum(
            float(r.get("actual_cost") or 0) for r in repairs
        )
        st.write(f"**Total Repairs:** {len(repairs)} | **Total Spent:** {format_currency(total_spent)}")

        for r in repairs:
            status = r.get("status", "unknown")
            cost = float(r.get("actual_cost") or 0)
            created = format_date_short(str(r.get("created_at", "")))
            desc = (r.get("description") or "")[:100]
            urgency = r.get("urgency", "")
            ticket_num = r.get("ticket_number", "N/A")

            st.markdown(
                f"- **#{ticket_num}** ({created}) -- {status.replace('_', ' ').title()} "
                f"| {urgency} | {format_currency(cost)} -- {desc}"
            )
    else:
        st.info("No repair history for this equipment.")

    # Edit button
    st.markdown("---")
    _render_edit_equipment_form(item)


# ------------------------------------------------------------------
# Store equipment grouped view
# ------------------------------------------------------------------

def _render_store_equipment_view(equipment: list[dict], store_id: str, stores: list[dict], search_text: str = ""):
    """Render equipment grouped by category for a specific store."""
    if not equipment:
        st.info("No equipment found for this store.")
        return

    store = next((s for s in stores if s["id"] == store_id), {})
    st.markdown(f"### Inventory for {store.get('store_number', '')} - {store.get('name', '')}")

    # Pre-fetch ticket stats for all equipment in one query
    eq_ids = tuple(item["id"] for item in equipment)
    _, repair_costs = _batch_ticket_stats(eq_ids)
    for item in equipment:
        item["_total_repair_cost"] = repair_costs.get(item["id"], 0)

    # Group by category
    categories = {}
    for item in equipment:
        cat = item.get("category") or "Uncategorized"
        categories.setdefault(cat, []).append(item)

    for cat_name in sorted(categories.keys()):
        items = categories[cat_name]
        st.markdown(f"#### {cat_name} ({len(items)} items)")

        for item in items:
            warranty = item.get("active_warranty")
            open_tickets = item.get("open_ticket_count", 0)
            name = item.get("name", "Unknown")
            mfr = item.get("manufacturer") or ""
            serial = item.get("serial_number") or ""

            # Use pre-fetched repair cost if available; fall back to query
            total_repair_cost = item.get("_total_repair_cost", 0)

            # Build label
            parts = [f"**{name}**"]
            if mfr:
                parts.append(mfr)
            if serial:
                parts.append(f"S/N: {serial}")
            label = " | ".join(parts)

            # Status indicators
            indicators = []
            if warranty:
                indicators.append("Warranty: Active")
            if open_tickets > 0:
                indicators.append(f"Open Tickets: {open_tickets}")
            if total_repair_cost > 0:
                indicators.append(f"Repair Cost: {format_currency(total_repair_cost)}")
            indicator_text = " | ".join(indicators) if indicators else ""

            with st.expander(f"{label}  {('-- ' + indicator_text) if indicator_text else ''}"):
                _render_equipment_detail(item)

        st.markdown("---")


# ------------------------------------------------------------------
# Add equipment form
# ------------------------------------------------------------------

def _render_add_equipment_form(stores: list[dict], client_id: str):
    """Render a form to manually add equipment to a store."""
    with st.expander("Add New Equipment", expanded=False):
        with st.form("add_equipment_form", clear_on_submit=True):
            st.markdown("### Add Equipment")

            col1, col2 = st.columns(2)

            with col1:
                store_options = {s["id"]: f"{s['store_number']} - {s['name']}" for s in stores}
                add_store_id = st.selectbox(
                    "Store *",
                    options=list(store_options.keys()),
                    format_func=lambda x: store_options[x],
                    key="add_eq_store",
                )
                add_name = st.text_input("Equipment Name *", placeholder="e.g., Walk-in Cooler")
                add_category = st.selectbox("Category *", EQUIPMENT_CATEGORIES, key="add_eq_cat")
                add_manufacturer = st.text_input("Manufacturer", placeholder="e.g., Henny Penny")

            with col2:
                add_model = st.text_input("Model", placeholder="e.g., OFE-322")
                add_serial = st.text_input("Serial Number", placeholder="e.g., ABC-12345")
                add_install_date = st.date_input(
                    "Install Date",
                    value=None,
                    key="add_eq_install",
                )
                add_notes = st.text_area("Notes", placeholder="Any additional details...", height=80)

            submitted = st.form_submit_button("Add Equipment", type="primary", width="stretch")

            if submitted:
                if not add_name or not add_name.strip():
                    st.error("Equipment name is required.")
                    return

                eq_data = {
                    "store_id": add_store_id,
                    "name": add_name.strip(),
                    "category": add_category,
                }
                if add_manufacturer:
                    eq_data["manufacturer"] = add_manufacturer.strip()
                if add_model:
                    eq_data["model"] = add_model.strip()
                if add_serial:
                    eq_data["serial_number"] = add_serial.strip()
                if add_install_date:
                    eq_data["install_date"] = add_install_date.isoformat()
                if add_notes:
                    eq_data["notes"] = add_notes.strip()

                result = create_equipment(eq_data)
                if result:
                    st.success(f"Equipment '{add_name}' added successfully!")
                    # Clear cache to reflect new data
                    get_equipment_for_client.clear()
                    st.rerun()
                else:
                    st.error("Failed to add equipment. Please try again.")


# ------------------------------------------------------------------
# Edit equipment form
# ------------------------------------------------------------------

def _render_edit_equipment_form(item: dict):
    """Render an inline edit form for an equipment item."""
    form_key = f"edit_eq_{item['id']}"

    with st.expander("Edit Equipment Details", expanded=False):
        with st.form(form_key, clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                edit_name = st.text_input("Name", value=item.get("name", ""), key=f"{form_key}_name")
                edit_category = st.selectbox(
                    "Category",
                    EQUIPMENT_CATEGORIES,
                    index=EQUIPMENT_CATEGORIES.index(item.get("category", "Other"))
                    if item.get("category") in EQUIPMENT_CATEGORIES else len(EQUIPMENT_CATEGORIES) - 1,
                    key=f"{form_key}_cat",
                )
                edit_manufacturer = st.text_input(
                    "Manufacturer", value=item.get("manufacturer", ""), key=f"{form_key}_mfr"
                )

            with col2:
                edit_model = st.text_input("Model", value=item.get("model", ""), key=f"{form_key}_model")
                edit_serial = st.text_input(
                    "Serial Number", value=item.get("serial_number", ""), key=f"{form_key}_serial"
                )
                current_install = None
                if item.get("install_date"):
                    try:
                        current_install = datetime.fromisoformat(str(item["install_date"])).date()
                    except Exception:
                        pass
                edit_install = st.date_input(
                    "Install Date", value=current_install, key=f"{form_key}_install"
                )
                edit_notes = st.text_area(
                    "Notes", value=item.get("notes", ""), key=f"{form_key}_notes", height=80
                )

            save = st.form_submit_button("Save Changes", type="primary", width="stretch")

            if save:
                updates = {}
                if edit_name and edit_name != item.get("name"):
                    updates["name"] = edit_name.strip()
                if edit_category != item.get("category"):
                    updates["category"] = edit_category
                if edit_manufacturer != (item.get("manufacturer") or ""):
                    updates["manufacturer"] = edit_manufacturer.strip()
                if edit_model != (item.get("model") or ""):
                    updates["model"] = edit_model.strip()
                if edit_serial != (item.get("serial_number") or ""):
                    updates["serial_number"] = edit_serial.strip()
                if edit_install:
                    updates["install_date"] = edit_install.isoformat()
                if edit_notes != (item.get("notes") or ""):
                    updates["notes"] = edit_notes.strip()

                if updates:
                    result = update_equipment(item["id"], updates)
                    if result:
                        st.success("Equipment updated successfully!")
                        get_equipment_for_client.clear()
                        st.rerun()
                    else:
                        st.error("Failed to update equipment.")
                else:
                    st.info("No changes detected.")
