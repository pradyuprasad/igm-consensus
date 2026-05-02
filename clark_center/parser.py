from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from dateutil import parser as date_parser

from .categories import classify_issue_categories
from .models import HtmlVote, PollMeta, QuestionMeta
from .normalize import normalize_vote
from .util import absolute_url, clean_text, read_csv_text, stable_id, url_slug


QUESTION_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def parse_poll_page(
    url: str,
    html: str,
    category_lookup: dict[str, str],
) -> PollMeta:
    soup = BeautifulSoup(html, "lxml")
    post = _main_post(soup)
    classes = post.get("class", []) if post else []
    is_special = "survey-special" in classes or "/surveys-special/" in url
    title = _title_text(soup.select_one("h1.title"))
    if not title:
        title = clean_text(_text_or_empty(soup.select_one("title"))).replace(" - Clark Center Forum", "")
    poll_id = _poll_id(url, classes)
    panel_type = _panel_type(post, classes)
    publication_date = _publication_date(soup)
    source_csv_url = _source_csv_url(soup)
    category_slugs = [
        class_name.removeprefix("category-")
        for class_name in classes
        if class_name.startswith("category-")
        and class_name not in {"category-economic-experts", "category-uncategorized"}
    ]
    topic_names = [category_lookup.get(slug, _title_from_slug(slug)) for slug in category_slugs]
    if is_special and not topic_names:
        topic_names = ["Financial Crises"]
    if is_special:
        questions, html_votes, context = _parse_special_page(soup)
    else:
        questions = _parse_questions(soup)
        html_votes = _parse_standard_html_votes(soup)
        context = _poll_context(soup)
    issue_categories, category_source, category_confidence = classify_issue_categories(
        category_slugs,
        title,
        [question.text for question in questions],
    )
    if is_special and issue_categories == "Other":
        issue_categories = "Banking; Financial regulation"
        category_source = "model_assigned"
        category_confidence = "0.70"
    notes: list[str] = []
    if not source_csv_url:
        notes.append("No official CSV download link found; extracted votes from HTML.")
    if is_special:
        notes.append("Survey-special page uses 0-5 numeric importance ratings, not the standard agreement scale.")
    return PollMeta(
        poll_id=poll_id,
        poll_title=title,
        poll_url=url,
        panel_type=panel_type,
        publication_date=publication_date,
        topic_or_category="; ".join(topic_names),
        issue_categories=issue_categories,
        category_source=category_source,
        category_confidence=category_confidence,
        poll_context=context,
        source_csv_url=source_csv_url,
        questions=questions,
        html_votes=html_votes,
        extraction_notes=notes,
        is_special=is_special,
    )


def parse_csv_votes(
    poll: PollMeta,
    csv_text: str,
    html_vote_lookup: dict[tuple[str, str], HtmlVote],
) -> list[dict[str, str]]:
    reader = csv.reader(io.StringIO(csv_text.lstrip("\ufeff"), newline=""))
    rows = list(reader)
    if not rows:
        return []
    header = [clean_text(cell) for cell in rows[0]]
    data_rows = rows[1:]
    question_specs = _csv_question_specs(header, poll.questions)
    if not question_specs:
        return []
    votes: list[dict[str, str]] = []
    for row_index, row in enumerate(data_rows, start=1):
        padded = row + [""] * (len(header) - len(row))
        if not any(clean_text(cell) for cell in padded):
            continue
        row_map = {header[i]: padded[i] if i < len(padded) else "" for i in range(len(header))}
        name = _csv_name(row_map, header)
        if not name:
            name = f"CSV row {row_index}"
        affiliation = _first_available(row_map, ("University", "Affiliation", "Institution"))
        for spec in question_specs:
            raw_vote = clean_text(padded[spec["vote_idx"]]) if spec["vote_idx"] < len(padded) else ""
            raw_confidence = clean_text(padded[spec["confidence_idx"]]) if spec.get("confidence_idx") is not None else ""
            comment = clean_text(padded[spec["comment_idx"]]) if spec.get("comment_idx") is not None else ""
            normalized_name = _person_key(name)
            html_vote = html_vote_lookup.get((spec["label"], normalized_name))
            votes.append(
                {
                    "question_label": spec["label"],
                    "statement_text": spec["statement_text"],
                    "economist_name": name,
                    "economist_affiliation": affiliation or (html_vote.affiliation if html_vote else ""),
                    "economist_profile_url": html_vote.profile_url if html_vote else "",
                    "vote_raw": raw_vote,
                    "vote_normalized": normalize_vote(raw_vote),
                    "confidence_raw": raw_confidence,
                    "comment": comment or (html_vote.comment if html_vote else ""),
                    "cited_resource_or_link": html_vote.cited_resource_or_link if html_vote else "",
                }
            )
    return votes


