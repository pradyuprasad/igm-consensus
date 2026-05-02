from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceLogEntry:
    timestamp_utc: str
    resource_type: str
    url: str
    status_code: int | str
    bytes_downloaded: int
    local_path: str
    notes: str = ""


@dataclass
class QuestionMeta:
    label: str
    text: str
    unweighted_page_percentages: dict[str, float] = field(default_factory=dict)
    weighted_page_percentages: dict[str, float] = field(default_factory=dict)


@dataclass
class HtmlVote:
    question_label: str
    economist_name: str
    affiliation: str = ""
    profile_url: str = ""
    vote_raw: str = ""
    confidence_raw: str = ""
    comment: str = ""
    cited_resource_or_link: str = ""


@dataclass
class PollMeta:
    poll_id: str
    poll_title: str
    poll_url: str
    panel_type: str
    publication_date: str
    topic_or_category: str
    issue_categories: str
    category_source: str
    category_confidence: str
    poll_context: str
    source_csv_url: str
    questions: list[QuestionMeta]
    html_votes: list[HtmlVote]
    extraction_notes: list[str] = field(default_factory=list)
    is_special: bool = False

