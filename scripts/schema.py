#!/usr/bin/env python3
"""Canonical enrichment schema shared by batch builder, validator, and writer.

Column order: the 26 columns requested for the Doctor Contact Enrichment Engine
come first, in the requested order. The original source columns and the
prospecting/HNI enrichment earned in earlier runs are appended after them, so
nothing already collected is lost.
"""

# --- the 26 requested enrichment columns, in the requested order -------------
REQUESTED_COLUMNS = [
    "Doctor Name",
    "Specialization",
    "Hospital",
    "Department",
    "City",
    "Country",
    "Professional Email",
    "Professional Phone",
    "Appointment Link",
    "Hospital Profile URL",
    "Clinic URL",
    "LinkedIn URL",
    "Google Scholar",
    "ResearchGate",
    "ORCID",
    "Professional X",
    "Professional Instagram",
    "Professional Facebook",
    "Professional YouTube",
    "Professional Website",
    "Indirect Contact Method",
    "Indirect Contact Details",
    "Best Way To Reach",
    "Confidence Score",
    "Sources Used",
    "Notes",
]

# --- original source data + audit + prior prospecting enrichment -------------
APPENDED_COLUMNS = [
    # original rows preserved
    "Experience", "Address", "Experience Discrepancy", "Affiliation Flag",
    # audit trail
    "Verification Method", "Status", "Enriched On",
    # prioritisation (heuristic, public-seniority signals only)
    "Priority Rank", "HNI Priority Score",
    # verified professional standing (public statements only)
    "Verified Role/Title", "Verified Experience", "Owns Clinic/Practice",
    "HNI Signals",
    # additional directory profiles that are not one of the 26 above
    "Practo Profile", "Apollo247/Directory Profile", "Lybrate Profile",
    "Other Professional Profiles",
]

OUTPUT_COLUMNS = REQUESTED_COLUMNS + APPENDED_COLUMNS

# Keys the enrichment agents return in each result record -> output column.
# Legacy keys are retained so result files written by earlier runs still merge.
RESULT_KEY_TO_COLUMN = {
    # --- identity / classification ---
    "specialization": "Specialization",
    "country": "Country",
    # --- tier 1: direct contact ---
    "professional_email": "Professional Email",
    "professional_phone": "Professional Phone",
    "appointment_link": "Appointment Link",
    # --- tier 2: official / professional presence ---
    "hospital_profile": "Hospital Profile URL",
    "clinic_url": "Clinic URL",
    "linkedin": "LinkedIn URL",
    "google_scholar": "Google Scholar",
    "researchgate": "ResearchGate",
    "orcid": "ORCID",
    # --- tier 3: professional social media ---
    "twitter": "Professional X",
    "instagram": "Professional Instagram",
    "facebook": "Professional Facebook",
    "youtube": "Professional YouTube",
    "personal_website": "Professional Website",
    # --- indirect route (always populated) ---
    "indirect_method": "Indirect Contact Method",
    "indirect_details": "Indirect Contact Details",
    "best_way": "Best Way To Reach",
    # --- audit ---
    "confidence_band": "Confidence Score",
    "sources": "Sources Used",
    "notes": "Notes",
    "verification_method": "Verification Method",
    "experience_discrepancy": "Experience Discrepancy",
    "affiliation_flag": "Affiliation Flag",
    "status": "Status",
    "enriched_on": "Enriched On",
    # --- prior prospecting enrichment (kept) ---
    "verified_role": "Verified Role/Title",
    "verified_experience": "Verified Experience",
    "owns_clinic": "Owns Clinic/Practice",
    "hni_signals": "HNI Signals",
    "practo": "Practo Profile",
    "directory_profile": "Apollo247/Directory Profile",
    "lybrate": "Lybrate Profile",
    "other_profiles": "Other Professional Profiles",
}

# --- status vocabulary -------------------------------------------------------
STATUS_ENRICHED = "Enriched"
STATUS_REVIEW = "Needs Human Review"
STATUS_AMBIGUOUS = "Ambiguous Match"
STATUS_BASELINE = "Baseline (not yet researched)"

VALID_STATUS = {STATUS_ENRICHED, STATUS_REVIEW, STATUS_AMBIGUOUS}

# --- confidence bands -------------------------------------------------------
# High    verified by multiple independent official sources
# Medium  strong evidence but only one official source
# Low     partial match only
# Unknown unable to confidently verify
CONF_HIGH, CONF_MEDIUM, CONF_LOW, CONF_UNKNOWN = "High", "Medium", "Low", "Unknown"
VALID_CONFIDENCE = {CONF_HIGH, CONF_MEDIUM, CONF_LOW, CONF_UNKNOWN}

# --- verification methods ---------------------------------------------------
# Page-verified   the profile page itself was retrieved and matched (earlier runs)
# Search-verified identity and URLs confirmed from search-index results only
VERIFY_PAGE = "Page-verified"
VERIFY_SEARCH = "Search-verified"
VERIFY_NONE = "Not verified"

# Fields that must never be populated without a corroborating source URL.
URL_FIELDS = [
    "linkedin", "hospital_profile", "practo", "directory_profile", "lybrate",
    "researchgate", "google_scholar", "personal_website", "clinic_url",
    "appointment_link", "orcid", "twitter", "facebook", "instagram", "youtube",
]
CONTACT_FIELDS = [
    "professional_email", "professional_phone", "department_email",
    "hospital_email", "appointment_number", "clinic_number",
    "secretary_number", "hospital_number",
]
