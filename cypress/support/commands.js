// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
import 'cypress-file-upload';
import moment from 'moment';

function tomorrow() {
    return moment().add(1, 'day').endOf('day').toISOString();
}

function yesterday() {
    return moment().add(-1, 'day').startOf('day').toISOString();
}

const ADMIN_USER = { username: 'admin', password: 'admin' };

Cypress.Commands.add('getAll', (aliases) => {
    // Get the value for multiple aliases at once.

    const values = [];

    cy.wrap(aliases).each(alias => {
        return cy.get(alias).then(value => values.push(value));
    }).then(() => {
        return values;
    });
});

Cypress.Commands.add('text', { prevSubject: true }, subject => {
    // Get the text in an element, with all consecutive whitespace replaced
    // with a single space. Returns a cy wrapper so it can be used in an async
    // context.
    return subject.text().replace(/\s+/g, ' ');
});

Cypress.Commands.add('login', (username, password, route = undefined) => {
    Cypress.log({
        name: 'login',
        message: username,
        consoleProps: () => ({ username, password }),
    });
    return cy.request({
        url:'/api/v1/login',
        method: 'POST',
        body: { username, password }
    }).its('body').then(body => {
        cy.window().its('__app__').then(app => {
            const url = app.$router.getRestoreRoute();
            app.$store.dispatch('user/login', { data: body });
            if (url) {
                cy.visit(url.fullPath);
            } else if (route) {
                cy.visit(route);
            } else {
                cy.reload()
            }
            cy.get('#app > .loader').should('not.exist');
        });
    });
});

Cypress.Commands.add('logout', () => {
    cy.window().its('__app__').then(app => {
        app.$store.dispatch('user/logout');
        cy.visit('/');
    });
});

const loginCredentials = {};

function getAuthHeaders(user) {
    // Get the authentication header for the given user, or for the user logged
    // in in the frontend if no user is given.

    const mkHeader = (name, token) => {
        const header = { Authorization: `Bearer ${token}` };
        loginCredentials[name] = header;
        return header;
    }

    if (user != null) {
        if (loginCredentials[user.username]) {
            return cy.wrap(loginCredentials[user.username], { log: false });
        }

        return cy.request({
            url: '/api/v1/login',
            method: 'POST',
            body: user,
        }).its('body').then(res => {
            return mkHeader(res.user.username, res.access_token);
        });
    } else {
        return cy.window().its('__app__').then(app => {
            const { username, jwtToken } = app.$store.state.user;
            return mkHeader(username, jwtToken);
        });
    }
}

Cypress.Commands.add('authRequest', (options) => {
    // Do a request as the logged in user, or as the given user

    const user = options.user;
    delete options.user;

    return getAuthHeaders(user).then(headers => {
        options.headers = Object.assign(options.headers || {}, headers);
        return cy.request(options);
    });
});

Cypress.Commands.add('formRequest', (options) => {
    // Send a request with a FormData object as body.  This is impossible with
    // cy.request, and must be used to send requests to the server containing
    // files. Use cy.fixtureAsFile to load a fixture as a File object suitable
    // to be used in FormData. The request is sent as the logged in user.

    let { url, method, headers, user, data } = options;

    return getAuthHeaders(user).then(authHeaders => {
        headers = Object.assign({}, headers || {}, authHeaders)
        return cy
            .server()
            .route(method, url)
            .as('formRequest')
            .window()
            .then(win => {
                var xhr = new win.XMLHttpRequest();
                xhr.open(method, url);
                Object.entries(headers).forEach(([name, value]) => {
                    xhr.setRequestHeader(name, value);
                });
                xhr.send(data);
            })
            .wait('@formRequest');
    });
});

Cypress.Commands.add('delayRoute', (route, delay = 1000, matchRoute = undefined) => {
    matchRoute = matchRoute || route;
    const reqOpts = Object.assign({}, route);

    function makeResponse(res) {
        return Object.assign({}, matchRoute, {
            delay,
            headers: res.headers,
            response: res.body,
            status: res.status,
        });
    }

    return cy.authRequest(route).then(
        res => {
            return cy.route(makeResponse(res));
        },
        err => {
            return cy.route(makeResponse(err));
        },
    );
});

