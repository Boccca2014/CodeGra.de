/* SPDX-License-Identifier: AGPL-3.0-only */
import {
    getProps,
    setProps,
    formatGrade,
    snakeToCamelCase,
    readableFormatDate,
    coerceToString,
} from '@/utils';
import moment from 'moment';
import { store } from '@/store';
import * as mutationTypes from '@/store/mutation-types';

const NONEXISTENT = {};

const REVISIONS = ['student', 'teacher'];

class BaseFile {
    constructor(id, name, parent) {
        this.id = id;
        this.name = name;
        this.parent = parent;
    }
}

export class File extends BaseFile {
    constructor(id, name, parent) {
        super(id, name, parent);
        Object.freeze(this);
    }

    static fromServerData(serverData, parent) {
        return new File(serverData.id, serverData.name, parent);
    }
}

export class Directory extends BaseFile {
    constructor(id, name, parent) {
        super(id, name, parent);
        this.entries = [];
    }

    _setEntries(entries) {
        this.entries = Object.freeze(entries);
        Object.freeze(this);
    }

    static fromServerData(serverData, parent = null) {
        const self = new Directory(serverData.id, serverData.name, parent);
        const entries = serverData.entries.map(entry => {
            if (Object.hasOwnProperty.call(entry, 'entries')) {
                return Directory.fromServerData(entry, self);
            } else {
                return File.fromServerData(entry, self);
            }
        });

        // eslint-disable-next-line
        self._setEntries(entries);
        return self;
    }

    static makeEmpty(id, name, parent) {
        const self = new Directory(id, name, parent);
        // eslint-disable-next-line
        self._setEntries([]);
        return self;
    }
}

class DiffEntry {
    constructor(ids, name) {
        this.ids = ids;
        this.name = name;
    }

    getRevisions(accum) {
        if (this.ids[0] !== this.ids[1]) {
            accum[this.ids[0]] = this.ids[1];
            accum[this.ids[1]] = this.ids[0];
            return true;
        } else {
            return false;
        }
    }
}

class DiffTree extends DiffEntry {
    constructor(ids, name, entries) {
        super(ids, name);
        this.entries = Object.freeze(entries);
        Object.freeze(this);
    }

    static fromDirectories(dir1, dir2) {
        let zipped = dir1.entries.reduce((accum, cur) => {
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
                };
            }
            accum[cur.name].other = cur;
            return accum;
        }, zipped);

        const entries = Object.values(zipped).reduce((accum, { self, other }) => {
            const curName = self.name || other.name;

            if (self instanceof Directory && other instanceof Directory) {
                accum.push(DiffTree.fromDirectories(self, other));
            } else if (self instanceof Directory) {
                if (other instanceof File) {
                    accum.push(Object.freeze(new DiffEntry([null, other.id], other.name)));
                }
                accum.push(
                    DiffTree.fromDirectories(
                        self,
                        Directory.makeEmpty(null, self.name, self.parent),
                    ),
                );
            } else if (other instanceof Directory) {
                if (self instanceof File) {
                    accum.push(Object.freeze(new DiffEntry([self.id, null], self.name)));
                }
                accum.push(
                    DiffTree.fromDirectories(
                        Directory.makeEmpty(null, other.name, other.parent),
                        other,
                    ),
                );
            } else {
                accum.push(
                    Object.freeze(new DiffEntry([self.id || null, other.id || null], curName)),
                );
            }

            return accum;
        }, []);

        entries.sort((a, b) => {
            if (a.name === b.name) {
                return a.entries ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        });

        return new DiffTree([dir1.id, dir2.id], dir1.name, entries);
    }

    getRevisions(accum) {
        const res = this.entries.reduce((foundAny, entry) => {
            // The method `getRevisions` mutates `accum` so don't short circuit
            // here.
            const val = entry.getRevisions(accum);
            return foundAny || val;
        }, this.ids[0] !== this.ids[1]);

        if (res) {
            if (this.ids[0] === this.ids[1]) {
                accum[this.ids[0]] = null;
            } else {
                if (this.ids[0]) {
                    accum[this.ids[0]] = this.ids[1];
                }
                if (this.ids[1]) {
                    accum[this.ids[1]] = this.ids[0];
                }
            }
        }

        return res;
    }
}

