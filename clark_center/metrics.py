from __future__ import annotations

from collections import Counter

from .normalize import AGREEMENT_ORDER
from .util import decimal


def statement_metrics(votes: list[dict[str, str]]) -> dict[str, str | int]:
    counts = Counter(vote["vote_normalized"] for vote in votes)
    n_strongly_agree = counts["Strongly Agree"]
    n_agree = counts["Agree"]
    n_uncertain = counts["Uncertain"]
    n_disagree = counts["Disagree"]
    n_strongly_disagree = counts["Strongly Disagree"]
    n_no_opinion = counts["No Opinion"]
    n_missing = counts["Did Not Answer / Missing"]
    denominator = n_strongly_agree + n_agree + n_uncertain + n_disagree + n_strongly_disagree
    if denominator:
        share_agree = (n_strongly_agree + n_agree) / denominator
        share_disagree = (n_disagree + n_strongly_disagree) / denominator
        share_uncertain = n_uncertain / denominator
        net_agreement = share_agree - share_disagree
        polarization = min(share_agree, share_disagree)
    else:
        share_agree = share_disagree = share_uncertain = net_agreement = polarization = None
    return {
        "n_respondents": len(votes),
        "n_answered_excluding_no_opinion": denominator,
        "n_strongly_agree": n_strongly_agree,
        "n_agree": n_agree,
        "n_uncertain": n_uncertain,
        "n_disagree": n_disagree,
        "n_strongly_disagree": n_strongly_disagree,
        "n_no_opinion": n_no_opinion,
        "n_missing_or_did_not_answer": n_missing,
        "share_agree": decimal(share_agree),
        "share_disagree": decimal(share_disagree),
        "share_uncertain": decimal(share_uncertain),
        "net_agreement": decimal(net_agreement),
        "majority_position": majority_position(share_agree, share_disagree, share_uncertain),
        "consensus_level": consensus_level(share_agree, share_disagree, share_uncertain),
        "polarization_score": decimal(polarization),
    }


def majority_position(
    share_agree: float | None,
    share_disagree: float | None,
    share_uncertain: float | None,
) -> str:
    if share_agree is None or share_disagree is None or share_uncertain is None:
        return "No clear majority"
    shares = {
        "Agree": share_agree,
        "Disagree": share_disagree,
        "Uncertain": share_uncertain,
    }
    label, value = max(shares.items(), key=lambda item: item[1])
    if value >= 0.50:
        return label
    return "No clear majority"


def consensus_level(
    share_agree: float | None,
    share_disagree: float | None,
    share_uncertain: float | None,
) -> str:
    if share_agree is None or share_disagree is None or share_uncertain is None:
        return "Split / disagreement"
    if share_agree >= 0.80:
        return "Strong consensus agree"
    if share_disagree >= 0.80:
        return "Strong consensus disagree"
    if share_uncertain >= 0.65:
        return "Uncertain consensus"
    if 0.65 <= share_agree < 0.80:
        return "Moderate consensus agree"
    if 0.65 <= share_disagree < 0.80:
        return "Moderate consensus disagree"
    if max(share_agree, share_disagree, share_uncertain) < 0.65:
        return "Split / disagreement"
    return "Split / disagreement"


def weighted_metrics(weighted_percentages: dict[str, float]) -> dict[str, str]:
    if not weighted_percentages:
        return {
            "weighted_share_strongly_agree": "",
            "weighted_share_agree_only": "",
            "weighted_share_uncertain": "",
            "weighted_share_disagree_only": "",
            "weighted_share_strongly_disagree": "",
            "weighted_share_agree": "",
            "weighted_share_disagree": "",
            "weighted_net_agreement": "",
            "weighted_polarization_score": "",
        }
    shares = {label: weighted_percentages.get(label, 0.0) / 100.0 for label in AGREEMENT_ORDER}
    agree = shares["Strongly Agree"] + shares["Agree"]
    disagree = shares["Disagree"] + shares["Strongly Disagree"]
    uncertain = shares["Uncertain"]
    return {
        "weighted_share_strongly_agree": decimal(shares["Strongly Agree"]),
        "weighted_share_agree_only": decimal(shares["Agree"]),
        "weighted_share_uncertain": decimal(uncertain),
        "weighted_share_disagree_only": decimal(shares["Disagree"]),
        "weighted_share_strongly_disagree": decimal(shares["Strongly Disagree"]),
        "weighted_share_agree": decimal(agree),
        "weighted_share_disagree": decimal(disagree),
        "weighted_net_agreement": decimal(agree - disagree),
        "weighted_polarization_score": decimal(min(agree, disagree)),
    }

