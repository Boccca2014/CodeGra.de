context('Manage assignment page', () => {
    let course;
    let assignment;
    let assignmentCopy;

    function createRubric() {
        cy.createRubric(assignment.id, [
            {
                header: 'Category 1',
                description: 'Category 1',
                items: [
                    { points: 0, header: '0 points', description: '0 points' },
                    { points: 1, header: '1 points', description: '1 points' },
                    { points: 2, header: '2 points', description: '2 points' },
                    { points: 3, header: '3 points', description: '3 points' },
                ],
            },
            {
                header: 'Category 2',
                description: 'Category 2',
                items: [
                    { points: 0, header: '0 points', description: '0 points' },
                    { points: 1, header: '1 points', description: '1 points' },
                    { points: 2, header: '2 points', description: '2 points' },
                    { points: 3, header: '3 points', description: '3 points' },
                ],
            },
            {
                header: 'Category 3',
                description: 'Category 3',
                items: [
                    { points: 0, header: '0 points', description: '0 points' },
                    { points: 1, header: '1 points', description: '1 points' },
                    { points: 2, header: '2 points', description: '2 points' },
                    { points: 3, header: '3 points', description: '3 points' },
                ],
            },
        ]);
        cy.reload();
    }

    before(() => {
        cy.visit('/');
        cy.login('admin', 'admin');

        const students = [
            { name: 'Student1', role: 'Student' },
            { name: 'Student2', role: 'Student' },
            { name: 'Student3', role: 'Student' },
            { name: 'Student4', role: 'Student' },
        ];

        cy.createCourse('AutoTest', students).then(res => {
            course = res;

            return cy.createAssignment(course.id, 'AutoTest', {
                state: 'open',
                deadline: 'tomorrow',
            });
        }).then(res => {
            assignment = res;

            return cy.createAssignment(course.id, 'Copy - AutoTest', {
                state: 'open',
                deadline: 'tomorrow',
            });
        }).then(res => {
            assignmentCopy = res;

            return cy.wrap(students).each(student => {
                return cy.createSubmission(
                    assignment.id,
                    'test_submissions/all_filetypes.zip',
                    { author: student.name },
                );
            });
        }).then(() => {
            cy.visit(`/courses/${course.id}/assignments/${assignment.id}`);
            cy.openCategory('AutoTest', { timeout: 8000 });
        });
    });

    context('Creating an AutoTest configuration', () => {
        beforeEach(() => {
            cy.login('admin', 'admin');
        });

        after(() => {
            // Delete the AT config.
            cy.visit(`/courses/${course.id}/assignments/${assignment.id}`);
            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Delete')
                .submit('success', { waitForDefault: false, hasConfirm: true });
        });

        it('should not be possible to create an AutoTest when there is no rubric', () => {
            cy.openCategory('Rubric');
            cy.get('.rubric-editor')
                .should('contain', 'Create new rubric');

            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('be.disabled');
        });

        it('should be possible to create an AutoTest when there is a rubric', () => {
            createRubric();

            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.be.disabled')
                .submit('success', { waitForDefault: false });

            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.exist');

            cy.get('.auto-test')
                .contains('.submit-button', 'Delete')
                .submit('success', { hasConfirm: true, waitForDefault: false });

            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.be.disabled');

            cy.openCategory('Rubric');
            cy.get('.rubric-editor')
                .find('.submit-button.delete-rubric')
                .submit('success', {
                    hasConfirm: true,
                    confirmInModal: true,
                    waitForDefault: false,
                });

            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('be.disabled');
        });

        it('should not be possible to accidentally delete things', () => {
            createRubric();

            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .submit('success', { waitForDefault: false });
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.exist');

            cy.get('.auto-test')
                .contains('.submit-button', 'Add level')
                .submit('success');
            cy.get('.auto-test')
                .contains('Add category')
                .submit('success');
            cy.get('.modal-dialog')
                .contains('button', 'Run Program')
                .click();

            function submit(context, btnText='', btnClass='') {
                context = cy.get(context);
                btnClass = `.submit-button${btnClass}`;

                (btnText ?  context.contains(btnClass, btnText) : context.find(btnClass))
                    .submit('default', {
                        hasConfirm: true,
                        waitForState: false,
                    })
                    .should('not.exist');
            }

            submit('.modal-dialog', '', '.delete-step');
            cy.get('.modal-dialog .auto-test-step').should('not.exist')
            submit('.modal-dialog', 'Delete');
            submit('.auto-test', 'Delete level');
            submit('.auto-test', 'Delete');
        });

        it('should be possible to copy an AutoTest', () => {
            // First make sure that there is an AT to import
            createRubric();
            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .submit('success', { waitForDefault: false });

            cy.visit(`/courses/${course.id}/assignments/${assignmentCopy.id}`);
            cy.openCategory('Rubric');
            cy.get('.rubric-editor')
                .should('contain', 'Create new rubric');

            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('exist');
            cy.get('.auto-test .copy-at-wrapper .multiselect')
                .multiselect([`${course.name} - AutoTest`]);
            cy.get('.auto-test .copy-at-wrapper .submit-button')
                .submit('success', { waitForDefault: false });
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.exist');

            cy.openCategory('Rubric');
            cy.get('.rubric-editor')
                .contains('Create new rubric')
                .should('not.exist');
        });
    });

    context('Running an AutoTest', () => {
        before(() => {
            cy.login('admin', 'admin');

            createRubric();

            cy.openCategory('AutoTest');
            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .submit('success', { waitForDefault: false })
                .should('not.exist');
        });

        after(() => {
            // Stop the run if it wasn't already stopped.
            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Stop')
                .then($btn => {
                    if (!$btn.get(0).disabled) {
                        return cy.wrap($btn).submit('success', { hasConfirm: true });
                    }
                });
            // Delete the AT config.
            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Delete')
                .submit('success', { waitForDefault: false, hasConfirm: true });
        });

        it('should not be possible if no categories have been created', () => {
            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Start')
                .should('be.disabled');

            // TODO: Check that the popover on the start button mentions that
            // there are no categories.

            cy.get('.auto-test-sets')
                .contains('.submit-button', 'Add level')
                .click();
            cy.get('.auto-test-set')
                .contains('.submit-button', 'Add category')
                .click();
            cy.get('.edit-suite-modal')
                .contains('.dropdown-toggle', 'Select a rubric category')
                .click();
            cy.get('.edit-suite-modal')
                .contains('.dropdown-menu li', 'Category 1')
                .click();
            cy.get('.edit-suite-modal')
                .contains('.add-step-btn', 'Run Program')
                .click();
            cy.get('.edit-suite-modal .name-input input')
                .type('Step 1');
            cy.get('.edit-suite-modal input.step-program')
                .type('true');
            cy.get('.edit-suite-modal')
                .contains('.submit-button', 'Save')
                .submit('success', { waitForState: false });

            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Start')
                .should('not.be.disabled');
        });

        it('should remove the run if it was deleted from somewhere else', () => {
            cy.get('.auto-test-run')
                .should('not.exist');
            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Start')
                .submit('success');
            cy.get('.auto-test-run')
                .should('exist')
                .find('.results-table tbody tr')
                .should('have.length', 4);

            cy.server();
            cy.route({
                url: '/api/v1/auto_tests/*/runs/*',
                method: 'GET',
            }).as('getRunRoute');

            // Delete the run. This uses the fact that the DELETE route for
            // a run is the same as the GET route, because we do not have
            // information about the run, specifically the autotest id and the
            // run id.
            cy.wait('@getRunRoute').then(res => {
                cy.authRequest({
                    url: res.url.replace(/\?.*/, ''),
                    method: 'DELETE',
                });
            });

            cy.wait('@getRunRoute', { requestTimeout: 7500 }).then(res => {
                expect(res.status).to.equal(404);
            });

            cy.get('.auto-test-run')
                .should('not.exist');
            cy.get('.auto-test .alert.run-deleted')
                .should('exist');
        });

        it('should not throw an error when viewing a single result while the author creates a new submission', () => {
            cy.get('.auto-test-run')
                .should('not.exist');
            cy.get('.auto-test')
                .contains('.card-header', 'Configuration')
                .contains('.submit-button', 'Start')
                .submit('success');
            cy.get('.auto-test-run')
                .should('exist')
                .find('.results-table tbody tr')
                .should('have.length', 4)
                .first()
                .as('firstResult');
            cy.get('@firstResult')
                .find('span.name-user')
                .text()
                .then(text => text.trim())
                .as('username');
            cy.get('@firstResult')
                .click();

            cy.server();
            cy.route({
                url: '/api/v1/auto_tests/*/runs/*/results/*',
                method: 'GET',
            }).as('getResultRoute');

            // Wait until we have loaded the result before creating a new
            // submission.
            cy.wait('@getResultRoute');
            cy.wait('@getResultRoute', { requestTimeout: 7500 });
            cy.get('@username').then(username => {
                cy.log('username', username);
                cy.createSubmission(
                    assignment.id,
                    'test_submissions/all_filetypes.zip',
                    { author: username },
                );
            });

            // Wait until we have tried to load the result again.
            cy.wait('@getResultRoute', { requestTimeout: 7500 }).then(res => {
                expect(res.response.body.state).to.equal('skipped');
            });

            // Check that the result state is updated to "skipped".
            cy.get('.auto-test-result-modal')
                .contains('.card-header', 'Setup')
                .find('.auto-test-state')
                .should('contain', 'Skipped');

            // Close the modal and wait until it's gone.
            cy.get('.auto-test-result-modal')
                .find('.modal-header .close')
                .click();
            cy.get('.auto-test-result-modal')
                .should('not.exist');

            // Check that there are no extra entries in the results list and
            // that the student is now last in the queue.
            cy.get('@username').then(username => {
                cy.get('.auto-test-run')
                    .contains('tbody tr', username)
                    .should('have.length', 1);
                cy.get('.auto-test-run tbody tr')
                    .last()
                    .should('contain', username);
            });
        });
    });
});