Cypress.Commands.add('fixtureAsFile', (path, filename, mimeType) => {
    // Load a fixture and return it as a File object.

    return cy.fixture(path, 'base64').then(fixture => {
        const decoded = atob(fixture);
        const len = decoded.length;
        const u8arr = new Uint8Array(len);

        for (let i = 0; i < len; i++) {
            u8arr[i] = decoded.charCodeAt(i);
        }

        return cy.wrap(new File([u8arr], filename, { type: mimeType }));
    });
});

// Upload a fixture to a file input.
Cypress.Commands.add('uploadFixture', { prevSubject: true }, (subject, fileName, mimeType = 'application/octet-stream') => {
    // Ensure this is a file input.
    cy.wrap(subject).should('have.prop', 'tagName').should('eq', 'INPUT');
    cy.wrap(subject).should('have.prop', 'type').should('eq', 'file');

    return cy.fixture(fileName).then(fileContent => {
        return cy.wrap(subject).upload({ fileContent, fileName, mimeType });
    });
});

Cypress.Commands.add('setSitePermission', (permission, roleName, value) => {
    cy.authRequest({
        url: '/api/v1/roles/',
        method: 'GET',
        user: ADMIN_USER,
    }).its('body').then(roles => {
        const role = roles.find(r => r.name === roleName);
        if (role.perms[permission] != value) {
            return cy.authRequest({
                url: `/api/v1/roles/${role.id}`,
                method: 'PATCH',
                user: ADMIN_USER,
                body: { permission, value },
            });
        }
    });
});

Cypress.Commands.add('createUser', (username, password, email = `${username}@example.com`) => {
    return cy.request({
        url: '/api/v1/user',
        method: 'POST',
        body: { name: username, username, password, email },
    });
});

Cypress.Commands.add('createCourse', (name, users=[]) => {
    return cy.authRequest({
        url: '/api/v1/courses/',
        method: 'POST',
        body: { name },
        user: ADMIN_USER,
    }).its('body').then(course => {
        // Get the course roles so we can map a role name
        // to a role id.
        return cy.authRequest({
            url: `/api/v1/courses/${course.id}/roles/`,
            method: 'GET',
            user: ADMIN_USER,
        }).its('body').then(roles => {
            return [course, roles];
        });
    }).then(([course, roles]) => {
        // Register each user for the course.
        cy.wrap(users).each(user => {
            const role = roles.find(r => r.name == user.role);
            cy.authRequest({
                url: `/api/v1/courses/${course.id}/users/`,
                method: 'PUT',
                user: ADMIN_USER,
                body: {
                    username: user.name,
                    role_id: role.id,
                },
            });
        })
        course.roles = roles;
        return cy.wrap(course);
    });
});

Cypress.Commands.add('createAssignment', (courseId, name, { state, bbZip, deadline } = {}) => {
    return cy.authRequest({
        url: `/api/v1/courses/${courseId}/assignments/`,
        method: 'POST',
        user: ADMIN_USER,
        body: { name },
    }).its('body').then(assignment => {
        const body = {};

        if (state !== undefined) {
            body.state = state;
        }

        if (deadline !== undefined) {
            if (deadline === 'tomorrow') {
                deadline = tomorrow();
            } else if (deadline === 'yesterday') {
                deadline = yesterday();
            }
            body.deadline = deadline;
        }

        if (bbZip) {
            cy.fixtureAsFile('test_blackboard/bb.zip', 'bb.zip', 'application/zip').then(bbZipFile => {
                const data = new FormData();
                data.append('file', bbZipFile);

                return cy.formRequest({
                    url: `/api/v1/assignments/${assignment.id}/submissions/`,
                    method: 'POST',
                    user: ADMIN_USER,
                    data,
                });
            });
        }

        if (Object.keys(body).length > 0) {
            return cy.patchAssignment(assignment.id, body);
        } else {
            return cy.wrap(assignment);
        }
    });
});

