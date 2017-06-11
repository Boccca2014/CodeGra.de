import os
import uuid
import shutil
import tempfile
from functools import reduce

import patoolib

from psef import app


def rename_directory_structure(rootdir):
    """
    Creates a nested dictionary that represents the folder structure of rootdir.

    A tree like:
    + dir1
      + dir 2
        - file 1
        - file 2
      - file 3
    will be moved to files given by :py:func:`random_file_path` and the object
    returned will represent the file structure, which will be something like this:
    ```
    {
        'dir1': {
            [
                'dir 2':{
                    [
                        ('file 1', 'new_name'),
                        ('file 2', 'new_name')
                    ]
                },
                ('file 3', 'new_name')
            ]
        }
    }
    ```

    :param str rootdir: The root directory to rename, files will not be removed
    :returns: The tree as described above.
    :rtype: dict
    """
    dir = {}
    rootdir = rootdir.rstrip(os.sep)
    start = rootdir.rfind(os.sep) + 1
    for path, dirs, files in os.walk(rootdir):
        folders = path[start:].split(os.sep)
        subdir = dict.fromkeys(files)
        parent = reduce(dict.get, folders[:-1], dir)
        parent[folders[-1]] = subdir

    def convert_to_lists(name, dirs):
        res = []
        for key, value in dirs.items():
            if value is None:
                new_name, filename = random_file_path()
                shutil.move(os.path.join(name, key), new_name)
                res.append((key, filename))
            else:
                res.append({
                    key:
                    convert_to_lists(os.path.join(name, key), value)
                })
        return res

    return convert_to_lists(rootdir[:start], dir)[0]


def is_archive(file):
    "Checks whether file ends with a known archive file extension."
    return file.filename.endswith(('.zip', '.tar.gz', '.tgz', '.tbz',
                                   '.tar.bz2'))


def extract(archive):
    "Extracts all files in archive with random name to uploads folder."
    tmpmode, tmparchive = tempfile.mkstemp()
    os.remove(tmparchive)
    tmparchive += '_' + os.path.basename(archive.filename)
    tmpdir = tempfile.mkdtemp()
    try:
        archive.save(tmparchive)
        patoolib.test_archive(tmparchive, verbosity=-1, interactive=False)
        patoolib.extract_archive(
            tmparchive, verbosity=-1, outdir=tmpdir, interactive=False)
        rootdir = tmpdir.rstrip(os.sep)
        start = rootdir.rfind(os.sep) + 1
        res = rename_directory_structure(tmpdir)[tmpdir[start:]]
        if len(res) > 1:
            return {'archive': res if isinstance(res, list) else [res]}
        elif not isinstance(res[0], dict):
            return {'archive': res}
        else:
            return res[0]
    finally:
        os.remove(tmparchive)
        shutil.rmtree(tmpdir)


def random_file_path():
    "Generates a new random file path in the upload directory."
    while True:
        name = str(uuid.uuid4())
        candidate = os.path.join(app.config['UPLOAD_DIR'], name)
        if os.path.exists(candidate):
            continue
        else:
            break
    return candidate, name


def dehead_filetree(tree):
    """Remove the head of the given filetree while preserving the old head
    name.

    So a tree {1: 2: 3: 4: [f1, f2]} will be converted to {1: [f1, f2]}

    :param dict tree: The file tree as generated by :py:func:`extract`
    :returns: The tree deheaded.
    :rtype: dict
    """
    assert len(tree) == 1
    head_node = list(tree.keys())[0]
    while len(tree[head_node]) == 1:
        if isinstance(tree[head_node], list):
            tree[head_node] = tree[head_node][0]
        elif isinstance(tree[head_node], dict):
            tree[head_node] = tree[head_node][list(tree[head_node].keys())[0]]
        else:
            break
        if not (isinstance(tree[head_node], list) or
                isinstance(tree[head_node], dict)):
            tree[head_node] = [tree[head_node]]
            break
    return tree


def process_files(files):
    """Process the given files by extracting, moving and saving their tree
    structure.

    :param files: The files to move and extract
    :returns: The tree of the files as is described by
              :py:func:`rename_directory_structure`
    :rtype: dict
    """
    if len(files) > 1 or not is_archive(files[0]):
        res = []
        for file in files:
            if is_archive(file):
                res.append(extract(file))
            else:
                new_file_name, filename = random_file_path()
                res.append((file.name, filename))
                file.save(new_file_name)
        res = {'.': res}
    else:
        res = extract(files[0])

    return dehead_filetree(res)