def html_votes_as_vote_rows(poll: PollMeta) -> list[dict[str, str]]:
    question_text_by_label = {question.label: question.text for question in poll.questions}
    rows: list[dict[str, str]] = []
    for vote in poll.html_votes:
        rows.append(
            {
                "question_label": vote.question_label,
                "statement_text": question_text_by_label.get(vote.question_label, ""),
                "economist_name": vote.economist_name,
                "economist_affiliation": vote.affiliation,
                "economist_profile_url": vote.profile_url,
                "vote_raw": vote.vote_raw,
                "vote_normalized": normalize_vote(vote.vote_raw),
                "confidence_raw": vote.confidence_raw,
                "comment": vote.comment,
                "cited_resource_or_link": vote.cited_resource_or_link,
            }
        )
    return rows


def build_html_vote_lookup(poll: PollMeta) -> dict[tuple[str, str], HtmlVote]:
    lookup: dict[tuple[str, str], HtmlVote] = {}
    for vote in poll.html_votes:
        lookup[(vote.question_label, _person_key(vote.economist_name))] = vote
    return lookup


def question_by_label(poll: PollMeta) -> dict[str, QuestionMeta]:
    return {question.label: question for question in poll.questions}


def csv_question_count(csv_text: str) -> int:
    rows = read_csv_text(csv_text)
    if not rows:
        return 0
    header = list(rows[0].keys())
    return len(_csv_question_specs(header, []))


def _main_post(soup: BeautifulSoup) -> Tag | None:
    return soup.select_one("div.post-single.type-survey, div.post-single.type-survey-special")


def _poll_id(url: str, classes: list[str]) -> str:
    panel = ""
    for class_name in classes:
        if class_name.startswith("survey_group-"):
            panel = class_name.removeprefix("survey_group-")
            break
    return stable_id(panel, url_slug(url), max_len=80)


def _panel_type(post: Tag | None, classes: list[str]) -> str:
    for class_name in classes:
        if class_name == "survey_group-us":
            return "US"
        if class_name == "survey_group-europe":
            return "Europe"
        if class_name == "survey_group-finance":
            return "Finance"
    if post:
        link = post.select_one("a[href*='/survey_group/']")
        if link:
            text = clean_text(link.get_text())
            if text:
                return text
    return ""


def _publication_date(soup: BeautifulSoup) -> str:
    node = soup.select_one("time.date")
    raw = clean_text(node.get_text()) if node else ""
    if not raw:
        meta = soup.select_one("meta[property='article:published_time']")
        raw = clean_text(meta.get("content")) if meta else ""
    if not raw:
        return ""
    try:
        return date_parser.parse(raw).date().isoformat()
    except (ValueError, TypeError, OverflowError):
        return ""


def _source_csv_url(soup: BeautifulSoup) -> str:
    for link in soup.select("div.data_download a, a"):
        text = clean_text(link.get_text())
        href = clean_text(link.get("href"))
        if href.lower().endswith(".csv") or "Download Poll Data" in text:
            return absolute_url(href)
    return ""