Cypress.Commands.add('patchAssignment', (assignmentId, props={}) => {
    const body = Object.assign({}, props);

    if (body.deadline === 'tomorrow') {
        body.deadline = tomorrow();
    } else if (body.deadline === 'yesterday') {
        body.deadline = yesterday();
    }

    if (body.state === 'submitting' || body.state === 'grading') {
        body.state = 'open';
    }

    cy.authRequest({
        url: `/api/v1/assignments/${assignmentId}`,
        method: 'PATCH',
        user: ADMIN_USER,
        body,
    }).its('body');
});

Cypress.Commands.add('tempPatchAssignment', (assignment, props, callback) => {
    const oldProps = Object.entries(assignment).reduce(
        (acc, [key, value]) => {
            if (Object.hasOwnProperty.call(props, key)) {
                acc[key] = value;
            }
            return acc;
        },
        {},
    );

    return cy.patchAssignment(assignment.id, props)
        .then(tempAssignment => {
            cy.reload();
            return callback(tempAssignment);
        })
        .then(() => cy.patchAssignment(assignment.id, oldProps));
});

Cypress.Commands.add('patchPeerFeedback', (assignmentId, settings) => {
    return cy.authRequest({
        url: `/api/v1/assignments/${assignmentId}/peer_feedback_settings`,
        method: settings == null ? 'DELETE' : 'PUT',
        user: ADMIN_USER,
        body: settings,
    });
});

Cypress.Commands.add('createSubmission', (assignmentId, fileName, opts={}) => {
    const { author, testSub } = opts;
    let url = `/api/v1/assignments/${assignmentId}/submission`;

    if (author) {
        url += `?author=${author}`;
    } else if (testSub) {
        url += '?is_test_submission';
    }

    return cy.fixtureAsFile(fileName, fileName, 'application/zip').then(file => {
        const data = new FormData();
        data.append('file', file);

        return cy.formRequest({
            url,
            method: 'POST',
            user: ADMIN_USER,
            data,
        }).its('response.body');
    });
});

Cypress.Commands.add('deleteSubmission', (submissionId) => {
    return cy.authRequest({
        url: `/api/v1/submissions/${submissionId}`,
        method: 'DELETE',
        user: ADMIN_USER,
    });
});

Cypress.Commands.add('patchSubmission', (submissionId, body) => {
    return cy.authRequest({
        url: `/api/v1/submissions/${submissionId}`,
        method: 'PATCH',
        user: ADMIN_USER,
        body,
    }).its('body');
});

Cypress.Commands.add('clearRubricResult', (submissionId) => {
    return cy.authRequest({
        url: `/api/v1/submissions/${submissionId}/rubricitems/`,
        method: 'PATCH',
        user: ADMIN_USER,
        body: {
            items: [],
        },
    }).its('body');
});

Cypress.Commands.add('createRubric', (assignmentId, rubricData, maxPoints = null) => {
    return cy.authRequest({
        url: `/api/v1/assignments/${assignmentId}/rubrics/`,
        method: 'PUT',
        user: ADMIN_USER,
        body: {
            rows: rubricData,
            max_points: maxPoints,
        },
    }).its('body');
});

Cypress.Commands.add('deleteRubric', (assignmentId, opts={}) => {
    return cy.authRequest({
        url: `/api/v1/assignments/${assignmentId}/rubrics/`,
        method: 'DELETE',
        user: ADMIN_USER,
        ...opts,
    });
});

