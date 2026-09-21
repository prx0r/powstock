"""Companies House bulk .dat file parsers.

Based on Global-Witness/uk-companies-house-parsers-public.
Parses fixed-width .dat files for:
- Product 195: Company Appointments (companies + persons)
- Product 195: Disqualified Directors (persons + disqualifications)

These are the bulk datasets available from Companies House on request.
"""

from dataclasses import dataclass, field
from typing import Any


# Record type identifiers
COMPANY_RECORD_TYPE = "1"
PERSON_RECORD_TYPE = "2"
TRAILER_IDENTIFIER = "99999999"
HEADER_IDENTIFIER = "DDDDSNAP"
DISQUAL_HEADER_IDENTIFIER = "DISQUALS"


@dataclass
class CompanyRecord:
    company_number: str
    company_status: str
    number_of_officers: int
    company_name: str


@dataclass
class PersonRecord:
    company_number: str
    person_number: str  # Unique 12-char ID from Companies House
    corporate_indicator: str
    appointment_date: str
    resignation_date: str
    postcode: str
    partial_date_of_birth: str
    full_date_of_birth: str
    title: str
    forenames: str
    surname: str
    honours: str
    care_of: str
    po_box: str
    address_line_1: str
    address_line_2: str
    post_town: str
    county: str
    country: str
    occupation: str
    nationality: str
    res_country: str


@dataclass
class DisqualificationRecord:
    person_number: str
    disqual_start_date: str
    disqual_end_date: str
    section_of_act: str
    disqual_type: str
    disqual_order_date: str
    case_number: str
    company_name: str
    court_name: str


def parse_company_row(row: str) -> CompanyRecord:
    """Parse a company record (type '1') from a fixed-width .dat file."""
    return CompanyRecord(
        company_number=row[0:8].strip(),
        company_status=row[9].strip(),
        number_of_officers=int(row[32:36]) if row[32:36].strip() else 0,
        company_name=row[40:40 + int(row[36:40]) - 1].strip() if row[36:40].strip() else "",
    )


def parse_person_row(row: str) -> PersonRecord:
    """Parse a person record (type '2') from a fixed-width .dat file."""
    variable_data_length = int(row[72:76]) if row[72:76].strip() else 0
    variable_data = row[76:76 + variable_data_length] if variable_data_length > 0 else ""
    parts = variable_data.split("<")

    def get_part(idx: int) -> str:
        return parts[idx].strip() if idx < len(parts) else ""

    return PersonRecord(
        company_number=row[0:8].strip(),
        person_number=row[12:24].strip(),
        corporate_indicator=row[24].strip(),
        appointment_date=row[32:40].strip(),
        resignation_date=row[40:48].strip(),
        postcode=row[48:56].strip(),
        partial_date_of_birth=row[56:64].strip(),
        full_date_of_birth=row[64:72].strip(),
        title=get_part(0),
        forenames=get_part(1),
        surname=get_part(2),
        honours=get_part(3),
        care_of=get_part(4),
        po_box=get_part(5),
        address_line_1=get_part(6),
        address_line_2=get_part(7),
        post_town=get_part(8),
        county=get_part(9),
        country=get_part(10),
        occupation=get_part(11),
        nationality=get_part(12),
        res_country=get_part(13),
    )


def parse_disqualification_row(row: str) -> DisqualificationRecord:
    """Parse a disqualification record (type '2') from a disqualified directors .dat file."""
    return DisqualificationRecord(
        person_number=row[1:13].strip(),
        disqual_start_date=row[13:21].strip(),
        disqual_end_date=row[21:29].strip(),
        section_of_act=row[29:49].strip(),
        disqual_type=row[49:79].strip(),
        disqual_order_date=row[79:87].strip(),
        case_number=row[87:117].strip(),
        company_name=row[117:277].strip(),
        court_name=row[281:].strip() if len(row) > 281 else "",
    )


