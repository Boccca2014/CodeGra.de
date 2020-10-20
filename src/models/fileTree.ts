import { hasAttr, sortBy, coerceToString } from '@/utils';
import { NONEXISTENT } from '@/constants';

const REVISIONS = ['student', 'teacher'] as const;

type Revision = Map<string | null, string | null>;

interface FileServerData {
    id: string;
    name: string;
}

interface DirectoryServerData extends FileServerData {
    entries: Array<FileServerData | DirectoryServerData>;
}

interface AutoTestDirectoryServerData extends DirectoryServerData {
    autoTestSuiteId: number;
}

export class BaseFile<T extends string | null> {
    constructor(
        public readonly id: T,
        public readonly name: string,
        public readonly parent: Directory<string> | null,
    ) {}

    public getFullName(): string {
        const parts = [this.name];
        let parent = this.parent;
        while (parent != null) {
            parts.push(parent.name);
            parent = parent.parent;
        }
        // We don't want the top level directory as this never has a meaningful
        // name.
        parts.pop();
        return parts.reverse().join('/');
    }
}

export class File extends BaseFile<string> {
    constructor(id: string, name: string, parent: Directory<string> | null) {
        super(id, name, parent);
        Object.freeze(this);
    }

    static fromServerData(serverData: FileServerData, parent: Directory<string> | null) {
        return new File(serverData.id, serverData.name, parent);
    }
}

export class Directory<T extends string | null> extends BaseFile<T> {
    protected _entries: ReadonlyArray<File | Directory<string>>;

    constructor(id: T, name: string, parent: Directory<string> | null) {
        super(id, name, parent);
        this._entries = [];
    }

    _setEntries(entries: readonly (File | Directory<string>)[]) {
        this._entries = Object.freeze(entries);
        Object.freeze(this);
    }

    get entries(): ReadonlyArray<File | Directory<string>> {
        return this._entries;
    }

    static fromServerData(
        serverData: DirectoryServerData,
        parent: Directory<string> | null,
        dirCls = Directory,
        fileCls = File,
    ): Directory<string> {
        // eslint-disable-next-line
        const self = new dirCls(serverData.id, serverData.name, parent);
        const entries = serverData.entries.map(entry => {
            if (hasAttr(entry, 'entries')) {
                return dirCls.fromServerData(entry as DirectoryServerData, self, Directory);
            } else {
                return fileCls.fromServerData(entry, self);
            }
        });

        // eslint-disable-next-line
        self._setEntries(entries);
        return self;
    }

    static makeEmpty<Y extends string | null>(
        id: Y,
        name: string,
        parent: Directory<string> | null,
    ) {
        const self = new Directory(id, name, parent);
        // eslint-disable-next-line
        self._setEntries([]);
        return self;
    }
}

export class AutoTestDirectory extends Directory<string> {
    public autoTestSuiteId!: number;

    _setEntries(entries: ReadonlyArray<Directory<string> | File>) {
        // We don't freeze the object here because we may need to set an
        // additional key later on in _setSuiteId().
        this._entries = Object.freeze(entries);
    }

    _setSuiteId(suiteId: number | null) {
        if (suiteId != null) {
            this.autoTestSuiteId = suiteId;
        }
        Object.freeze(this);
    }

    static fromServerData(
        serverData: AutoTestDirectoryServerData,
        parent: Directory<string> | null,
    ) {
        const self = Directory.fromServerData(
            serverData,
            parent,
            AutoTestDirectory as any,
        ) as AutoTestDirectory;
        // eslint-disable-next-line
        self._setSuiteId(serverData.autoTestSuiteId);
        return self;
    }
}

class DiffEntry {
    constructor(
        public readonly ids: [string | null, string] | [string, string | null],
        public readonly name: string,
    ) {}

    getRevisions(accum: Revision) {
        if (this.ids[0] !== this.ids[1]) {
            accum.set(this.ids[0], this.ids[1]);
            accum.set(this.ids[1], this.ids[0]);
            return true;
        } else {
            return false;
        }
    }
}

type DiffDirs =
    | { dir1: Directory<string>; dir2: Directory<string | null> }
    | { dir1: Directory<string | null>; dir2: Directory<string> };

