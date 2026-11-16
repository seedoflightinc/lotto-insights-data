import copy
import datetime as dt
import unittest
from update_history import extend, parse, validate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'date': '1999-10-27', 'numbers': [1, 2, 3, 4, 5, 6]},
                     {'date': '1999-10-30', 'numbers': [7, 8, 9, 10, 11, 12]}]

    def test_valid(self):
        validate(self.rows)

    def test_duplicate_date(self):
        with self.assertRaises(ValueError): validate(self.rows + [self.rows[-1]])

    def test_missing_draw(self):
        with self.assertRaises(ValueError): validate(self.rows[1:])

    def test_future_draw(self):
        with self.assertRaises(ValueError): validate(self.rows, dt.date(1999, 10, 28))

    def test_invalid_numbers(self):
        for numbers in ([1, 1, 3, 4, 5, 6], [0, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 54], [True, 2, 3, 4, 5, 6]):
            bad = copy.deepcopy(self.rows)
            bad[0]['numbers'] = numbers
            with self.assertRaises(ValueError): validate(bad)

    def test_extension(self):
        extend({'draws': self.rows[:1]}, self.rows)

    def test_removed_or_changed(self):
        with self.assertRaises(ValueError): extend({'draws': self.rows}, self.rows[:1])
        bad = copy.deepcopy(self.rows)
        bad[0]['numbers'] = [2, 3, 4, 5, 6, 7]
        with self.assertRaises(ValueError): extend({'draws': self.rows}, bad)

    def test_pdf_columns_and_double_play(self):
        rows = parse('10/27/99 1-2-3-4-5-6 LOTTO 10/30/99 7-8-9-10-11-12 LOTTO\n10/30/99 1-2-3-4-5-6 LOTTO DP')
        self.assertEqual(rows, self.rows)

    def test_unrecognized_pdf_row(self):
        with self.assertRaises(ValueError): parse('10/27/99 format changed')


if __name__ == '__main__': unittest.main()
