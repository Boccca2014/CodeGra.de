import pytest

import psef
from psef.archive import (
    Archive, UnsafeArchive, ArchiveMemberInfo, _TarArchive, _ZipArchive,
    _7ZipArchive
)


def test_check_files(app, monkeypatch, describe):
    with describe('setup'):
        monkeypatch.setitem(app.config, 'MAX_NUMBER_OF_FILES', 100000)
        safe = 'test_data/test_submissions/multiple_dir_archive.tar.gz'
        unsafe = 'test_data/test_submissions/unsafe.tar.gz'

    with describe('Safe archive is file'):
        with open(safe,
                  'rb') as fp, Archive.create_from_fileobj(safe, fp) as arch:
            assert arch.check_files() is None

    with describe('Unsafe raises exception'):
        with open(unsafe, 'rb') as fp, Archive.create_from_fileobj(
            unsafe, fp
        ) as arch:
            with pytest.raises(UnsafeArchive) as wrap:
                arch.check_files()

            assert wrap.value.args[0] == (
                'Archive member destination is outside the target directory'
            )

    with describe('empty file'):
        for name in ['///', '', './/..//']:

            class MyArchive:
                def has_less_items_than(self, x):
                    return True

                def get_members(self):
                    return [
                        ArchiveMemberInfo(
                            orig_name=name,
                            is_dir=True,
                            size=2,
                            orig_file=None,
                        ),
                    ]

            with pytest.raises(UnsafeArchive) as wrap:
                Archive(MyArchive(), '').check_files()

            msg = wrap.value.args[0]
            assert msg == (
                'Archive member destination is outside the target directory'
            )


def test_get_members_tarfile(describe):
    with describe('setup'):
        f1 = 'test_data/test_submissions/multiple_dir_archive.tar.gz'
        f2 = 'test_data/test_submissions/deheading_dir_archive.tar.gz'
        f3 = 'test_data/test_submissions/with_empty_dir.tar.gz'

    with describe('multiple dir'), open(f1, 'rb') as fp:
        zp = _TarArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('dir', True),
            ('dir/single_file_work', False),
            ('dir/single_file_work_copy', False),
            ('dir2', True),
            ('dir2/single_file_work', False),
            ('dir2/single_file_work_copy', False),
        ]

    with describe('deheading dir'), open(f2, 'rb') as fp:
        zp = _TarArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('dir', True),
            ('dir/dir2', True),
            ('dir/dir2/single_file_work', False),
            ('dir/dir2/single_file_work_copy', False),
        ]

    with describe('with empty dir'), open(f3, 'rb') as fp:
        zp = _TarArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('with_empty_dir', True),
            ('with_empty_dir/empty_dir', True),
            ('with_empty_dir/full_dir', True),
            ('with_empty_dir/full_dir/a_file', False),
        ]


def test_get_members_zipfile(describe):
    with describe('setup'):
        f1 = 'test_data/test_submissions/multiple_dir_archive.zip'
        f2 = 'test_data/test_submissions/deheading_dir_archive.zip'
        f3 = 'test_data/test_submissions/with_empty_dir.zip'

    with describe('multiple dir'), open(f1, 'rb') as fp:
        zp = _ZipArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('dir/single_file_work', False),
            ('dir/single_file_work_copy', False),
            ('dir2/single_file_work', False),
            ('dir2/single_file_work_copy', False),
        ]

    with describe('deheading dir'), open(f2, 'rb') as fp:
        zp = _ZipArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('dir/dir2/single_file_work', False),
            ('dir/dir2/single_file_work_copy', False),
        ]

    with describe('with empty dir'), open(f3, 'rb') as fp:
        zp = _ZipArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('with_empty_dir/', True),
            ('with_empty_dir/empty_dir/', True),
            ('with_empty_dir/full_dir/', True),
            ('with_empty_dir/full_dir/a_file', False),
        ]


def test_get_members_7zip(describe):
    with describe('setup'):
        f1 = 'test_data/test_submissions/multiple_dir_archive.7z'
        f2 = 'test_data/test_submissions/deheading_dir_archive.7z'
        f3 = 'test_data/test_submissions/with_empty_dir.7z'

    with describe('multiple dir'), open(f1, 'rb') as fp:
        zp = _7ZipArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('dir/single_file_work', False),
            ('dir/single_file_work_copy', False),
            ('dir2/single_file_work', False),
            ('dir2/single_file_work_copy', False),
        ]

    with describe('deheading dir'), open(f2, 'rb') as fp:
        zp = _7ZipArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('dir/dir2/single_file_work', False),
            ('dir/dir2/single_file_work_copy', False),
        ]

    with describe('with empty dir'), open(f3, 'rb') as fp:
        zp = _7ZipArchive(fp)
        found = sorted(zp.get_members())
        assert [(f.orig_name, f.is_dir) for f in found] == [
            ('with_empty_dir/full_dir/a_file', False),
            # ERROR: This is in correct, but caused by our 7zip library:
            # https://github.com/fancycode/pylzma/issues/69
            # ('with_empty_dir/empty_dir', True),
        ]