export class FileTree {
    constructor(studentTree, teacherTree, diff, flattened, revisions, autoTestTree = null) {
        this.student = studentTree;
        this.teacher = teacherTree;
        this.diff = diff;
        this.flattened = flattened;
        this._revisions = revisions;

        this.autotest = autoTestTree;
        Object.freeze(this);
    }

    addAutoTestTree(autoTestTree) {
        return new FileTree(
            this.student,
            this.teacher,
            this.diff,
            this.flattened,
            this._revisions,
            Directory.fromServerData(autoTestTree),
        );
    }

    static fromServerData(serverStudentTree, serverTeacherTree) {
        const studentTree = Directory.fromServerData(serverStudentTree);
        const teacherTree = serverTeacherTree && Directory.fromServerData(serverTeacherTree);
        const diff = DiffTree.fromDirectories(studentTree, teacherTree || studentTree);
        const revisions = {};
        if (teacherTree) {
            diff.getRevisions(revisions);
        }

        const flattened = Object.freeze(FileTree.flatten(diff));
        return new FileTree(studentTree, teacherTree, diff, flattened, Object.freeze(revisions));
    }

    static flatten(tree, prefix = []) {
        const filePaths = {};
        if (!tree || !tree.entries) {
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
        return this.hasRevision(this.teacher) || this.hasRevision(this.student);
    }

    hasRevision(f) {
        if (f instanceof DiffEntry) {
            return f.ids.some(id => id && this.hasRevision(id));
        } else {
            let fId;
            if (Object.hasOwnProperty.call(f, 'id')) {
                fId = f.id;
            } else {
                fId = f;
            }

            return Object.hasOwnProperty.call(this._revisions, fId);
        }
    }

    getRevisionId(f) {
        return this._revisions[f.id];
    }

    // Returns the first file in the file tree that is not a folder
    // The file tree is searched with BFS
    getFirstFile(revision) {
        const tree = this[revision];

        if (!tree) {
            return null;
        }

        const queue = [tree];
        let candidate = null;
        let firstFound = null;

        while (queue.length > 0) {
            candidate = queue.shift();

            if (candidate.entries) {
                queue.push(...candidate.entries);
            } else {
                firstFound = firstFound || candidate;
                if (!candidate.name.startsWith('.')) {
                    return candidate;
                }
            }
        }

        // Well fuck it, lets simply return a broken file.
        return firstFound;
    }

    // Search the tree for the file with the given id.
    search(revision, id) {
        return this.findFileInDir(this[revision], id);
    }

    getRevision(id) {
        return REVISIONS.find(rev => this.search(rev, id) != null);
    }

    findFileInDir(tree, id) {
        if (!tree || !tree.entries || id == null) {
            return null;
        }
        const todo = [tree.entries];

        for (let i = 0; todo.length > i; ++i) {
            const entries = todo[i];
            for (let j = 0; j < entries.length; ++j) {
                const child = entries[j];

                if (
                    child.id === id ||
                    this._revisions[child.id] === id ||
                    (child.ids && (child.ids[0] === id || child.ids[1] === id))
                ) {
                    return child;
                } else if (child.entries != null) {
                    todo.push(child.entries);
                }
            }
        }
        return null;
    }
}

export class FeedbackLine {
    constructor(fileId, line, message, author) {
        // a fileId should never be a number.
        this.fileId = coerceToString(fileId);
        // A lineNumber should always be a number.
        this.line = Number(line);
        this.lineNumber = this.line;

        this.msg = message;
        this.authorId = null;

        if (author) {
            this.authorId = author.id;
            store.commit(`users/${mutationTypes.ADD_OR_UPDATE_USER}`, author);
        }

        Object.freeze(this);
    }

    get author() {
        return store.getters['users/getUser'](this.authorId);
    }
}

export class Feedback {
    constructor(general, linter, userLines) {
        this.general = general;
        this.linter = linter;
        this.userLines = Object.freeze(userLines);
        this.user = Object.freeze(
            this.userLines.reduce((acc, line) => {
                setProps(acc, line, line.fileId, line.lineNumber);
                return acc;
            }, {}),
        );

        Object.freeze(this);
    }

