from __future__ import annotations


def data_dictionary_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(table: str, column: str, definition: str, data_type: str, allowed: str = "", notes: str = "") -> None:
        rows.append(
            {
                "table_name": table,
                "column_name": column,
                "definition": definition,
                "data_type": data_type,
                "allowed_values": allowed,
                "notes": notes,
            }
        )

    for column, definition, data_type, allowed, notes in STATEMENTS:
        add("statements", column, definition, data_type, allowed, notes)
    for column, definition, data_type, allowed, notes in VOTES:
        add("votes", column, definition, data_type, allowed, notes)
    for column, definition, data_type, allowed, notes in SOURCE_LOG:
        add("source_log", column, definition, data_type, allowed, notes)
    for column, definition, data_type, allowed, notes in FAILED:
        add("failed_or_ambiguous_pages", column, definition, data_type, allowed, notes)
    return rows


STATEMENTS = [
    ("statement_id", "Stable unique identifier for a poll statement.", "string", "", ""),
    ("poll_id", "Stable unique identifier for the poll page.", "string", "", ""),
    ("poll_title", "Title of the poll page.", "string", "", ""),
    ("poll_url", "Clark Center poll URL.", "string", "", ""),
    ("panel_type", "Expert panel shown on the source page.", "string", "US; Europe; Finance", ""),
    ("publication_date", "Publication date parsed from the poll page.", "date", "YYYY-MM-DD", ""),
    ("topic_or_category", "Source topic/category names when available.", "string", "", "Semicolon-separated."),
    ("question_label", "Question label from the source page.", "string", "Question A; Question B; ...", ""),
    ("statement_text", "Full statement text for the question.", "string", "", ""),
    ("poll_context", "Context shown before the poll statements, if any.", "string", "", ""),
    ("n_respondents", "Number of vote rows extracted for the statement.", "integer", "", ""),
    ("n_answered_excluding_no_opinion", "Count of standard agree/disagree/uncertain answers excluding No Opinion and missing.", "integer", "", ""),
    ("n_strongly_agree", "Unweighted count of Strongly Agree votes.", "integer", "", ""),
    ("n_agree", "Unweighted count of Agree votes.", "integer", "", ""),
    ("n_uncertain", "Unweighted count of Uncertain votes.", "integer", "", ""),
    ("n_disagree", "Unweighted count of Disagree votes.", "integer", "", ""),
    ("n_strongly_disagree", "Unweighted count of Strongly Disagree votes.", "integer", "", ""),
    ("n_no_opinion", "Unweighted count of No Opinion votes.", "integer", "", ""),
    ("n_missing_or_did_not_answer", "Unweighted count of missing or Did Not Answer responses.", "integer", "", ""),
    ("share_agree", "(Strongly Agree + Agree) / answered excluding No Opinion and missing.", "number", "0-1", ""),
    ("share_disagree", "(Disagree + Strongly Disagree) / answered excluding No Opinion and missing.", "number", "0-1", ""),
    ("share_uncertain", "Uncertain / answered excluding No Opinion and missing.", "number", "0-1", ""),
    ("net_agreement", "share_agree minus share_disagree.", "number", "-1 to 1", ""),
    ("majority_position", "Largest category when it reaches at least 0.50.", "string", "Agree; Disagree; Uncertain; No clear majority", ""),
    ("consensus_level", "Consensus bucket derived from unweighted shares.", "string", "Strong consensus agree; Moderate consensus agree; Split / disagreement; Moderate consensus disagree; Strong consensus disagree; Uncertain consensus", ""),
    ("polarization_score", "min(share_agree, share_disagree).", "number", "0-0.5", ""),
    ("source_csv_url", "Official Download Poll Data CSV URL when available.", "string", "", ""),
    ("extraction_method", "Primary extraction method used for this statement.", "string", "csv; html; mixed", "mixed means CSV votes plus HTML metadata/weighted chart/profile links."),
    ("extraction_notes", "Statement-level extraction notes.", "string", "", ""),
    ("issue_categories", "Issue categories assigned to the statement.", "string", "", "Semicolon-separated; see allowed category list in methodology."),
    ("category_source", "How issue_categories were assigned.", "string", "source; model_assigned; mixed", ""),
    ("category_confidence", "Extractor confidence in category assignment.", "number", "0-1", ""),
    ("weighted_share_strongly_agree", "Confidence-weighted Strongly Agree share from source chart, when available.", "number", "0-1", "This is separate from unweighted counts."),
    ("weighted_share_agree_only", "Confidence-weighted Agree-only share from source chart, when available.", "number", "0-1", ""),
    ("weighted_share_uncertain", "Confidence-weighted Uncertain share from source chart, when available.", "number", "0-1", ""),
    ("weighted_share_disagree_only", "Confidence-weighted Disagree-only share from source chart, when available.", "number", "0-1", ""),
    ("weighted_share_strongly_disagree", "Confidence-weighted Strongly Disagree share from source chart, when available.", "number", "0-1", ""),
    ("weighted_share_agree", "Confidence-weighted Strongly Agree plus Agree share.", "number", "0-1", ""),
    ("weighted_share_disagree", "Confidence-weighted Disagree plus Strongly Disagree share.", "number", "0-1", ""),
    ("weighted_net_agreement", "weighted_share_agree minus weighted_share_disagree.", "number", "-1 to 1", ""),
    ("weighted_polarization_score", "min(weighted_share_agree, weighted_share_disagree).", "number", "0-0.5", ""),
]

