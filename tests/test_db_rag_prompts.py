"""Regression tests for defects the acceptance probes (build ticket 11) found in
the shared text-to-SQL generation prompt (used by chat, admin and reports agents
alike) -- fixed here rather than only in the reports persona.
"""

from datetime import datetime, timezone
from unittest import TestCase, main
from unittest.mock import patch

from app.prompts.db_rag import DB_RAG_SQL_GENERATION_SYSTEM_PROMPT, get_sql_generation_prompt


class EpochMillisecondGuidanceTest(TestCase):
    """The live Lyndom DB stores every transactional `int8` epoch column in
    milliseconds, not seconds. `to_timestamp(col)` alone silently produces a
    timestamp ~58,000 years in the future and matches zero rows on any
    calendar-year/quarter/month filter -- no tool error, just an empty result
    the model has no way to explain."""

    def test_prompt_states_milliseconds_not_seconds(self) -> None:
        self.assertIn("milliseconds", DB_RAG_SQL_GENERATION_SYSTEM_PROMPT)

    def test_prompt_teaches_the_millisecond_to_timestamp_conversion(self) -> None:
        self.assertIn("to_timestamp(col / 1000.0)", DB_RAG_SQL_GENERATION_SYSTEM_PROMPT)


class TodaysDateGuidanceTest(TestCase):
    """Probe 4 ("declining customers over the last five years") found the
    generator hardcode a literal 2018-2024 window instead of a window relative
    to the real current date -- the prompt never told it what "today" is, so it
    fell back to its own (stale) training-time sense of "now". The user-turn
    prompt must state the real server date and push it toward CURRENT_DATE/
    NOW()-relative arithmetic."""

    def test_prompt_states_todays_date(self) -> None:
        fixed_now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        with patch("app.prompts.db_rag.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            prompt = get_sql_generation_prompt("How many orders last year?", "")
        self.assertIn("2026-09-15", prompt)

    def test_prompt_pushes_toward_relative_date_arithmetic(self) -> None:
        prompt = get_sql_generation_prompt("How many orders last year?", "")
        self.assertIn("CURRENT_DATE", prompt)
        self.assertIn("your own sense of the current date", prompt)


if __name__ == "__main__":
    main()
