import subprocess
from itertools import groupby

import flask
import pytest

from .. import Tester


class UpgradeTester(Tester):
    def get_providers(self):
        return self.db.engine.execute(
            'SELECT * FROM "LTIProvider" ORDER BY key'
        ).fetchall()

    @staticmethod
    def do_test():
        return True

    def load_data(self):
        self.providers = self.get_providers()
        flask.current_app.config['LTI_CONSUMER_KEY_SECRETS'] = {
            'lms1': ('Canvas', ['bas', 'cda']),
            'lms2': ('BrightSpace', ['woo']),
        }

    def check(self):
        cur_providers = self.get_providers()
        assert len(cur_providers) > 0
        assert len(self.providers
                   ) <= len(cur_providers), 'No providers should be deleted'
        new_lti1p1 = {
            p.key: p
            for p in self.db.engine.execute(
                'SELECT * FROM "LTIProvider" '
                "WHERE lti_provider_version = 'lti1.1' "
                'ORDER BY key'
            ).fetchall()
        }
        assert new_lti1p1['lms1'].lms_1p1_name == 'Canvas'
        assert new_lti1p1['lms1'].lms_1p1_secret == ['bas', 'cda']
        assert new_lti1p1['lms1p1_removed'].lms_1p1_name is None
        assert new_lti1p1['lms1p1_removed'].lms_1p1_secret is None
        assert 'lms2' in new_lti1p1
        assert new_lti1p1['lms2'].lms_1p1_name == 'BrightSpace'
        assert new_lti1p1['lms2'].lms_1p1_secret == ['woo']


class DowngradeTester(Tester):
    @staticmethod
    def do_test():
        return False

    def load_data(self):
        pass

    def check(self):
        pass
