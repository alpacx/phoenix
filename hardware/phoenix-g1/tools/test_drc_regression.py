import unittest
from drc_regression import introduced


def report(*pairs):
    return {'violations': [{'type': 'clearance', 'severity': 'error',
                            'items': [{'uuid': x} for x in pair]} for pair in pairs]}


class DrcRegressionTests(unittest.TestCase):
    def test_equal_counts_cannot_hide_replaced_violation(self):
        self.assertEqual(len(introduced(report(('a', 'b')), report(('a', 'c')))), 1)

    def test_item_order_is_irrelevant(self):
        self.assertFalse(introduced(report(('a', 'b')), report(('b', 'a'))))

    def test_fixed_violations_do_not_count_as_regressions(self):
        self.assertFalse(introduced(report(('a', 'b')), report()))


if __name__ == '__main__':
    unittest.main()
