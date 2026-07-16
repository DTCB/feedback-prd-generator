import app
import pandas as pd


def test_filter_badcases_prefers_severity_when_available():
    df = pd.DataFrame(
        {
            "severity": ["Low", "High", "Critical", "Medium"],
            "rating": [5, 4, 3, 1],
            "sentiment": ["positive", "neutral", "neutral", "negative"],
        }
    )

    badcases = app.filter_badcases(df)

    assert len(badcases) == 2
    assert set(badcases.index) == {1, 2}


def test_filter_badcases_falls_back_to_rating_and_sentiment_without_severity():
    df = pd.DataFrame(
        {
            "rating": [5, 2, 3, 1],
            "sentiment": ["positive", "neutral", "negative", "positive"],
        }
    )

    badcases = app.filter_badcases(df)

    assert len(badcases) == 3
    assert set(badcases.index) == {1, 2, 3}


def test_filter_badcases_prefers_explicit_flag():
    df = pd.DataFrame(
        {
            "is_badcase": [False, True, False],
            "severity": ["Critical", "Low", "High"],
            "rating": [1, 5, 1],
        }
    )

    badcases = app.filter_badcases(df)

    assert len(badcases) == 1
    assert badcases.index.tolist() == [1]
