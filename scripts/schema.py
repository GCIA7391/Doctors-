#!/usr/bin/env python3
"""Canonical enrichment schema shared by batch builder, validator, and writer."""

# Columns of the enriched output workbook, in order.
OUTPUT_COLUMNS = [
    # --- original source data ---
    "Doctor Name", "Department", "Experience", "Hospital", "Address", "City",
    # --- prioritisation (heuristic, public-seniority signals only) ---
    "Priority Rank", "HNI Priority Score",
    # --- professional profiles ---
    "LinkedIn URL", "Official Hospital Profile", "Practo Profile",
    "Apollo247/Directory Profile", "Lybrate Profile", "ResearchGate",
    "Google Scholar", "Personal Website",
    # --- publicly listed contacts (never inferred) ---
    "Professional Email", "Department Email", "Hospital Email",
    "Appointment Number", "Clinic Number", "Secretary Number", "Hospital Number",
    # --- social media (only if unambiguously the doctor's) ---
    "X (Twitter)", "Facebook", "Instagram", "YouTube",
    "Other Professional Profiles",
    # --- verification / HNI enrichment ---
    "Verified Role/Title", "Verified Experience", "Owns Clinic/Practice",
    "HNI Signals",
    # --- audit trail ---
    "Sources", "Confidence Score", "Status", "Notes", "Enriched On",
]

# Keys the enrichment agents must return in each result record.
# Maps JSON key -> output column.
RESULT_KEY_TO_COLUMN = {
    "linkedin": "LinkedIn URL",
    "hospital_profile": "Official Hospital Profile",
    "practo": "Practo Profile",
    "directory_profile": "Apollo247/Directory Profile",
    "lybrate": "Lybrate Profile",
    "researchgate": "ResearchGate",
    "google_scholar": "Google Scholar",
    "personal_website": "Personal Website",
    "professional_email": "Professional Email",
    "department_email": "Department Email",
    "hospital_email": "Hospital Email",
    "appointment_number": "Appointment Number",
    "clinic_number": "Clinic Number",
    "secretary_number": "Secretary Number",
    "hospital_number": "Hospital Number",
    "twitter": "X (Twitter)",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "youtube": "YouTube",
    "other_profiles": "Other Professional Profiles",
    "verified_role": "Verified Role/Title",
    "verified_experience": "Verified Experience",
    "owns_clinic": "Owns Clinic/Practice",
    "hni_signals": "HNI Signals",
    "sources": "Sources",
    "confidence": "Confidence Score",
    "status": "Status",
    "notes": "Notes",
    "enriched_on": "Enriched On",
}

STATUS_ENRICHED = "Enriched"
STATUS_REVIEW = "Needs Human Review"
STATUS_AMBIGUOUS = "Ambiguous Match"