def _parse_questions(soup: BeautifulSoup) -> list[QuestionMeta]:
    questions: list[QuestionMeta] = []
    question_nodes = soup.select("h3.surveyQuestion")
    page_source = str(soup)
    unweighted = _parse_chart_arrays(page_source, "pollVals")
    weighted = _parse_chart_arrays(page_source, "weightedPV")
    if question_nodes:
        statement_nodes: list[tuple[str, Tag | None]] = []
        for index, node in enumerate(question_nodes):
            label_text = clean_text(node.get_text())
            match = re.search(r"Question\s+([A-Z])", label_text, re.I)
            label = f"Question {match.group(1).upper()}" if match else f"Question {QUESTION_LABELS[index]}"
            statement_nodes.append((label, node.find_next("h4")))
    else:
        statement_nodes = [
            (f"Question {QUESTION_LABELS[index]}", node)
            for index, node in enumerate(soup.select(".poll_results_wrapper_default h4"))
        ]
    for index, (label, statement_node) in enumerate(statement_nodes):
        text = clean_text(statement_node.get_text(" ", strip=True)) if statement_node else ""
        questions.append(
            QuestionMeta(
                label=label,
                text=text,
                unweighted_page_percentages=unweighted.get(index, {}),
                weighted_page_percentages=weighted.get(index, {}),
            )
        )
    return questions


def _parse_chart_arrays(text: str, prefix: str) -> dict[int, dict[str, float]]:
    pattern = re.compile(rf"var\s+{re.escape(prefix)}\d+_(\d+)\s*=\s*\[(.*?)\];", re.S)
    arrays: dict[int, dict[str, float]] = {}
    for match in pattern.finditer(text):
        index = int(match.group(1))
        values: dict[str, float] = {}
        for label, number in re.findall(r"\['([^']+)'\s*,\s*([0-9.]+)\]", match.group(2)):
            values[clean_text(label)] = float(number)
        arrays[index] = values
    return arrays


def _parse_standard_html_votes(soup: BeautifulSoup) -> list[HtmlVote]:
    votes: list[HtmlVote] = []
    found_heading_tables = False
    for heading in soup.find_all("h3"):
        heading_text = clean_text(heading.get_text(" ", strip=True))
        match = re.search(r"Question\s+([A-Z])\s+Participant Responses", heading_text, re.I)
        if not match:
            continue
        found_heading_tables = True
        label = f"Question {match.group(1).upper()}"
        table = heading.find_next("table", class_="responseDetail")
        if table is None:
            continue
        votes.extend(_parse_response_table(table, label))
    if not found_heading_tables:
        for index, table in enumerate(soup.select("table.responseDetail")):
            if "voteTableSpecialWrapper" in table.get("class", []):
                continue
            votes.extend(_parse_response_table(table, f"Question {QUESTION_LABELS[index]}"))
    return votes