    static fromServerData(feedback) {
        const authors = feedback.authors;

        const general = getProps(feedback, null, 'general');
        const linter = getProps(feedback, {}, 'linter');

        const userLines = Object.entries(getProps(feedback, {}, 'user')).reduce(
            (lines, [fileId, fileFeedback]) => {
                lines.push(
                    ...Object.entries(fileFeedback).map(([line, lineFeedback]) => {
                        if (line instanceof FeedbackLine) {
                            return line;
                        } else {
                            return new FeedbackLine(
                                fileId,
                                line,
                                lineFeedback,
                                getProps(authors, null, fileId, line),
                            );
                        }
                    }),
                );
                return lines;
            },
            [],
        );
        return new Feedback(general, linter, userLines);
    }

    addFeedbackLine(line) {
        if (!(line instanceof FeedbackLine)) {
            throw new Error('The given line is not the correct class');
        }

        const newLines = [...this.userLines];
        const oldLineIndex = this.userLines.findIndex(
            l => l.lineNumber === line.lineNumber && l.fileId === line.fileId,
        );
        if (oldLineIndex < 0) {
            newLines.push(line);
        } else {
            newLines[oldLineIndex] = line;
        }

        return new Feedback(this.general, this.linter, newLines);
    }

    removeFeedbackLine(fileId, lineNumber) {
        return new Feedback(
            this.general,
            this.linter,
            this.userLines.filter(l => !(l.lineNumber === lineNumber && l.fileId === fileId)),
        );
    }
}

const SUBMISSION_SERVER_PROPS = ['id', 'origin', 'extra_info', 'grade_overridden', 'comment'];

const USER_PROPERTIES = ['user', 'assignee', 'comment_author'].reduce((acc, cur) => {
    acc[cur] = `${snakeToCamelCase(cur)}Id`;
    return acc;
}, {});

export class Submission {
    constructor(props) {
        Object.assign(this, props);
        this.grade = formatGrade(this.fullGrade);
        this.formattedCreatedAt = readableFormatDate(this.createdAt);
        Object.freeze(this);
    }

    static fromServerData(serverData, assignmentId) {
        const props = {};
        SUBMISSION_SERVER_PROPS.forEach(prop => {
            props[prop] = serverData[prop];
        });

        props.assignmentId = assignmentId;
        props.createdAt = moment.utc(serverData.created_at, moment.ISO_8601);
        props.fullGrade = serverData.grade;

        Object.entries(USER_PROPERTIES).forEach(([serverProp, idProp]) => {
            const user = serverData[serverProp];
            if (user != null) {
                props[idProp] = user.id;
                store.commit(`users/${mutationTypes.ADD_OR_UPDATE_USER}`, user);
            } else {
                props[idProp] = null;
            }
        });

        return new Submission(props);
    }

    get fileTree() {
        return store.getters['fileTrees/getFileTree'](this.assignmentId, this.id);
    }

    get feedback() {
        return store.getters['feedback/getFeedback'](this.assignmentId, this.id);
    }

    update(newProps) {
        return new Submission(
            Object.assign(
                {},
                this,
                Object.entries(newProps).reduce((acc, [key, val]) => {
                    if (key === 'id') {
                        throw TypeError(`Cannot set submission property: ${key}`);
                    } else if (key === 'grade') {
                        acc.fullGrade = val;
                    } else if (USER_PROPERTIES[key] != null) {
                        const prop = USER_PROPERTIES[key];

                        if (val) {
                            store.dispatch('users/addOrUpdateUser', { user: val });
                            acc[prop] = val.id;
                        } else {
                            acc[prop] = null;
                        }
                    } else {
                        acc[key] = val;
                    }

                    return acc;
                }, {}),
            ),
        );
    }

    get assignment() {
        return store.getters['courses/assignments'][this.assignmentId];
    }

    isLate() {
        if (this.assignment == null) {
            return false;
        }
        return this.createdAt.isAfter(this.assignment.deadline);
    }
}

Object.entries(USER_PROPERTIES).forEach(([serverProp, idProp]) => {
    Object.defineProperty(Submission.prototype, serverProp, {
        get() {
            return store.getters['users/getUser'](this[idProp]) || { id: null };
        },
        enumerable: false,
    });
});
