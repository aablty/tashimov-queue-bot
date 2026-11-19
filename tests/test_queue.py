import unittest
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tortoise import Tortoise

from src.bot.keyboards.queue import queue_markup
from src.bot.utils.queue import is_booking_open, minimum_start_minute
from src.bot.views.queue import render_queue
from src.db.models import Queue, QueueSlot
from src.db.queue import QueueRepository


class QueueRenderingTests(unittest.TestCase):
    def test_booking_opens_ten_minutes_before_queue(self) -> None:
        starts_at = datetime(2026, 10, 29, 12, 0, tzinfo=ZoneInfo("Asia/Qyzylorda"))
        ends_at = datetime(2026, 10, 29, 13, 0, tzinfo=ZoneInfo("Asia/Qyzylorda"))

        self.assertFalse(
            is_booking_open(
                starts_at,
                ends_at,
                now=datetime(2026, 10, 29, 11, 49, tzinfo=starts_at.tzinfo),
            )
        )
        self.assertTrue(
            is_booking_open(
                starts_at,
                ends_at,
                now=datetime(2026, 10, 29, 11, 50, tzinfo=starts_at.tzinfo),
            )
        )
        self.assertTrue(
            is_booking_open(
                starts_at,
                ends_at,
                now=datetime(2026, 10, 29, 12, 59, tzinfo=starts_at.tzinfo),
            )
        )
        self.assertFalse(
            is_booking_open(
                starts_at,
                ends_at,
                now=datetime(2026, 10, 29, 13, 0, tzinfo=starts_at.tzinfo),
            )
        )

    def test_exact_hour_is_allowed_for_one_time_queue(self) -> None:
        current = datetime(2026, 10, 29, 22, 0, tzinfo=ZoneInfo("Asia/Qyzylorda"))
        with patch("src.bot.utils.queue.datetime") as datetime_mock:
            datetime_mock.now.return_value = current
            self.assertEqual(minimum_start_minute(date(2026, 10, 29)), 22 * 60)

    def test_started_hour_is_rounded_to_the_next_hour(self) -> None:
        current = datetime(2026, 10, 29, 22, 1, tzinfo=ZoneInfo("Asia/Qyzylorda"))
        with patch("src.bot.utils.queue.datetime") as datetime_mock:
            datetime_mock.now.return_value = current
            self.assertEqual(minimum_start_minute(date(2026, 10, 29)), 23 * 60)

    def test_render_shows_capacity_and_occupants(self) -> None:
        queue = SimpleNamespace(
            status="active",
            capacity=2,
            slots=[
                SimpleNamespace(position=2, user_id=None, user_name=None),
                SimpleNamespace(position=1, user_id=42, user_name="Aida"),
            ],
        )

        rendered = render_queue(queue)

        self.assertIn("активна", rendered)
        self.assertIn("Занято: 1/2", rendered)
        self.assertIn('1. <a href="tg://user?id=42">Aida</a>', rendered)
        self.assertNotIn("свободно", rendered)

    def test_render_marks_closed_queue(self) -> None:
        queue = SimpleNamespace(
            status="closed",
            capacity=1,
            slots=[SimpleNamespace(position=1, user_id=None, user_name=None)],
        )

        self.assertIn("закрыта", render_queue(queue, closed=True))

    def test_markup_uses_compact_numeric_grid(self) -> None:
        now = datetime.now(UTC)
        queue = SimpleNamespace(
            id=7,
            status="active",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            slots=[
                SimpleNamespace(position=position, user_id=None)
                for position in range(1, 11)
            ],
        )

        markup = queue_markup(queue)

        self.assertEqual([len(row) for row in markup.inline_keyboard[:2]], [5, 5])
        self.assertEqual(markup.inline_keyboard[0][0].text, "1")
        self.assertEqual(markup.inline_keyboard[1][-1].text, "10")

    def test_markup_keeps_occupied_numbers_and_marks_them(self) -> None:
        now = datetime.now(UTC)
        queue = SimpleNamespace(
            id=7,
            status="active",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            slots=[
                SimpleNamespace(position=1, user_id=42),
                SimpleNamespace(position=2, user_id=None),
            ],
        )

        markup = queue_markup(queue)

        occupied, free = markup.inline_keyboard[0]
        self.assertEqual(occupied.text, "1")
        self.assertEqual(occupied.style, "primary")
        self.assertIsNotNone(occupied.disabled)
        self.assertEqual(free.text, "2")
        self.assertEqual(free.style, "success")
        self.assertIsNone(free.disabled)

    def test_markup_disables_free_slots_before_booking_window(self) -> None:
        now = datetime.now(UTC)
        queue = SimpleNamespace(
            id=7,
            status="active",
            starts_at=now + timedelta(minutes=11),
            ends_at=now + timedelta(hours=1, minutes=11),
            slots=[SimpleNamespace(position=1, user_id=None)],
        )

        button = queue_markup(queue).inline_keyboard[0][0]

        self.assertEqual(button.style, "primary")
        # Telegram requires an action field even on a disabled button, so
        # callback_data must stay set — the client won't let it be tapped.
        self.assertIsNotNone(button.callback_data)
        self.assertIsNotNone(button.disabled)


class UpdateScheduleKeepsBookingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await Tortoise.init(
            db_url="sqlite://:memory:", modules={"models": ["src.db.models"]}
        )
        await Tortoise.generate_schemas()

    async def asyncTearDown(self) -> None:
        await Tortoise.close_connections()

    async def test_editing_a_schedule_does_not_wipe_an_active_booking(self) -> None:
        repository = QueueRepository()
        weekday = min(datetime.now(ZoneInfo("Asia/Qyzylorda")).weekday(), 5)
        schedule = await repository.create_schedule(
            chat_id=1,
            teacher_id=1,
            name="Flutter",
            kind="weekly",
            once_date=None,
            weekday=weekday,
            start_minute=9 * 60,
            end_minute=10 * 60,
            capacity=2,
            timezone="Asia/Qyzylorda",
        )
        queue = await Queue.filter(schedule_id=schedule.id).first()
        slot = await QueueSlot.filter(queue_id=queue.id, position=1).first()
        slot.user_id = 777
        slot.user_name = "Student"
        await slot.save()

        await repository.update_schedule(
            schedule.id,
            name="Flutter Pro",
            kind="weekly",
            once_date=None,
            weekday=weekday,
            start_minute=9 * 60,
            end_minute=10 * 60,
            capacity=3,
        )

        refreshed = await QueueSlot.get(id=slot.id)
        self.assertEqual(refreshed.user_id, 777)
        self.assertEqual(await Queue.filter(schedule_id=schedule.id).count(), 1)


if __name__ == "__main__":
    unittest.main()
