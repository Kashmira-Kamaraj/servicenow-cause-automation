import streamlit as st
import pandas as pd

# --------------------------------------------------
# Helper: validate cause format
# --------------------------------------------------
def is_valid_cause(cause_text, service_offerings, canonical_categories):
    if pd.isna(cause_text) or str(cause_text).strip() == "":
        return False

    parts = [p.strip() for p in str(cause_text).split(" - ")]
    if len(parts) != 3:
        return False

    service, category, rca = parts
    if service not in service_offerings:
        return False
    if category not in canonical_categories:
        return False
    if rca == "":
        return False

    return True


# --------------------------------------------------
# Simulated AI (Copilot) fallback
# --------------------------------------------------
def ai_fallback_suggest(text_blob, canonical_categories):
    if "resolved" in text_blob or "fixed" in text_blob:
        return "Configuration issue", "Resolved after configuration check"

    if "working" in text_blob or "no issue" in text_blob:
        return "Configuration issue", "No fault found"

    return canonical_categories[0], "Root cause under investigation"


# --------------------------------------------------
# CORE LOGIC (USED BY SINGLE + BULK MODE)
# --------------------------------------------------
def process_ticket(ticket_row, rca_list, service_offerings, canonical_categories):

    service_offering = ticket_row["service_offering"]
    existing_cause = ticket_row["existing_cause"]

    # Skip tickets that already have valid causes
    if is_valid_cause(existing_cause, service_offerings, canonical_categories):
        return None, None, "Skipped (already valid)"

    text_blob = (
        str(ticket_row["short_description"]) + " " +
        str(ticket_row["description"]) + " " +
        str(ticket_row["work_notes"])
    ).lower()

    # Rule-based category
    if any(w in text_blob for w in ["login", "access", "unauthorized"]):
        category = "Access issue"
    elif any(w in text_blob for w in ["offline", "down", "not reachable"]):
        category = "Offline issue"
    elif any(w in text_blob for w in ["timeout", "network", "connectivity"]):
        category = "Connectivity issue"
    elif any(w in text_blob for w in ["screen", "display", "black"]):
        category = "Display issue"
    else:
        category = "Configuration issue"

    matched_rca = "Under analysis"
    confidence = 50
    reason = "Rule-based default"

    # Match existing RCA
    for rca in rca_list:
        if rca.lower() in text_blob:
            matched_rca = rca
            confidence = 90
            reason = f"Matched existing RCA: {rca}"
            break

    # Create new RCA if needed
    if matched_rca == "Under analysis":
        new_rca = str(ticket_row["work_notes"]).strip()
        if new_rca == "" or new_rca.lower() == "nan":
            new_rca = "Root cause under investigation"
        matched_rca = new_rca[:50]
        confidence = 60
        reason = "New RCA created from work notes"

    # AI fallback
    if confidence < 75:
        ai_category, ai_rca = ai_fallback_suggest(text_blob, canonical_categories)
        category = ai_category
        matched_rca = ai_rca
        confidence = 70
        reason = "AI fallback used"

    cause = f"{service_offering} - {category} - {matched_rca}"

    return cause, confidence, reason


# --------------------------------------------------
# Streamlit UI
# --------------------------------------------------
st.set_page_config(page_title="ServiceNow Cause Automation", layout="wide")
st.title("ServiceNow Cause Automation")

# --------------------------------------------------
# Load data
# --------------------------------------------------
tickets_df = pd.read_excel("../data/tickets.xlsx")

rca_df = pd.read_excel("../data/List3_RCA_Phrases.xlsx")
rca_list = rca_df.iloc[:, 0].dropna().tolist()

service_offerings = pd.read_excel(
    "../data/List1_Service_Offerings.xlsx", header=None
)[0].dropna().tolist()

cause_cat_df = pd.read_excel("../data/List2_Cause_Categories.xlsx")
canonical_categories = cause_cat_df.iloc[:, -1].dropna().tolist()

# --------------------------------------------------
# Show tickets
# --------------------------------------------------
st.subheader("Tickets")
st.dataframe(tickets_df)

# --------------------------------------------------
# SINGLE TICKET MODE
# --------------------------------------------------
ticket_numbers = tickets_df["ticket_number"].tolist()
selected_ticket = st.selectbox("Select a ticket (Single Mode)", ticket_numbers)

ticket_data = tickets_df[tickets_df["ticket_number"] == selected_ticket].iloc[0]

if st.button("Generate / Correct Cause (Single Ticket)"):
    cause, confidence, reason = process_ticket(
        ticket_data,
        rca_list,
        service_offerings,
        canonical_categories
    )

    if cause:
        tickets_df.loc[
            tickets_df["ticket_number"] == selected_ticket,
            "existing_cause"
        ] = cause
        tickets_df.to_excel("../data/tickets.xlsx", index=False)

        st.success("Cause updated successfully")
        st.code(cause)
        st.info(f"Confidence: {confidence}%")
        st.write(f"Reason: {reason}")
    else:
        st.info(reason)

# --------------------------------------------------
# BULK MODE
# --------------------------------------------------
st.divider()
st.subheader("Bulk Processing")

if st.button("Process All Eligible Tickets"):
    processed = 0
    skipped = 0
    ai_used = 0

    for idx, row in tickets_df.iterrows():
        cause, confidence, reason = process_ticket(
            row,
            rca_list,
            service_offerings,
            canonical_categories
        )

        if cause:
            tickets_df.at[idx, "existing_cause"] = cause
            processed += 1

            if "AI fallback" in reason:
                ai_used += 1
        else:
            skipped += 1

    tickets_df.to_excel("../data/tickets.xlsx", index=False)

    st.success("Bulk processing completed")
    st.write(f"Tickets processed: {processed}")
    st.write(f"Tickets skipped: {skipped}")
    st.write(f"Tickets using AI fallback: {ai_used}")
