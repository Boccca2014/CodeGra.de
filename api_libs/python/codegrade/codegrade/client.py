from dataclasses import dataclass
from functools import partial, wraps
from typing import Any, Dict, Union


class _User SettingModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.user_setting as user_setting

        self.get_all_notification_settings = wraps(user_setting.get_all_notification_settings)(partial(user_setting.get_all_notification_settings, client=client))
        self.patch_notification_setting = wraps(user_setting.patch_notification_setting)(partial(user_setting.patch_notification_setting, client=client))
        self.get_all_ui_preferences = wraps(user_setting.get_all_ui_preferences)(partial(user_setting.get_all_ui_preferences, client=client))
        self.patch_ui_preference = wraps(user_setting.patch_ui_preference)(partial(user_setting.patch_ui_preference, client=client))
        self.get_ui_preference = wraps(user_setting.get_ui_preference)(partial(user_setting.get_ui_preference, client=client))
class _Site settingsModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.site_settings as site_settings

        self.get_all = wraps(site_settings.get_all)(partial(site_settings.get_all, client=client))
        self.patch = wraps(site_settings.patch)(partial(site_settings.patch, client=client))
class _AssignmentModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.assignment as assignment

        self.get_all = wraps(assignment.get_all)(partial(assignment.get_all, client=client))
        self.get_rubric = wraps(assignment.get_rubric)(partial(assignment.get_rubric, client=client))
        self.put_rubric = wraps(assignment.put_rubric)(partial(assignment.put_rubric, client=client))
        self.delete_rubric = wraps(assignment.delete_rubric)(partial(assignment.delete_rubric, client=client))
        self.get_course = wraps(assignment.get_course)(partial(assignment.get_course, client=client))
        self.copy_rubric = wraps(assignment.copy_rubric)(partial(assignment.copy_rubric, client=client))
        self.patch = wraps(assignment.patch)(partial(assignment.patch, client=client))
class _AutoTestModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.auto_test as auto_test

        self.create = wraps(auto_test.create)(partial(auto_test.create, client=client))
        self.restart_result = wraps(auto_test.restart_result)(partial(auto_test.restart_result, client=client))
        self.get_results_by_user = wraps(auto_test.get_results_by_user)(partial(auto_test.get_results_by_user, client=client))
        self.get_result = wraps(auto_test.get_result)(partial(auto_test.get_result, client=client))
        self.delete_suite = wraps(auto_test.delete_suite)(partial(auto_test.delete_suite, client=client))
        self.update_suite = wraps(auto_test.update_suite)(partial(auto_test.update_suite, client=client))
        self.delete_set = wraps(auto_test.delete_set)(partial(auto_test.delete_set, client=client))
        self.update_set = wraps(auto_test.update_set)(partial(auto_test.update_set, client=client))
        self.stop_run = wraps(auto_test.stop_run)(partial(auto_test.stop_run, client=client))
        self.add_set = wraps(auto_test.add_set)(partial(auto_test.add_set, client=client))
        self.start_run = wraps(auto_test.start_run)(partial(auto_test.start_run, client=client))
        self.copy = wraps(auto_test.copy)(partial(auto_test.copy, client=client))
        self.get = wraps(auto_test.get)(partial(auto_test.get, client=client))
        self.delete = wraps(auto_test.delete)(partial(auto_test.delete, client=client))
        self.patch = wraps(auto_test.patch)(partial(auto_test.patch, client=client))
class _CourseModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.course as course

        self.get_all = wraps(course.get_all)(partial(course.get_all, client=client))
        self.put_enroll_link = wraps(course.put_enroll_link)(partial(course.put_enroll_link, client=client))
        self.get_group_sets = wraps(course.get_group_sets)(partial(course.get_group_sets, client=client))
        self.get_snippets = wraps(course.get_snippets)(partial(course.get_snippets, client=client))
        self.delete_role = wraps(course.delete_role)(partial(course.delete_role, client=client))
        self.get = wraps(course.get)(partial(course.get, client=client))
        self.patch = wraps(course.patch)(partial(course.patch, client=client))
class _UserModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.user as user

        self.get = wraps(user.get)(partial(user.get, client=client))
        self.login = wraps(user.login)(partial(user.login, client=client))
class _GroupModule:
    def __init__(self, client: 'Client') -> None:
        import codegrade.api.group as group

        self.get = wraps(group.get)(partial(group.get, client=client))


@dataclass
class Client:
    """ A class for keeping track of data related to the API """

    base_url: str

    def get_headers(self) -> Dict[str, str]:
        """ Get headers to be used in all endpoints """
        return {}

    @property
    def user_setting(self) -> _User SettingModule:
        return _User SettingModule(self)
    @property
    def site_settings(self) -> _Site settingsModule:
        return _Site settingsModule(self)
    @property
    def assignment(self) -> _AssignmentModule:
        return _AssignmentModule(self)
    @property
    def auto_test(self) -> _AutoTestModule:
        return _AutoTestModule(self)
    @property
    def course(self) -> _CourseModule:
        return _CourseModule(self)
    @property
    def user(self) -> _UserModule:
        return _UserModule(self)
    @property
    def group(self) -> _GroupModule:
        return _GroupModule(self)


@dataclass
class AuthenticatedClient(Client):
    """ A Client which has been authenticated for use on secured endpoints """

    token: str

    def get_headers(self) -> Dict[str, str]:
        """ Get headers to be used in authenticated endpoints """
        return {"Authorization": f"Bearer {self.token}"}