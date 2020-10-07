import pytest

from psef.ignore import Options, FileRule, ParseError, SubmissionValidator


def test_parse_option():
    def make_config(opt_name, opt_value):
        return {
            'key': opt_name,
            'value': opt_value,
        }

    opts = Options()
    assert opts.get(Options.OptionName.delete_empty_directories) is False
    opts.parse_option(make_config('delete_empty_directories', True))
    assert opts.get(Options.OptionName.delete_empty_directories) is True

    with pytest.raises(ParseError) as e:
        opts.parse_option(make_config('delete_empty_directories', True))
    assert e.value.msg.startswith('Option "delete_empty_directories" was')


def test_parse_file_rule():
    def mc(filename, file_type='file', rule_type='allow'):
        return {
            'rule_type': rule_type, 'file_type': file_type, 'name': filename
        }

    with pytest.raises(ParseError) as e:
        FileRule.parse(mc(''))
    assert e.value.msg.startswith('The filename of a rule should be a non')

    with pytest.raises(ParseError) as e:
        FileRule.parse(mc('*/dir/', 'directory'))
    assert e.value.msg.startswith('Directories cannot contain wildcards')

    with pytest.raises(ParseError) as e:
        FileRule.parse(mc('/dir/*c*'))
    assert e.value.msg.startswith('Files can only contain one wildcard')

    with pytest.raises(ParseError) as e:
        FileRule.parse(mc('/dir/*/name'))
    assert e.value.msg.startswith('Files can only contain a wildcard for the ')

    with pytest.raises(ParseError) as e:
        FileRule.parse(mc('/dir/name/'))
    assert e.value.msg.startswith('Filenames should not end with a "/"')

    with pytest.raises(ParseError) as e:
        FileRule.parse(mc('/dir/name', 'directory'))
    assert e.value.msg.startswith('Directory names should end with a "/"')

    res = FileRule.parse(mc(' '))
    assert res.rule_type == FileRule.RuleType.allow
    assert res.file_type == FileRule.FileType.file
    assert res.filename.name == ' '
    assert res.filename.dir_names == []


def test_wrong_rule_with_policy():
    with pytest.raises(ParseError) as e:
        SubmissionValidator.parse({
            'policy': 'allow_all_files',
            'rules': [{
                'rule_type': 'allow', 'file_type': 'file', 'name': 'hello.py'
            }],
            'options': [],
        })
    assert e.value.msg.startswith('The policy is set to "allow_all_files", so')

    with pytest.raises(ParseError) as e:
        SubmissionValidator.parse({
            'policy': 'deny_all_files',
            'rules': [{
                'rule_type': 'deny', 'file_type': 'file', 'name': 'hello.py'
            }],
            'options': [],
        })
    assert e.value.msg.startswith('The policy is set to "deny_all_files", so')


def test_policy_deny_no_rules():
    with pytest.raises(ParseError) as e:
        SubmissionValidator.parse({
            'policy': 'deny_all_files',
            'options': [],
            'rules': [],
        })
    assert e.value.msg.startswith('When the policy is set to "deny_all_files"')
