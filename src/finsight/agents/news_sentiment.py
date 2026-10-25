from __future__ import annotations

import re

from finsight.models import NewsSearchResult, NewsSentimentAssessment

_POSITIVE_TERMS = {
    "approval",
    "beat",
    "beats",
    "growth",
    "upgrade",
    "profit",
    "record",
    "raises",
    "surge",
    "wins",
}
_NEGATIVE_TERMS = {
    "concern",
    "concerns",
    "cuts",
    "decline",
    "downgrade",
    "drop",
    "fraud",
    "investigation",
    "lawsuit",
    "layoff",
    "loss",
    "miss",
    "misses",
    "recall",
    "warning",
}


def assess_headline_sentiment(news: NewsSearchResult | None) -> NewsSentimentAssessment:
    if news is None:
        return NewsSentimentAssessment(
            status="failed",
            method="headline keyword screen",
            positive_headlines=0,
            negative_headlines=0,
            neutral_headlines=0,
            summary="News sentiment could not be assessed because news retrieval failed.",
            warnings=["No retrieved headlines were available for analysis."],
        )
    if not news.articles:
        return NewsSentimentAssessment(
            status="partial",
            method="headline keyword screen",
            positive_headlines=0,
            negative_headlines=0,
            neutral_headlines=0,
            summary="The provider returned no headlines to classify.",
            warnings=["Headline sentiment is unavailable because no articles were returned."],
        )

    positive = negative = neutral = 0
    for article in news.articles:
        tokens = set(re.findall(r"[a-z]+", article.title.lower()))
        has_positive = bool(tokens & _POSITIVE_TERMS)
        has_negative = bool(tokens & _NEGATIVE_TERMS)
        if has_positive and not has_negative:
            positive += 1
        elif has_negative and not has_positive:
            negative += 1
        else:
            # Mixed headlines remain unclassified instead of forcing a direction.
            neutral += 1

    label = (
        "more positive"
        if positive > negative
        else "more negative"
        if negative > positive
        else "mixed or neutral"
    )
    return NewsSentimentAssessment(
        status="partial",
        method="simple keyword screen of headlines only",
        positive_headlines=positive,
        negative_headlines=negative,
        neutral_headlines=neutral,
        summary=(
            f"Headline keyword screen: {positive} positive, {negative} negative, "
            f"{neutral} neutral or mixed; overall {label}."
        ),
        warnings=[
            "This is a simple headline-only keyword screen, not a language-model or article-text "
            "sentiment analysis."
        ],
    )