Cypress.Commands.add('createAutoTest', (assignmentId, autoTestConfig) => {
    const patchProps = Object.entries(autoTestConfig).reduce((acc, [key, val]) => {
        if (key == 'grade_calculation' || key == 'results_always_visible') {
            acc[key] = val;
        }
        return acc;
    }, {});
    return cy.authRequest({
        url: '/api/v1/auto_tests/',
        method: 'POST',
        user: ADMIN_USER,
        body: {
            assignment_id: assignmentId,
        },
    }).its('body').then(autoTest => {
        if (Object.keys(patchProps).length > 0) {
            cy.authRequest({
                url: `/api/v1/auto_tests/${autoTest.id}`,
                method: 'PATCH',
                user: ADMIN_USER,
                body: patchProps,
            });
        }
        return cy.wrap(autoTestConfig.sets).each(setConfig =>
            cy.authRequest({
                url: `/api/v1/auto_tests/${autoTest.id}/sets/`,
                method: 'POST',
                user: ADMIN_USER,
            }).its('body').then(set =>
                cy.authRequest({
                    url: `/api/v1/auto_tests/${autoTest.id}/sets/${set.id}`,
                    method: 'PATCH',
                    user: ADMIN_USER,
                    body: { stop_points: setConfig.stop_points },
                }).then(() =>
                    cy.wrap(setConfig.suites).each(suiteConfig =>
                        cy.authRequest({
                            url: `/api/v1/auto_tests/${autoTest.id}/sets/${set.id}/suites/`,
                            method: 'PATCH',
                            user: ADMIN_USER,
                            body: suiteConfig,
                        }),
                    ),
                ),
            ),
        ).then(() =>
            // Get the object again so we're sure we have the latest.
            cy.authRequest({
                url: `/api/v1/auto_tests/${autoTest.id}`,
                method: 'GET',
                user: ADMIN_USER,
            }).its('body'),
        );
    });
});

Cypress.Commands.add('createAutoTestFromFixture', (assignmentId, autoTest, rubric) => {
    // Since AutoTest categories must map to a rubric category, we must know
    // the rubric row's id in advance before we can submit the AutoTest config.
    // This function loads a fixture from the test_auto_tests fixture
    // subdirectory and patches its rubric row ids with the ones in the given
    // rubric. The rubric row ids in the fixture represent rubric row indices.

    cy.fixture(`test_auto_tests/${autoTest}.json`).then(autoTestConfig => {
        autoTestConfig.sets.forEach(set => {
            set.suites.forEach(suite => {
                const idx = suite.rubric_row_id;
                suite.rubric_row_id = rubric[idx].id;
            });
        });
        return cy.createAutoTest(assignmentId, autoTestConfig);
    });
});

Cypress.Commands.add('deleteAutoTest', (autoTestId) => {
    return cy.authRequest({
        url: `/api/v1/auto_tests/${autoTestId}`,
        method: 'DELETE',
        user: ADMIN_USER,
    });
});

Cypress.Commands.add('createGroupSet', (courseId, minSize=1, maxSize=1) => {
    return cy.authRequest({
        url: `/api/v1/courses/${courseId}/group_sets/`,
        method: 'PUT',
        user: ADMIN_USER,
        body: {
            minimum_size: minSize,
            maximum_size: maxSize,
        },
    }).its('body');
});

Cypress.Commands.add('connectGroupSet', (courseId, assignmentId, minSize=1, maxSize=1) => {
    cy.createGroupSet(courseId, minSize, maxSize).then(
        groupSet => cy.patchAssignment(assignmentId, {
            group_set_id: groupSet.id,
        }),
    );
});

Cypress.Commands.add('disconnectGroupSet', (assignmentId) => {
    return cy.patchAssignment(assignmentId, {
        group_set_id: null,
    });
});

Cypress.Commands.add('joinGroup', (groupSetId, username) => {
    return cy.authRequest({
        url: `/api/v1/group_sets/${groupSetId}/group`,
        method: 'POST',
        user: ADMIN_USER,
        body: { member_ids: [] },
    }).its('body').then(
        group => cy.authRequest({
            url: `/api/v1/groups/${group.id}/member`,
            method: 'POST',
            user: ADMIN_USER,
            body: { username },
        }),
    );
});

Cypress.Commands.add('openCategory', (name) => {
    return cy.get('.local-header .categories')
        .contains('.category', name)
        .click()
        .should('have.class', 'selected');
});

Cypress.Commands.add('containsAll', { prevSubject: true }, (subject, msgs) => {
    return cy.wrap(subject).text().then($text => {
        for (let msg of msgs) {
            cy.wrap($text).should('contain', msg);
        }
        return cy.wrap(subject);
    });
});

Cypress.Commands.add('shouldNotOverflow', { prevSubject: true }, (subject) => {
    return cy.wrap(subject).each($el =>
        cy.wrap($el)
            .should('be.visible')
            .then(() => {
                const { scrollWidth, clientWidth } = $el.get(0);
                expect(scrollWidth).to.be.at.most(clientWidth);
            }),
    );
});

