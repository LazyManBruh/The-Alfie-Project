"""News headlines skill via BBC's RSS feed. Also covers the collision fix:
Wikipedia's broad "what is X" trigger was swallowing "what is in the news"
before "the news"/"news headlines"/"top headlines" were added to its
exclusion list (same class of bug hit for time/date/weather/system_control
phrasing earlier)."""

from unittest.mock import patch, MagicMock
import pytest
from alfie_assistant.skills.news_skill import NewsSkill
from alfie_assistant.skills.wikipedia_skill import WikipediaSkill

_SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Headline one</title></item>
<item><title>Headline two</title></item>
<item><title>Headline three</title></item>
<item><title>Headline four</title></item>
</channel></rss>"""


@pytest.fixture
def skill():
    return NewsSkill()


def test_reads_top_three_headlines_only(skill):
    fake_response = MagicMock(status_code=200, text=_SAMPLE_RSS.decode())
    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = fake_response
        response = skill.handle("give me the news")

    assert "Headline one" in response
    assert "Headline two" in response
    assert "Headline three" in response
    assert "Headline four" not in response


def test_feed_failure_reported_gracefully(skill):
    with patch("httpx.Client", side_effect=Exception("network down")):
        response = skill.handle("give me the news")
    assert "sir" in response.lower()


def test_does_not_collide_with_wikipedia():
    news, wiki = NewsSkill(), WikipediaSkill()
    for utterance in ["what is in the news", "give me the news", "top headlines"]:
        assert news.matches(utterance)
        assert not wiki.matches(utterance)


@pytest.mark.integration
def test_real_headlines(skill):
    response = skill.handle("give me the news")
    assert response.startswith("Here are the top headlines, sir:")
