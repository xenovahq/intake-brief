import csv
import os
import re
from datetime import datetime

INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
CSV_FILENAME = "intake_responses.csv"


def read_latest_intake():
    file_path = os.path.join(INPUT_FOLDER, CSV_FILENAME)

    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = list(csv.DictReader(csvfile))

        if not reader:
            raise ValueError("CSV file is empty.")

        return reader[-1]


def safe_get(data, key):
    value = data.get(key, "")
    if value:
        value = value.strip()
    return value if value else "Information not provided."

def read_firm_context():
    context_path = os.path.join("context", "firm_context.txt")

    if not os.path.exists(context_path):
        return "Firm context not available."

    with open(context_path, "r", encoding="utf-8") as f:
        return f.read()

def calculate_completeness(intake_data):
    required_fields = [
        "company_name",
        "industry",
        "project_description",
        "timeline",
        "budget",
        "existing_tools",
        "constraints"
    ]

    missing = []
    vague = []

    for field in required_fields:
        value = intake_data.get(field, "").strip()

        if not value:
            missing.append(field)
        elif field == "timeline" and value.lower() in ["asap", "soon"]:
            vague.append("timeline")

    score = len(required_fields) - len(missing)

    return score, len(required_fields), missing, vague

def determine_next_step(missing, vague):
    if "budget" in missing:
        return "Clarify budget range before discovery session."
    if "timeline" in vague:
        return "Confirm realistic implementation timeline."
    if missing:
        return "Request missing intake details before proceeding."
    return "Schedule structured discovery session."

def generate_markdown(intake_data):
    company_name = safe_get(intake_data, "company_name")
    industry = safe_get(intake_data, "industry")
    project_description = safe_get(intake_data, "project_description")
    timeline = safe_get(intake_data, "timeline")
    budget = safe_get(intake_data, "budget")
    existing_tools = safe_get(intake_data, "existing_tools")
    constraints = safe_get(intake_data, "constraints")

    # NEW: Pull firm context
    firm_context = read_firm_context()

    # NEW: Calculate completeness
    score, total, missing, vague = calculate_completeness(intake_data)

    # NEW: Determine next step
    next_step = determine_next_step(missing, vague)

    markdown_content = f"""# Client Engagement Brief

## Firm Context
{firm_context}

---

## 1. Client Overview
**Company Name:** {company_name}  
**Industry:** {industry}

## 2. Project Summary
{project_description}

## 3. Constraints & Considerations
- **Timeline:** {timeline}
- **Budget:** {budget}
- **Existing Tools:** {existing_tools}
- **Constraints:** {constraints}

## 4. Intake Completeness
Score: {score}/{total}

Missing Fields: {", ".join(missing) if missing else "None"}  
Vague Fields: {", ".join(vague) if vague else "None"}

## 5. Recommended Next Step
{next_step}
"""

    return markdown_content, company_name

def save_output(markdown_content, company_name):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    today = datetime.today().strftime("%Y-%m-%d")
    safe_company = re.sub(r"[^\w\-]", "_", company_name)[:64]
    filename = f"{safe_company}_{today}.md"

    file_path = os.path.join(OUTPUT_FOLDER, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    return file_path


if __name__ == "__main__":
    intake_data = read_latest_intake()
    markdown_content, company_name = generate_markdown(intake_data)
    output_path = save_output(markdown_content, company_name)

    print(f"Brief generated successfully: {output_path}")