Cypress.Commands.add('setText', { prevSubject: true }, (subject, text) => {
    // Clear the input and type `text` if it is a nonempty string.
    const toWrite = `{selectall}{backspace}${text  || ''}`;
    return cy.wrap(subject).clear().type(toWrite);
});

// Click a submit button, and optionally wait for its state to return back to
// default.
Cypress.Commands.add('submit', { prevSubject: true }, (subject, state, optsArg = {}) => {
    const opts = Object.assign({
        popoverMsg: '',
        hasConfirm: false,
        doConfirm: true,
        confirmInModal: false,
        confirmMsg: '',
        waitForState: true,
        waitForDefault: true,
        warningCallback: () => {},
        confirmCallback: null,
    }, optsArg);

    if (!Array.isArray(opts.popoverMsg)) {
        opts.popoverMsg = [opts.popoverMsg];
    }

    if (!Array.isArray(opts.confirmMsg)) {
        opts.confirmMsg = [opts.confirmMsg];
    }

    // Ensure this is a submit button.
    cy.wrap(subject).should('have.class', 'submit-button');
    cy.wrap(subject).click();

    if (opts.confirmCallback) {
        cy.get(`.popover .submit-button-confirm`).then(opts.confirmCallback);
    }

    // Click a button the confirm popover.
    if (opts.hasConfirm) {
        if (opts.confirmInModal) {
            const id = subject.get(0).id;
            cy.get(`#${id}-modal`)
                .should('have.class', 'show')
                .should('be.visible')
                .containsAll(opts.confirmMsg)
                .contains('.btn:visible', opts.doConfirm ? 'Confirm' : 'Cancel')
                .click();
            cy.get(`#${id}-modal`)
                .should('not.exist');
        } else {
            cy.get('.popover .submit-button-confirm')
                .containsAll(opts.confirmMsg)
                .should('be.visible')
                .contains('.btn:visible', opts.doConfirm ? 'Yes' : 'No')
                .click();
            cy.get('.popover .submit-button-confirm').should('not.be.visible');
            cy.get('.popover .submit-button-confirm').should('not.exist');
        }

        if (!opts.doConfirm) {
            return cy.wrap(subject);
        }
    }

    if (!opts.waitForState) {
        return cy.wrap(subject);
    }

    cy.wrap(subject).should('have.class', `state-${state}`);

    if (state === 'warning') {
        cy.get(`.popover .submit-button-${state}`).then(opts.warningCallback);
    }

    // Close the error/warning popover.
    if (state === 'error' || state === 'warning') {
        cy.get(`.popover .submit-button-${state}`)
            .containsAll(opts.popoverMsg)
            .find('.hide-button')
            .click();
        cy.get(`.popover .submit-button-${state}`).should('not.be.visible')
        cy.get(`.popover .submit-button-${state}`).should('not.exist');
    }

    if (opts.waitForDefault) {
        cy.wrap(subject).should('have.class', 'state-default');
    }

    return cy.wrap(subject);
});

Cypress.Commands.add('multiselect', { prevSubject: true }, (subject, items) => {
    // Select items in a <multiselect>. Each item is typed in the multiselect
    // and then the first matching item is selected. Fails if no matching items
    // could be found.

    cy.wrap(items).each(item => {
        cy.wrap(subject)
            .should('have.class', 'multiselect')
            .find('input')
            .type(item);
        cy.wrap(subject)
            .find('.multiselect__element')
            .first()
            .click();
    });
});

Cypress.Commands.add('parentsUpto', { prevSubject: true }, (subject, selector) => {
    // Similar to the builtin parentsUntil, but selects the parent that matches
    // the selector instead of the last parent that doesn't.
    return cy.wrap(subject).parentsUntil(selector).parent();
});

Cypress.Commands.add('shouldReload', fn => {
    // Check that executing the given function causes a page reload.

    // Set a property on window that will be gone after the reload.
    cy.window().should('not.have.property', 'beforeReload');
    cy.window().then(w => w.beforeReload = true);
    cy.window().should('have.property', 'beforeReload', true);

    fn();

    cy.window().should('not.have.property', 'beforeReload');
});

//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This is will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... })

// Cypress.Commands.add('url', 'http://localhost:8080')
