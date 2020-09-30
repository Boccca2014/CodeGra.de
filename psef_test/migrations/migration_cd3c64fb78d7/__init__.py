import itertools

import pytest

from .. import Tester


class UpgradeTester(Tester):
    courses = None

    def get_rubric_rows(self):
        return self.db.engine.execute(
            'SELECT * FROM "RubricRow" ORDER BY id',
        ).fetchall()

    def load_data(self):
        self.rubric_rows = self.get_rubric_rows()

    def check(self):
        cur_rows = self.get_rubric_rows()
        assert len(cur_rows) > 0
        assert len(self.rubric_rows
                   ) == len(cur_rows), 'No rubric_rows should be deleted'

        # Check that rows get the correct absolute position.
        for row in cur_rows:
            assert str(row['position']) in row['header']

        # Check that rows get the correct relative position.
        for row1, row2 in itertools.combinations(cur_rows, 2):
            if row1['Assignment_id'] != row2['Assignment_id']:
                continue
            elif row1['created_at'] < row2['created_at']:
                assert row1['position'] < row2['position']
            else:
                assert row1['position'] >= row2['position']

        # Check that positions are reused between assignments.
        pos_assig1 = set(
            row['position']
            for row in cur_rows
            if row['Assignment_id'] == 1
        )
        pos_assig2 = set(
            row['position']
            for row in cur_rows
            if row['Assignment_id'] == 2
        )
        assert pos_assig1 == pos_assig2


class DowngradeTester(Tester):
    @staticmethod
    def do_test():
        return False

    def load_data(self):
        pass

    def check(self):
        pass