class DiffTree extends DiffEntry {
    public readonly entries: ReadonlyArray<DiffEntry>;

    constructor(
        ids: [string, string | null] | [string | null, string],
        name: string,
        entries: DiffEntry[],
    ) {
        super(ids, name);
        this.entries = Object.freeze(entries);
        Object.freeze(this);
    }

    static fromDirectories({ dir1, dir2 }: DiffDirs) {
        let zipped = dir1.entries.reduce<
            Record<
                string,
                {
                    self: typeof NONEXISTENT | Directory<string> | File;
                    other: typeof NONEXISTENT | Directory<string> | File;
                }
            >
        >((accum, cur) => {
            accum[cur.name] = {
                self: cur,
                other: NONEXISTENT,
            };
            return accum;
        }, {});

        zipped = dir2.entries.reduce((accum, cur) => {
            if (accum[cur.name] == null) {
                accum[cur.name] = {
                    self: NONEXISTENT,
                    other: cur,
                };
            }
            accum[cur.name].other = cur;
            return accum;
        }, zipped);

        const entries = sortBy(
            Object.values(zipped).reduce<(DiffTree | DiffEntry)[]>((accum, { self, other }) => {
                if (self instanceof Directory && other instanceof Directory) {
                    accum.push(DiffTree.fromDirectories({ dir1: self, dir2: other }));
                } else if (self instanceof Directory) {
                    if (other instanceof File) {
                        accum.push(Object.freeze(new DiffEntry([null, other.id], other.name)));
                    }
                    accum.push(
                        DiffTree.fromDirectories({
                            dir1: self,
                            dir2: Directory.makeEmpty(null, self.name, self.parent),
                        }),
                    );
                } else if (other instanceof Directory) {
                    if (self instanceof File) {
                        accum.push(Object.freeze(new DiffEntry([self.id, null], self.name)));
                    }
                    accum.push(
                        DiffTree.fromDirectories({
                            dir1: Directory.makeEmpty(null, other.name, other.parent),
                            dir2: other,
                        }),
                    );
                } else {
                    let curName: string = '';
                    let selfId = null;
                    let otherId = null;

                    if (other instanceof File) {
                        otherId = other.id;
                        curName = other.name;
                    }
                    if (self instanceof File) {
                        selfId = self.id;
                        curName = self.name;
                    }

                    accum.push(Object.freeze(new DiffEntry([selfId, otherId] as any, curName)));
                }

                return accum;
            }, []),
            entry => [entry.name, entry instanceof DiffTree],
        );

        const ids: [string | null, string] | [string, string | null] = [dir1.id, dir2.id] as any;
        return new DiffTree(ids, dir1.name, entries);
    }

    getRevisions(accum: Revision) {
        const res = this.entries.reduce((foundAny, entry) => {
            // The method `getRevisions` mutates `accum` so don't short circuit
            // here.
            const val = entry.getRevisions(accum);
            return foundAny || val;
        }, this.ids[0] !== this.ids[1]);

        if (res) {
            if (this.ids[0] === this.ids[1]) {
                accum.set(this.ids[0], null);
            } else {
                if (this.ids[0] != null) {
                    accum.set(this.ids[0], this.ids[1]);
                }
                if (this.ids[1] != null) {
                    accum.set(this.ids[1], this.ids[0]);
                }
            }
        }

        return res;
    }
}

export class FileTree {
    public student: Directory<string>;

    public teacher: Directory<string> | null;

    public diff: DiffTree;

    public autotest: AutoTestDirectory | null;

    private _revisions: Readonly<Revision>;

    constructor(
        studentTree: Directory<string>,
        teacherTree: Directory<string> | null,
        diff: DiffTree,
        public readonly flattened: Record<string, string>,
        revisions: Readonly<Revision>,
        autoTestTree: AutoTestDirectory | null = null,
    ) {
        this.student = studentTree;
        this.teacher = teacherTree;
        this.diff = diff;
        this.flattened = flattened;
        this._revisions = revisions;

        this.autotest = autoTestTree;
        Object.freeze(this);
    }

    addAutoTestTree(autoTestTree: AutoTestDirectoryServerData) {
        return new FileTree(
            this.student,
            this.teacher,
            this.diff,
            this.flattened,
            this._revisions,
            AutoTestDirectory.fromServerData(autoTestTree, null),
        );
    }

