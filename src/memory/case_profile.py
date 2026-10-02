DEFAULT_CASE_PROFILE = {
    "complainant_name": "",
    "incident_type": "",
    "incident_date": "",
    "incident_time": "",
    "incident_location": "",
    "description": "",
    "suspect_name": "",
    "phone_number": "",
    "email": "",
    "imei_number": "",
    "vehicle_number": "",
    "bank_account": "",
    "upi_id": "",
    "amount_lost": "",
}


def create_case_profile():
    return DEFAULT_CASE_PROFILE.copy()


def update_case_profile(
    profile: dict,
    data: dict,
) -> dict:

    for key, value in data.items():

        if key not in profile:
            continue

        if value is None:
            continue

        if isinstance(value, str):
            value = value.strip()

        if value:
            profile[key] = value

    return profile