def parse_appointments_file(file_path: str) -> dict[str, Any]:
    """Parse a Product 195 company appointments .dat file.

    Returns:
        {
            "companies": {company_number: CompanyRecord},
            "persons": {person_number: PersonRecord},
            "company_person_links": [(company_number, person_number)],
        }
    """
    companies = {}
    persons = {}
    links = []
    companies_count = 0
    persons_count = 0

    with open(file_path, "r") as f:
        for row_num, row in enumerate(f):
            row = row.rstrip("\n")

            if row_num == 0:
                # Header
                header_id = row[0:8]
                if header_id != HEADER_IDENTIFIER:
                    print(f"Warning: unexpected header '{header_id}', expected '{HEADER_IDENTIFIER}'")
                continue

            if row[0:8] == TRAILER_IDENTIFIER:
                # Trailer - validate counts
                record_count = int(row[8:16]) if row[8:16].strip() else 0
                total = companies_count + persons_count
                if record_count != total:
                    print(f"Warning: count mismatch - trailer says {record_count}, processed {total}")
                break

            record_type = row[8] if len(row) > 8 else ""

            if record_type == COMPANY_RECORD_TYPE:
                company = parse_company_row(row)
                companies[company.company_number] = company
                companies_count += 1

            elif record_type == PERSON_RECORD_TYPE:
                person = parse_person_row(row)
                persons[person.person_number] = person
                links.append((person.company_number, person.person_number))
                persons_count += 1

    return {
        "companies": companies,
        "persons": persons,
        "company_person_links": links,
        "stats": {
            "companies": companies_count,
            "persons": persons_count,
        },
    }


def parse_disqualifications_file(file_path: str) -> dict[str, Any]:
    """Parse a Product 195 disqualified directors .dat file.

    Returns:
        {
            "persons": {person_number: PersonRecord},
            "disqualifications": {person_number: [DisqualificationRecord]},
        }
    """
    persons = {}
    disqualifications: dict[str, list[DisqualificationRecord]] = {}

    with open(file_path, "r") as f:
        for row in f:
            row = row.rstrip("\n")
            record_type = row[0] if row else ""

            if record_type == "1":
                # Person record
                person_number = row[1:13].strip()
                # Parse name from variable data
                var_len = int(row[29:33]) if row[29:33].strip() else 0
                var_data = row[33:33 + var_len] if var_len > 0 else ""
                parts = var_data.split("<")
                surname = parts[1].strip() if len(parts) > 1 else ""
                forenames = parts[2].strip() if len(parts) > 2 else ""

                persons[person_number] = {
                    "person_number": person_number,
                    "date_of_birth": row[13:21].strip(),
                    "postcode": row[21:29].strip(),
                    "surname": surname,
                    "forenames": forenames,
                }

            elif record_type == "2":
                # Disqualification record
                disqual = parse_disqualification_row(row)
                if disqual.person_number not in disqualifications:
                    disqualifications[disqual.person_number] = []
                disqualifications[disqual.person_number].append(disqual)

    return {
        "persons": persons,
        "disqualifications": disqualifications,
    }


def person_to_dict(person: PersonRecord) -> dict[str, Any]:
    """Convert PersonRecord to dict for storage."""
    return {
        "person_number": person.person_number,
        "company_number": person.company_number,
        "corporate_indicator": person.corporate_indicator,
        "title": person.title,
        "forenames": person.forenames,
        "surname": person.surname,
        "honours": person.honours,
        "full_name": f"{person.title} {person.forenames} {person.surname}".strip(),
        "occupation": person.occupation,
        "nationality": person.nationality,
        "residence_country": person.res_country,
        "country": person.country,
        "postcode": person.postcode,
        "address": ", ".join(filter(None, [
            person.care_of, person.po_box, person.address_line_1,
            person.address_line_2, person.post_town, person.county, person.country,
        ])),
        "appointment_date": person.appointment_date,
        "resignation_date": person.resignation_date,
        "partial_date_of_birth": person.partial_date_of_birth,
        "full_date_of_birth": person.full_date_of_birth,
        "is_active": not person.resignation_date,
    }
