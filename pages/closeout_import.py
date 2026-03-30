"""PSP Closeout Package Importer.

Allows PSP admins to upload a project closeout PDF and auto-populate
the equipment, warranty, and service agent records for a store.
"""

from __future__ import annotations

import tempfile
import os
from datetime import date

import streamlit as st

from database.supabase_client import get_current_user
from database.tenant import get_effective_client_id
from database.stores import get_stores
from database.closeout_parser import (
    extract_pdf_text,
    parse_closeout_with_claude,
    import_to_supabase,
    summarise_parsed,
)
from utils.permissions import can_access_psp_admin, require_permission


def render():
    """Render the Closeout Package Importer page."""
    st.markdown(
        '<div style="background: linear-gradient(135deg, #1a1a2e, #16213e); '
        'color: white; padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 1rem;">'
        '<h1 style="margin:0; font-size:1.5rem; font-weight:700;">📦 Closeout Package Importer</h1>'
        '<p style="margin:0.25rem 0 0 0; font-size:0.85rem; opacity:0.8;">'
        'Upload a PSP project closeout PDF to auto-populate equipment, warranties, and service agents</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    user = get_current_user()
    if not user:
        st.error("Not logged in.")
        return

    require_permission(can_access_psp_admin, "Only PSP users can access the Closeout Importer.")

    client_id = get_effective_client_id()
    if not client_id:
        st.warning("Please select a client first.")
        return

    # ----------------------------------------------------------------
    # Step 1: Select store + upload PDF
    # ----------------------------------------------------------------
    st.markdown("### Step 1 — Select Store & Upload PDF")

    stores = get_stores(client_id)
    if not stores:
        st.warning("No stores found for this client. Add stores first.")
        return

    store_options = {
        f"{s.get('store_number', '?')} — {s.get('name', 'Unknown')} ({s.get('city', '')}, {s.get('state', '')})": s["id"]
        for s in stores
    }

    selected_store_label = st.selectbox("Select Store", options=list(store_options.keys()))
    store_id = store_options[selected_store_label]
    selected_store = next((s for s in stores if s["id"] == store_id), {})

    col_date, col_upload = st.columns([1, 2])
    with col_date:
        opening_date = st.date_input(
            "Store Opening Date",
            value=None,
            help="Used as the warranty start date for all equipment. "
                 "Should match the opening date in the closeout package.",
        )
    with col_upload:
        uploaded_file = st.file_uploader(
            "Upload Closeout PDF",
            type=["pdf"],
            help="Upload the PSP project closeout package PDF for this store.",
        )

    if not uploaded_file:
        st.info("Upload a closeout PDF to continue.")
        _show_what_gets_imported()
        return

    # ----------------------------------------------------------------
    # Step 2: Parse PDF
    # ----------------------------------------------------------------
    parse_key = f"closeout_parsed_{store_id}"
    file_name_key = f"closeout_filename_{store_id}"

    # Re-parse if a new file is uploaded
    if (
        parse_key not in st.session_state
        or st.session_state.get(file_name_key) != uploaded_file.name
    ):
        with st.spinner("📄 Reading PDF and extracting data with AI... (this takes ~15 seconds)"):
            try:
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name

                # Extract text
                pdf_text = extract_pdf_text(tmp_path)
                os.unlink(tmp_path)

                # Parse with Claude
                store_state = selected_store.get("state", "")
                parsed = parse_closeout_with_claude(pdf_text, store_state=store_state)
                st.session_state[parse_key] = parsed
                st.session_state[file_name_key] = uploaded_file.name

            except ImportError:
                st.error(
                    "pdfplumber is not installed. Add `pdfplumber` to requirements.txt "
                    "and redeploy the app."
                )
                return
            except Exception as e:
                st.error(f"Failed to parse PDF: {e}")
                import traceback
                st.code(traceback.format_exc())
                return

    parsed = st.session_state[parse_key]
    summary = summarise_parsed(parsed)

    # ----------------------------------------------------------------
    # Step 3: Preview
    # ----------------------------------------------------------------
    st.markdown("---")
    st.markdown("### Step 2 — Review Extracted Data")

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Equipment Items", summary["total_equipment"])
    with m2:
        st.metric("Serial Numbers", summary["total_serials"])
    with m3:
        st.metric("Service Agents", len(summary["service_agents"]))
    with m4:
        st.metric("Vendor Contacts", summary["vendors"])

    # Store info detected
    store_info = parsed.get("store_info", {})
    if store_info.get("address"):
        cofo_str = f"  |  CofO: {summary['cofo_date']}" if summary.get("cofo_date") else ""
        st.caption(
            f"📍 Detected store: {summary['store_address']}  |  "
            f"Opening: {summary['opening_date'] or 'not found'}"
            f"{cofo_str}  |  "
            f"Health permit: {summary['permit_number'] or 'not found'} "
            f"(expires {summary['permit_expiry'] or 'unknown'})"
        )

    # Equipment preview table
    equipment_list = parsed.get("equipment_list", [])
    if equipment_list:
        with st.expander(f"📋 Equipment List ({len(equipment_list)} items)", expanded=True):
            for i, item in enumerate(equipment_list):
                col_name, col_mfg, col_model, col_serial, col_warranty, col_agent = st.columns(
                    [3, 2, 2, 2, 3, 2]
                )
                with col_name:
                    if i == 0:
                        st.caption("**Equipment**")
                    st.write(item.get("name", "—"))
                with col_mfg:
                    if i == 0:
                        st.caption("**Manufacturer**")
                    st.write(item.get("manufacturer", "—"))
                with col_model:
                    if i == 0:
                        st.caption("**Model**")
                    st.write(item.get("model", "—"))
                with col_serial:
                    if i == 0:
                        st.caption("**Serial(s)**")
                    serials = item.get("serial_numbers", [])
                    st.write(", ".join(serials) if serials else "—")
                with col_warranty:
                    if i == 0:
                        st.caption("**Warranty**")
                    st.write(item.get("warranty_terms", "—"))
                with col_agent:
                    if i == 0:
                        st.caption("**Service Agent**")
                    agent = item.get("service_agent_name", "")
                    if item.get("contact_factory_first"):
                        st.caption("Factory direct")
                    else:
                        st.write(agent or "—")

    # Service agents to be created
    if summary["service_agents"]:
        with st.expander(f"🔧 Service Agents to Import ({len(summary['service_agents'])} companies)"):
            for agent, count in summary["service_agents"].items():
                # Find phone for this agent
                phone = next(
                    (i.get("service_agent_phone", "") for i in equipment_list
                     if i.get("service_agent_name") == agent),
                    ""
                )
                st.write(f"**{agent}** — {phone} ({count} equipment item{'s' if count > 1 else ''})")

    # Categories breakdown
    if summary["categories"]:
        with st.expander("📊 Equipment by Category"):
            for cat, count in sorted(summary["categories"].items(), key=lambda x: -x[1]):
                st.write(f"• {cat}: {count}")

    # ----------------------------------------------------------------
    # Step 4: Dry run option + Import
    # ----------------------------------------------------------------
    st.markdown("---")
    st.markdown("### Step 3 — Import")

    if not opening_date:
        st.warning(
            "⚠️ No opening date set — warranty start dates will default to today. "
            "Go back to Step 1 and enter the opening date for accurate warranty records."
        )

    confirm = st.checkbox(
        f"I confirm this is the correct store: **{selected_store_label}**",
        key=f"closeout_confirm_{store_id}",
    )

    col_dry, col_import = st.columns(2)

    with col_dry:
        if st.button("🔍 Dry Run (preview without saving)", use_container_width=True):
            with st.spinner("Validating..."):
                dry_result = import_to_supabase(
                    parsed=parsed,
                    store_id=store_id,
                    client_id=client_id,
                    user_id=user["id"],
                    opening_date=opening_date,
                    dry_run=True,
                )
            _show_import_result(dry_result, dry_run=True)

    with col_import:
        if st.button(
            "✅ Import to Database",
            type="primary",
            use_container_width=True,
            disabled=not confirm,
        ):
            with st.spinner("Importing equipment, warranties, and service agents..."):
                import_result = import_to_supabase(
                    parsed=parsed,
                    store_id=store_id,
                    client_id=client_id,
                    user_id=user["id"],
                    opening_date=opening_date,
                    dry_run=False,
                )
            _show_import_result(import_result, dry_run=False)

            if not import_result["errors"]:
                if import_result.get("store_updated"):
                    st.info("✅ Store record updated with opening date, CofO date, and health permit details.")
                # Clear parse cache so a fresh PDF can be uploaded
                st.session_state.pop(parse_key, None)
                st.session_state.pop(file_name_key, None)
                st.balloons()


# ------------------------------------------------------------------
# Helper display functions
# ------------------------------------------------------------------

def _show_import_result(result: dict, dry_run: bool):
    prefix = "DRY RUN — " if dry_run else ""
    label = "would be" if dry_run else "were"

    st.markdown(f"#### {prefix}Import Results")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Equipment", result["equipment_created"], help=f"Records {label} created")
    with c2:
        st.metric("Warranties", result["warranties_created"], help=f"Warranty records {label} created")
    with c3:
        st.metric("Contractors Created", result["contractors_created"])
    with c4:
        st.metric("Contractors Updated", result["contractors_updated"])

    if result["skipped"]:
        with st.expander(f"⚠️ Skipped ({len(result['skipped'])})"):
            for name, reason in result["skipped"]:
                st.write(f"• **{name}**: {reason}")

    if result["errors"]:
        with st.expander(f"❌ Errors ({len(result['errors'])})"):
            for err in result["errors"]:
                st.error(err)
    elif not dry_run:
        st.success(
            f"Import complete! {result['equipment_created']} equipment records, "
            f"{result['warranties_created']} warranties, and "
            f"{result['contractors_created']} service agents added."
        )


def _show_what_gets_imported():
    """Show a brief explainer while waiting for PDF upload."""
    st.markdown("---")
    st.markdown("#### What gets imported from a closeout package:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            "**📦 Equipment Records**\n"
            "- Name & description\n"
            "- Manufacturer & model\n"
            "- Serial numbers\n"
            "- Category\n"
            "- Install date"
        )
    with col2:
        st.markdown(
            "**🛡️ Warranty Records**\n"
            "- Parts & labor period\n"
            "- Parts-only period\n"
            "- Compressor warranty\n"
            "- Start & end dates\n"
            "- Manufacturer contact"
        )
    with col3:
        st.markdown(
            "**🔧 Service Agents**\n"
            "- Company name & phone\n"
            "- Trade type\n"
            "- State & city coverage\n"
            "- Added to contractor directory\n"
            "- Auto-matched on future tickets"
        )
