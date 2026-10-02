class EntityMergeAgent:
    """
    Merges newly extracted entities into the existing FIR form.
    """

    def merge(
        self,
        form: dict,
        entities: dict,
    ) -> dict:

        # -------------------------------------------------
        # 1. Explicit FIR-specific fields
        # -------------------------------------------------

        complainant_name = entities.get(
            "complainant_name"
        )

        if (
            complainant_name
            and not form.get("complainant_name")
        ):
            form["complainant_name"] = complainant_name


        incident_type = entities.get(
            "incident_type"
        )

        if (
            incident_type
            and incident_type != "unknown"
            and not form.get("incident_type")
        ):
            form["incident_type"] = incident_type


        incident_date = entities.get("incident_date")

        # Prefer explicit incident_date
        if incident_date and not form.get("incident_date"):
            form["incident_date"] = incident_date

        # Fallback to extracted dates
        elif (
            not form.get("incident_date")
            and entities.get("dates")
        ):
            form["incident_date"] = entities["dates"][0]

        incident_time = entities.get("incident_time")

        # Prefer explicit incident_time
        if incident_time and not form.get("incident_time"):
            form["incident_time"] = incident_time

        # Fallback to extracted times
        elif (
            not form.get("incident_time")
            and entities.get("times")
        ):
            form["incident_time"] = entities["times"][0]


        incident_location = entities.get(
            "incident_location"
        )

        if (
            incident_location
            and not form.get("incident_location")
        ):
            form["incident_location"] = incident_location


        # -------------------------------------------------
        # 2. Incident description
        # -------------------------------------------------

        incident_description = entities.get(
            "incident_description"
        )

        if incident_description:

            if not form.get("description"):

                form["description"] = (
                    incident_description.strip()
                )

            elif (
                incident_description.lower()
                not in form["description"].lower()
            ):

                form["description"] = (
                    form["description"].strip()
                    + ". "
                    + incident_description.strip()
                )


        # -------------------------------------------------
        # 3. Conversation description
        # -------------------------------------------------

        # Conversation description
        # Only merge description when the extracted description
        # actually represents incident details.

        description = entities.get("description")

        if description:

            if not form.get("description"):

                form["description"] = description.strip()

            elif (
                description.lower()
                not in form["description"].lower()
            ):

                form["description"] = (
                    form["description"].strip()
                    + ". "
                    + description.strip()
                )

        # -------------------------------------------------
        # 4. Other general entities
        # -------------------------------------------------

        mapping = {
            "phone_numbers": "phone_number",
            "emails": "email",
            "upi_ids": "upi_id",
            "bank_accounts": "bank_account",
            "vehicle_numbers": "vehicle_number",
        }

        for entity_key, form_key in mapping.items():

            values = entities.get(entity_key)

            if values and not form.get(form_key):

                form[form_key] = values[0]


        return form