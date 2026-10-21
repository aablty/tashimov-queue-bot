import unittest
from types import SimpleNamespace

from src.bot.handlers.queue import queue_markup, render_queue


class QueueRenderingTests(unittest.TestCase):
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
        queue = SimpleNamespace(
            id=7,
            status="active",
            slots=[
                SimpleNamespace(position=position, user_id=None)
                for position in range(1, 11)
            ],
        )

        markup = queue_markup(queue)

        self.assertEqual([len(row) for row in markup.inline_keyboard[:2]], [5, 5])
        self.assertEqual(markup.inline_keyboard[0][0].text, "1")
        self.assertEqual(markup.inline_keyboard[1][-1].text, "10")


if __name__ == "__main__":
    unittest.main()
