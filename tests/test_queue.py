import unittest
from types import SimpleNamespace

from src.bot.handlers.queue import render_queue


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
        self.assertIn("занято 1/2", rendered)
        self.assertIn("1. Aida", rendered)
        self.assertIn("2. свободно", rendered)

    def test_render_marks_closed_queue(self) -> None:
        queue = SimpleNamespace(
            status="closed",
            capacity=1,
            slots=[SimpleNamespace(position=1, user_id=None, user_name=None)],
        )

        self.assertIn("закрыта", render_queue(queue))


if __name__ == "__main__":
    unittest.main()