def _parse_response_table(table: Tag, label: str) -> list[HtmlVote]:
    votes: list[HtmlVote] = []
    for row in table.select("tr.parent-row"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        name_cell = row.select_one("td.response-name")
        name_link = name_cell.find("a") if name_cell else None
        profile_url = absolute_url(clean_text(name_link.get("href"))) if name_link else ""
        name = _name_from_cell(name_cell)
        affiliation = clean_text(cells[1].get_text(" ", strip=True))
        vote_raw = _rating_text(cells[2])
        confidence_raw = _rating_text(cells[3])
        child = row.find_next_sibling("tr", class_="tablesorter-childRow")
        comment, links = _comment_and_links(child, profile_url)
        if name:
            votes.append(
                HtmlVote(
                    question_label=label,
                    economist_name=name,
                    affiliation=affiliation,
                    profile_url=profile_url,
                    vote_raw=vote_raw,
                    confidence_raw=confidence_raw,
                    comment=comment,
                    cited_resource_or_link=links,
                )
            )
    return votes


def _parse_special_page(soup: BeautifulSoup) -> tuple[list[QuestionMeta], list[HtmlVote], str]:
    content = soup.select_one(".post-content") or soup
    context = ""
    first_para = content.find("p")
    if first_para:
        context = clean_text(first_para.get_text(" ", strip=True))
    questions: list[QuestionMeta] = []
    ordered_list = content.find("ol")
    if ordered_list:
        for index, item in enumerate(ordered_list.find_all("li", recursive=False)):
            letter = QUESTION_LABELS[index]
            questions.append(QuestionMeta(label=f"Question {letter}", text=clean_text(item.get_text(" ", strip=True))))
    votes: list[HtmlVote] = []
    table = content.find("table", class_="voteTableSpecialWrapper")
    if not table:
        return questions, votes, context
    question_by_short_label = {question.label.split()[-1]: question for question in questions}
    for row in table.select("tr.parent-row"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 5:
            continue
        name_cell = cells[0]
        name_link = name_cell.find("a")
        profile_url = absolute_url(clean_text(name_link.get("href"))) if name_link else ""
        name = _name_from_cell(name_cell)
        affiliation = clean_text(cells[1].get_text(" ", strip=True))
        confidence_raw = clean_text(cells[3].get_text(" ", strip=True))
        comment, links = _comment_and_links(cells[4], profile_url)
        vote_table = cells[2].find("table")
        if vote_table:
            added_for_row = False
            for vote_row in vote_table.find_all("tr"):
                vote_cells = vote_row.find_all("td", recursive=False)
                if len(vote_cells) < 3:
                    continue
                letter = clean_text(vote_cells[0].get_text()).strip(".")
                if not letter:
                    continue
                label = f"Question {letter.upper()}"
                if letter.upper() not in question_by_short_label:
                    continue
                added_for_row = True
                votes.append(
                    HtmlVote(
                        question_label=label,
                        economist_name=name,
                        affiliation=affiliation,
                        profile_url=profile_url,
                        vote_raw=clean_text(vote_cells[2].get_text(" ", strip=True)),
                        confidence_raw=confidence_raw,
                        comment=comment,
                        cited_resource_or_link=links,
                    )
                )
            if not added_for_row and "Did Not Answer" in clean_text(vote_table.get_text(" ", strip=True)):
                for question in questions:
                    votes.append(
                        HtmlVote(
                            question_label=question.label,
                            economist_name=name,
                            affiliation=affiliation,
                            profile_url=profile_url,
                            vote_raw="Did Not Answer",
                            confidence_raw=confidence_raw,
                            comment=comment,
                            cited_resource_or_link=links,
                        )
                    )
        else:
            raw = clean_text(cells[2].get_text(" ", strip=True))
            for question in questions:
                votes.append(
                    HtmlVote(
                        question_label=question.label,
                        economist_name=name,
                        affiliation=affiliation,
                        profile_url=profile_url,
                        vote_raw=raw,
                        confidence_raw=confidence_raw,
                        comment=comment,
                        cited_resource_or_link=links,
                    )
                )
    return questions, votes, context


def _poll_context(soup: BeautifulSoup) -> str:
    content = soup.select_one(".post-content")
    if not content:
        return ""
    pieces: list[str] = []
    for child in content.children:
        if isinstance(child, Tag) and (
            "poll_results_wrapper_default" in child.get("class", [])
            or child.select_one("h3.surveyQuestion")
        ):
            break
        if isinstance(child, Tag) and child.name == "h3" and "surveyQuestion" in child.get("class", []):
            break
        if isinstance(child, Tag) and child.name == "p":
            text = clean_text(child.get_text(" ", strip=True))
            if text and "Source:" not in text:
                pieces.append(text)
    return " ".join(pieces)


def _csv_question_specs(header: list[str], questions: list[QuestionMeta]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    index = 0
    skipped = {
        "last name",
        "first name",
        "name",
        "university",
        "affiliation",
        "institution",
        "email",
    }
    while index < len(header):
        col = clean_text(header[index])
        lowered = col.lower()
        if not col or lowered in skipped or _is_confidence_col(col) or _is_comment_col(col):
            index += 1
            continue
        label = questions[len(specs)].label if len(specs) < len(questions) else f"Question {QUESTION_LABELS[len(specs)]}"
        statement_text = questions[len(specs)].text if len(specs) < len(questions) and questions[len(specs)].text else col
        confidence_idx = None
        comment_idx = None
        if index + 1 < len(header) and _is_confidence_col(header[index + 1]):
            confidence_idx = index + 1
            if index + 2 < len(header) and _is_comment_col(header[index + 2]):
                comment_idx = index + 2
                next_index = index + 3
            else:
                next_index = index + 2
        elif index + 1 < len(header) and _is_comment_col(header[index + 1]):
            comment_idx = index + 1
            next_index = index + 2
        else:
            next_index = index + 1
        specs.append(
            {
                "label": label,
                "statement_text": statement_text,
                "vote_idx": index,
                "confidence_idx": confidence_idx,
                "comment_idx": comment_idx,
            }
        )
        index = next_index
    return specs


def _is_confidence_col(col: str) -> bool:
    return "confidence" in col.lower()


def _is_comment_col(col: str) -> bool:
    lowered = col.lower()
    return "please explain" in lowered or "comment" in lowered or "explain your response" in lowered


def _csv_name(row: dict[str, str], header: list[str]) -> str:
    lower_to_key = {key.lower(): key for key in header}
    if "first name" in lower_to_key or "last name" in lower_to_key:
        first = clean_text(row.get(lower_to_key.get("first name", ""), ""))
        last = clean_text(row.get(lower_to_key.get("last name", ""), ""))
        return clean_text(f"{first} {last}")
    for key in ("Name", "Participant"):
        if key in row:
            return clean_text(row.get(key))
    return ""


def _first_available(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        if key in row and clean_text(row.get(key)):
            return clean_text(row.get(key))
    return ""


def _name_from_cell(cell: Tag | None) -> str:
    if cell is None:
        return ""
    link = cell.find("a")
    source = link if link else cell
    for image in source.find_all("img"):
        image.decompose()
    text = clean_text(source.get_text(" ", strip=True))
    return text.replace("Bio/Vote History", "").strip()


def _rating_text(cell: Tag | None) -> str:
    if cell is None:
        return ""
    rating = cell.select_one(".br-current-rating")
    if rating:
        return clean_text(rating.get_text(" ", strip=True))
    return clean_text(cell.get_text(" ", strip=True))


def _comment_and_links(node: Tag | None, profile_url: str) -> tuple[str, str]:
    if node is None:
        return "", ""
    links: list[str] = []
    for link in node.find_all("a"):
        href = absolute_url(clean_text(link.get("href")))
        text = clean_text(link.get_text(" ", strip=True))
        if href and href != profile_url and "Bio/Vote History" not in text:
            links.append(href)
        if "Bio/Vote History" in text:
            link.decompose()
    comment = clean_text(node.get_text(" ", strip=True)).replace("Bio/Vote History", "").strip()
    return comment, "; ".join(dict.fromkeys(links))


def _text_or_empty(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _title_text(node: Tag | None) -> str:
    if node is None:
        return ""
    direct_text = "".join(str(child) for child in node.children if isinstance(child, NavigableString))
    direct_text = clean_text(direct_text)
    if direct_text:
        return direct_text
    return clean_text(node.get_text(" ", strip=True))


def _title_from_slug(slug: str) -> str:
    return clean_text(slug.replace("-", " ").title())


def _person_key(name: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", clean_text(name).lower())
    tokens = [token for token in tokens if len(token) > 1]
    return "".join(tokens)