    static fromServerData(
        serverStudentTree: DirectoryServerData,
        serverTeacherTree: DirectoryServerData | null,
    ) {
        const studentTree = Directory.fromServerData(serverStudentTree, null, Directory);
        const teacherTree =
            serverTeacherTree == null
                ? null
                : Directory.fromServerData(serverTeacherTree, null, Directory);
        const diff = DiffTree.fromDirectories({
            dir1: studentTree,
            dir2: teacherTree ?? studentTree,
        });
        const revisions = new Map();
        if (teacherTree != null) {
            diff.getRevisions(revisions);
        }

        const flattened = Object.freeze(FileTree.flatten(diff));
        return new FileTree(studentTree, teacherTree, diff, flattened, Object.freeze(revisions));
    }

    static flatten(tree: DiffTree | null, prefix: string[] = []) {
        const filePaths: Record<string, string> = {};
        if (tree == null || tree.entries == null) {
            return {};
        }

        tree.entries.forEach(f => {
            prefix.push(f.name);

            if (f instanceof DiffTree) {
                const dirPaths = FileTree.flatten(f, prefix);
                Object.assign(filePaths, dirPaths);
            } else {
                const name = prefix.join('/');
                if (f.ids[0] != null) {
                    filePaths[f.ids[0]] = name;
                }
                if (f.ids[1] != null) {
                    filePaths[f.ids[1]] = name;
                }
            }

            prefix.pop();
        });

        return filePaths;
    }

    hasAnyRevision() {
        if (this.teacher == null) {
            return false;
        }
        return this.hasRevision(this.student) || this.hasRevision(this.teacher);
    }

    hasRevision(f: string | DiffEntry | BaseFile<string>): boolean {
        if (f instanceof DiffEntry) {
            return f.ids.some(id => id != null && this.hasRevision(id));
        } else {
            let fId: string;
            if (typeof f === 'string') {
                fId = f;
            } else if (hasAttr(f, 'id')) {
                fId = f.id;
            } else {
                fId = coerceToString(f);
            }

            return this._revisions.has(fId);
        }
    }

    getRevisionId(f: BaseFile<string | null>) {
        return this._revisions.get(f.id);
    }

    // Returns the first file in the file tree that is not a folder
    // The file tree is searched with BFS
    getFirstFile(revision: typeof REVISIONS[number]) {
        const tree = this[revision];

        if (tree == null) {
            return null;
        }

        const queue: Array<Directory<string> | File> = [tree];
        let candidate = null;
        let firstFound: File | null = null;

        while (queue.length > 0) {
            candidate = queue.shift();

            if (candidate == null) {
                break;
            } else if (candidate instanceof Directory) {
                queue.push(...candidate.entries);
            } else {
                firstFound = firstFound ?? candidate;
                if (!candidate.name.startsWith('.')) {
                    return candidate;
                }
            }
        }

        // Well fuck it, lets simply return a broken file.
        return firstFound;
    }

    // Search the tree for the file with the given id.
    search(revision: typeof REVISIONS[number], id: string) {
        return this.findFileInDir(this[revision], id);
    }

    getRevision(id: string) {
        return REVISIONS.find(rev => this.search(rev, id) != null);
    }

    findFileInDir<T extends Directory<string> | DiffTree>(
        tree: T | null,
        id: string | null,
    ): null | (T extends Directory<string> ? BaseFile<string> : DiffEntry) {
        if (tree == null || tree.entries == null || id == null) {
            return null;
        }
        const todo = [tree.entries];

        for (let i = 0; todo.length > i; ++i) {
            const entries = todo[i];
            for (let j = 0; j < entries.length; ++j) {
                const child = entries[j];

                if (child instanceof BaseFile && child.id === id) {
                    return child as any;
                } else if (child instanceof BaseFile && this._revisions.get(child.id) === id) {
                    return child as any;
                } else if (
                    child instanceof DiffEntry &&
                    (child.ids[0] === id || child.ids[1] === id)
                ) {
                    return child as any;
                } else if (child instanceof Directory || child instanceof DiffTree) {
                    todo.push(child.entries);
                }
            }
        }
        return null;
    }
}