VOTES = [
    ("vote_id", "Stable unique identifier for an economist-statement vote.", "string", "", ""),
    ("statement_id", "Foreign key to statements.statement_id.", "string", "", ""),
    ("poll_id", "Foreign key to poll page.", "string", "", ""),
    ("poll_title", "Title of the poll page.", "string", "", ""),
    ("poll_url", "Clark Center poll URL.", "string", "", ""),
    ("panel_type", "Expert panel shown on the source page.", "string", "US; Europe; Finance", ""),
    ("publication_date", "Publication date parsed from the poll page.", "date", "YYYY-MM-DD", ""),
    ("question_label", "Question label from the source page.", "string", "Question A; Question B; ...", ""),
    ("statement_text", "Full statement text for the question.", "string", "", ""),
    ("economist_name", "Economist or panelist name.", "string", "", ""),
    ("economist_affiliation", "University or institutional affiliation from source HTML when available.", "string", "", ""),
    ("economist_profile_url", "Bio/Vote History URL from source HTML when available.", "string", "", ""),
    ("vote_raw", "Original vote exactly as extracted from the preferred source.", "string", "", "Official CSV labels are preserved where CSV is available."),
    ("vote_normalized", "Vote mapped to the requested normalized categories.", "string", "Strongly Agree; Agree; Uncertain; Disagree; Strongly Disagree; No Opinion; Did Not Answer / Missing; Other / Not Applicable", "Numeric 0-5 survey-special ratings map to Other / Not Applicable."),
    ("confidence_raw", "Confidence value exactly as extracted.", "string", "", ""),
    ("confidence_numeric", "Numeric confidence when parseable.", "number", "", ""),
    ("comment", "Economist comment from source.", "string", "", ""),
    ("cited_resource_or_link", "Background/resource link included in the visible comment row, if any.", "string", "", "Semicolon-separated."),
    ("source_csv_url", "Official Download Poll Data CSV URL when available.", "string", "", ""),
    ("extraction_method", "Primary extraction method used for this vote.", "string", "csv; html; mixed", ""),
    ("extraction_notes", "Vote-level extraction notes.", "string", "", ""),
]

SOURCE_LOG = [
    ("timestamp_utc", "UTC time when the source was requested.", "datetime", "ISO 8601", ""),
    ("resource_type", "Type of source resource.", "string", "robots; sitemap; api; page; csv", ""),
    ("url", "URL fetched.", "string", "", ""),
    ("status_code", "HTTP status code, `cache` for cache reuse, or blank if the request failed before a response.", "integer/string", "", ""),
    ("bytes_downloaded", "Number of response bytes downloaded.", "integer", "", ""),
    ("local_path", "Path of cached raw response.", "string", "", ""),
    ("notes", "Fetch notes or error text.", "string", "", ""),
]

FAILED = [
    ("poll_url", "Poll URL with a failure or ambiguity.", "string", "", ""),
    ("poll_id", "Poll ID when known.", "string", "", ""),
    ("issue_type", "Failure or ambiguity type.", "string", "", ""),
    ("details", "Human-readable details.", "string", "", ""),
]
