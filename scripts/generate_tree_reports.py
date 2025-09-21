#!/usr/bin/env python3
"""Generate tree risk assessment summaries and export them to Google Docs/PDF.

This script fetches tree records from an Airtable base, summarises each record with
OpenAI's Chat Completions API, appends the summaries to a Google Doc template, and
exports the result as a PDF document. Configuration is controlled via environment
variables (see ``README.md`` for details).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


@dataclass(frozen=True)
class TreeRecord:
    """Simple representation of a tree record stored in Airtable."""

    record_id: str
    species: str
    dbh: str
    height: str
    condition: str
    risk_rating: str

    @classmethod
    def from_airtable(cls, record: dict) -> "TreeRecord":
        """Create a :class:`TreeRecord` instance from an Airtable API response."""

        fields = record.get("fields", {})
        return cls(
            record_id=record.get("id", ""),
            species=_stringify_field(fields.get("Species", "Unknown")),
            dbh=_stringify_field(fields.get("DBH", "N/A")),
            height=_stringify_field(fields.get("Height", "N/A")),
            condition=_stringify_field(fields.get("Health Condition", "N/A")),
            risk_rating=_stringify_field(fields.get("Risk Rating", "N/A")),
        )


def _stringify_field(value: object) -> str:
    """Return a string representation of a field value."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def get_required_env(name: str) -> str:
    """Return a required environment variable or raise ``KeyError``."""

    value = os.getenv(name)
    if not value:
        raise KeyError(name)
    return value


def ensure_output_directory(path: Path) -> Path:
    """Ensure that an output directory exists and return it."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def fetch_airtable_records(api_key: str, base_id: str, table_name: str) -> List[TreeRecord]:
    """Fetch and normalise tree records from Airtable."""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    params: dict[str, str] = {}
    records: List[TreeRecord] = []

    while True:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        for record in payload.get("records", []):
            records.append(TreeRecord.from_airtable(record))

        offset = payload.get("offset")
        if not offset:
            break
        params["offset"] = offset

    return records


def build_prompt(record: TreeRecord) -> str:
    """Build the prompt used to generate a risk assessment summary."""

    return (
        "You are a consulting arborist. Write a Tree Risk Assessment summary:\n\n"
        f"Species: {record.species}\n"
        f"DBH: {record.dbh}\n"
        f"Height: {record.height}\n"
        f"Condition: {record.condition}\n"
        f"Risk Rating: {record.risk_rating}\n\n"
        "Requirements:\n"
        "- Professional tone\n"
        "- 2 short paragraphs\n"
        "- Clear risk statement + management recommendation\n"
    )


def generate_summaries(
    client: OpenAI,
    records: Iterable[TreeRecord],
    *,
    model: str,
    max_tokens: int,
) -> List[str]:
    """Generate a summary for each tree record using OpenAI."""

    summaries: List[str] = []
    for record in records:
        prompt = build_prompt(record)
        logging.info("Generating summary for record %s (%s)", record.record_id, record.species)

        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )

        try:
            content = completion.choices[0].message.content or ""
        except (IndexError, AttributeError):
            content = ""

        content = content.strip()
        if not content:
            logging.warning(
                "OpenAI returned an empty response for record %s; skipping.",
                record.record_id or record.species,
            )
            continue

        summaries.append(content)

    return summaries


def insert_summaries_into_doc(docs_service, doc_id: str, summaries: Iterable[str]) -> None:
    """Insert the generated summaries into the Google Doc template."""

    summaries_list = list(summaries)
    if not summaries_list:
        logging.warning("No summaries to insert into the document.")
        return

    text_to_insert = "\n\n".join(summaries_list).strip() + "\n\n"
    requests_body = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": text_to_insert,
            }
        }
    ]

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests_body},
    ).execute()


def export_doc_to_pdf(drive_service, doc_id: str, output_path: Path) -> Path:
    """Export the Google Doc to a PDF file and return the resulting path."""

    pdf_bytes = drive_service.files().export(
        fileId=doc_id, mimeType="application/pdf"
    ).execute()

    output_path.write_bytes(pdf_bytes)
    return output_path


def main() -> None:
    """Entry point for the CLI script."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        airtable_api_key = get_required_env("AIRTABLE_API_KEY")
        airtable_base_id = get_required_env("AIRTABLE_BASE_ID")
        openai_api_key = get_required_env("OPENAI_API_KEY")
        doc_id = get_required_env("GOOGLE_DOC_TEMPLATE_ID")
    except KeyError as exc:  # pragma: no cover - simple configuration guard
        missing = exc.args[0]
        logging.error("Missing required environment variable: %s", missing)
        raise SystemExit(1) from exc

    table_name = os.getenv("AIRTABLE_TABLE_NAME", "Trees")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "400"))
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")

    output_dir = ensure_output_directory(Path(os.getenv("OUTPUT_DIR", "outputs")))
    output_filename = os.getenv("OUTPUT_PDF_FILENAME", "generated_report.pdf")
    output_path = output_dir / output_filename

    try:
        records = fetch_airtable_records(airtable_api_key, airtable_base_id, table_name)
    except requests.RequestException as exc:
        logging.error("Failed to fetch Airtable records: %s", exc)
        raise SystemExit(1) from exc

    if not records:
        logging.warning("No records retrieved from Airtable table '%s'.", table_name)
        return

    client = OpenAI(api_key=openai_api_key)
    summaries = generate_summaries(client, records, model=model, max_tokens=max_tokens)

    if not summaries:
        logging.warning("No summaries were generated; aborting document update.")
        return

    try:
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=SCOPES,
        )
    except (FileNotFoundError, ValueError) as exc:
        logging.error("Failed to load Google service account credentials: %s", exc)
        raise SystemExit(1) from exc

    docs_service = build("docs", "v1", credentials=credentials)
    drive_service = build("drive", "v3", credentials=credentials)

    try:
        insert_summaries_into_doc(docs_service, doc_id, summaries)
    except HttpError as exc:
        logging.error("Failed to update Google Doc: %s", exc)
        raise SystemExit(1) from exc

    try:
        export_doc_to_pdf(drive_service, doc_id, output_path)
    except HttpError as exc:
        logging.error("Failed to export Google Doc to PDF: %s", exc)
        raise SystemExit(1) from exc

    logging.info("Report successfully written to %s", output_path.resolve())


if __name__ == "__main__":
    main()
