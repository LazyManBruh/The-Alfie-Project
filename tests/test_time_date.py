"""Time and date skills. Also covers the regression where "times" (as in
"15 times 23") matched the time skill via plain substring, since "time" is
literally inside "times"."""

from alfie_assistant.skills.time_skill import TimeSkill
from alfie_assistant.skills.date_skill import DateSkill


def test_time_matches_and_answers():
    skill = TimeSkill()
    assert skill.matches("what time is it")
    assert skill.handle("what time is it").startswith("It's ")


def test_time_does_not_match_times_the_math_word():
    assert not TimeSkill().matches("what is 15 times 23")


def test_date_matches_and_answers():
    skill = DateSkill()
    assert skill.matches("what is the date today")
    assert skill.handle("what is the date today").startswith("Today is ")
