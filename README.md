# codex-test

## Tree risk assessment report generator

This repository contains a small utility for producing tree risk assessment summaries.
The script pulls tree inventory records from Airtable, asks OpenAI's GPT models to
write professional summaries, appends those summaries to a Google Docs template, and
exports the finished report as a PDF.

### Prerequisites

* Python 3.10 or newer
* An Airtable base with a table containing the tree inventory
* An OpenAI API key with access to the chosen model
* A Google Cloud service account with access to the Google Doc template (store the
  JSON credentials locally)

Install the Python dependencies with:

```bash
pip install -r requirements.txt
```

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `AIRTABLE_API_KEY` | ✅ | Airtable personal access token or API key. |
| `AIRTABLE_BASE_ID` | ✅ | The base identifier for the Airtable workspace. |
| `AIRTABLE_TABLE_NAME` | ❌ | Name of the Airtable table (defaults to `Trees`). |
| `OPENAI_API_KEY` | ✅ | API key used to call OpenAI's API. |
| `OPENAI_MODEL` | ❌ | Chat Completions model name (defaults to `gpt-4o-mini`). |
| `OPENAI_MAX_TOKENS` | ❌ | Maximum tokens for each completion (defaults to `400`). |
| `GOOGLE_DOC_TEMPLATE_ID` | ✅ | The ID of the Google Docs template to update. |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | ❌ | Path to the Google service account credentials file (defaults to `credentials.json`). |
| `OUTPUT_DIR` | ❌ | Directory where the exported PDF will be saved (defaults to `outputs`). |
| `OUTPUT_PDF_FILENAME` | ❌ | Filename for the generated PDF (defaults to `generated_report.pdf`). |

### Running the script

Once the environment variables are configured, run the generator with:

```bash
python scripts/generate_tree_reports.py
```

On success the Google Doc is updated with the generated summaries and the document is
exported to a PDF file under the configured output directory.
