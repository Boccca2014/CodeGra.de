context('Submissions page', () => {
    let course;
    let assignments = {};

    function createRubric(assigId) {
        return cy.createRubric(assigId, [
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
        ]).then(() => {
            cy.reload();
        });
    }

    function visitSubmissions(assignment=null) {
        const id = (assignment || assignments.withSubs).id;
        cy.visit(`/courses/${course.id}/assignments/${id}/submissions`);

        return cy.url().should('contain', '/submissions');
    }

    function getStudent(name, outer=false) {
        const inner = cy.get('.submissions-table .user').contains(name);
        if (outer) {
            return inner.parentsUntil('tbody').last();
        }
        return inner;
    }

    function giveGrade(name, grade) {
        getStudent(name).click();
        cy.get('.grade-viewer input[name=grade-input]').clear();
        if (grade != null) {
            cy.get('.grade-viewer input[name=grade-input]').type(`${grade}`);
        }
        cy.get('.grade-viewer .submit-grade-btn').submit('success');
        visitSubmissions();
    }

    before(() => {
        const users = [
            { name: 'robin',    role: 'TA' },
            { name: 'student1', role: 'Student' },
            { name: 'student2', role: 'Student' },
            { name: 'student3', role: 'Student' },
            { name: 'student4', role: 'Student' },
        ];

        cy.visit('/')

        cy.createCourse('SubmissionsPage', users).then(res => {
            course = res;

            return cy.createAssignment(course.id, 'With Submissions', {
                state: 'open',
                deadline: 'tomorrow',
            });
        }).then(res => {
            assignments.withSubs = res;

            return cy.createAssignment(course.id, 'Without Submissions', {
                state: 'open',
                deadline: 'tomorrow',
            });
        }).then(res => {
            assignments.withoutSubs = res;
            return cy.wrap(users).each(
                author => cy.createSubmission(
                    assignments.withSubs.id,
                    'test_submissions/hello.py',
                    { author: author.name },
                ),
            );
        });
    });

    context('As a teacher', () => {
        beforeEach(() => {
            cy.login('admin', 'admin');
            visitSubmissions();
        })

        it('should be on the submissions page', () => {
            cy.url().should('contain', 'submissions');
            cy.get('.submissions-table').should('exist');
        })

        it('should have a button to go to the assignment management page', () => {
            cy.get('.manage-assignment-button')
                .should('exist')
                .click();
            cy.url().should('not.contain', '/submissions');
        });

        it('should show a message when the assignment does not exist', () => {
            cy.visit(`/courses/${course.id}/assignments/1000000000/submissions`);
            cy.get('.page.submissions').within(() => {
                cy.get('.local-header .title').should('contain', 'Unknown assignment');
                cy.get('.cat-container .alert-danger')
                    .should('contain', 'The requested assignment does not exist or you do not have permission');
            });
        });

        it('should not show a grade by default', () => {
            cy.createSubmission(
                assignments.withSubs.id,
                'test_submissions/hello.py',
                { author: 'student1' },
            ).then(() => {
                cy.reload();
                cy.get('input[name="submissions-filter"]')
                    .type('Student1');

                getStudent('Student1', true)
                    .find('.submission-grade')
                    .contains('-');
                giveGrade('Student1', 5.0101);
                getStudent('Student1', true)
                    .find('.submission-grade')
                    .contains('5.01');
            });
        });

        it('should not be assigned by default', () => {
            getStudent('Student1', true)
                .find('.assigned-to-grader select')
                .should('have.value', '')
                .should('contain', '-');
            cy.get('.cat-container .assigned-to-me-option')
                .should('not.exist');

            getStudent('Student1', true)
                .find('.assigned-to-grader select')
                .select('admin')
                .should('contain', 'admin');
            cy.get('.cat-container .assigned-to-me-option')
                .should('be.visible');

            getStudent('Student2').should('exist');
            cy.get('.cat-container .assigned-to-me-option').click();
            getStudent('Student2').should('not.exist');

            getStudent('Student1', true)
                .find('.assigned-to-grader select')
                .select('-');
            cy.get('.cat-container .assigned-to-me-option')
                .should('not.exist');
            getStudent('Student2').should('exist');
        });

        it('should indicate which students submitted work after the deadline', () => {
            cy.patchAssignment(assignments.withSubs.id, {
                deadline: 'yesterday',
            });
            cy.createSubmission(assignments.withSubs.id, 'test_submissions/hello.py', {
                author: 'student1',
            });
            cy.reload().then(() => {
                getStudent('Student1', true)
                    .should('have.class', 'table-danger')
                    .find('.late-submission-icon')
                    .should('exist');
            });
        });

        it('should indicate when a student also has a group submission', () => {
            const assigId = assignments.withSubs.id;

            cy.patchAssignment(assigId, { deadline: 'tomorrow' });
            cy.createSubmission(assigId, 'test_submissions/hello.py', { author: 'student1' });
            cy.connectGroupSet(course.id, assigId).then(
                assig => cy.joinGroup(assig.group_set.id, 'student1'),
            );
            cy.createSubmission(assigId, 'test_submissions/hello.py', { author: 'student1' })
                .then(sub => {
                    cy.log('submission', sub);
                    cy.reload().then(() => {
                        // Can't use getStudent('Student1') here because it may find
                        // the row of the student's group's submission.
                        cy.get('tr.table-warning')
                            .should('contain', 'Student1');
                    }).then(() => {
                        cy.deleteSubmission(sub.id);
                    });
                });
        });

        context('Categories', () => {
            it('should show the "Submissions" tab by default', () => {
                cy.get('.local-header .categories')
                    .contains('.category', 'Submissions')
                    .should('have.class', 'selected');
            });

            it('should show a tab for the rubric', () => {
                cy.get('.submissions-table').should('exist');

                cy.openCategory('Rubric');
                cy.get('.cat-container')
                    .should('contain', 'There is no rubric for this assignment');

                createRubric(assignments.withSubs.id).then(() => {
                    cy.get('.rubric-editor')
                        .should('exist')
                        .should('not.have.class', 'editable');

                    cy.deleteRubric(assignments.withSubs.id);
                });
            });

            it('should show a tab for the CSV export', () => {
                cy.get('.submissions-table').should('exist');

                cy.openCategory('Export');
            });

            it('should show a tab for groups management if this is a group assignment', () => {
                cy.disconnectGroupSet(assignments.withSubs.id);
                cy.reload();

                cy.get('.local-header .categories .category')
                    .each($cat => {
                        cy.wrap($cat).should('not.contain', 'Groups');
                    });

                cy.connectGroupSet(course.id, assignments.withSubs.id).then(() => {
                    cy.reload();
                    cy.get('.submissions-table').should('exist');

                    cy.openCategory('Groups');
                    cy.get('.cat-container')
                        .should('contain', 'There are no groups yet');
                });
            });
        });

        context('Filtering', () => {
            function filterSubmissions(filter) {
                return cy.get('.search-wrapper input[name="submissions-filter"]')
                    .clear()
                    .type(filter);
            }

            it('should be possible to filter', () => {
                getStudent('Student1').should('exist');
                getStudent('Student2').should('exist');

                filterSubmissions('Student2{enter}');
                getStudent('Student1').should('not.exist');
                getStudent('Student2').should('exist');

                // Make sure search bar is saved in url
                cy.reload();
                getStudent('Student1').should('not.exist');
                getStudent('Student2').should('exist');

                getStudent('Student2').click();
                cy.get('.submission-nav-bar').should('contain', 'Student2');
                cy.get('.file-viewer .inner-viewer').should('be.visible');

                cy.get('.sidebar').contains('.sidebar-entry', 'Submissions').click();
                cy.get('.sidebar .submissions-sidebar-list').should('be.visible');
                cy.get('.sidebar-filter input').should('have.value', 'Student2');
                cy.get('.sidebar-list').should('contain', 'Student2');
                cy.get('.sidebar-list').should('not.contain', 'Student1');
                cy.get('.sidebar .back-button').click();

                // Even when navigating to submission
                cy.get('.local-header .back-button').click();
                getStudent('Student1').should('not.exist');
                getStudent('Student2').should('exist');
            });

            it('should update the number of visible submissions at the bottom of the table', () => {
                getStudent('Robin').should('exist');
                getStudent('Student1').should('exist');
                getStudent('Student2').should('exist');
                getStudent('Student3').should('exist');
                getStudent('Student4').should('exist');

                cy.get('.submissions-table .submission-count').as('count');
                cy.get('@count').should('contain', '5 out of 5');
                filterSubmissions('Student');
                cy.get('@count').should('contain', '4 out of 5');
                filterSubmissions('Robin');
                cy.get('@count').should('contain', '1 out of 5');
                filterSubmissions('Robinnnnnnnnnnnnnnn');
                cy.get('@count').should('contain', '0 out of 5');

                visitSubmissions(assignments.withoutSubs);
                cy.get('@count').should('contain', '0 out of 0');
            });

            it('should show a message when there are no submissions', () => {
                visitSubmissions(assignments.withoutSubs);

                cy.get('.submissions-table .b-table-empty-row')
                    .should('contain', 'There are no submissions yet');
            });

            it('should show a message when no submissions match the filter', () => {
                getStudent('Robin').should('exist');
                filterSubmissions('xyz');

                cy.get('.submissions-table .b-table-empty-row')
                    .should('contain', 'No submissions found with the given filters');

                visitSubmissions(assignments.withoutSubs);
                filterSubmissions('xyz');

                cy.get('.submissions-table .b-table-empty-row')
                    .should('contain', 'There are no submissions yet');
            });

            it('should be kept when going to a submission and back', () => {
                filterSubmissions('Student2');
                cy.url().should('match', /[?&]q=Student2/);

                getStudent('Student2').click();
                cy.url()
                    .should('match', /submissions\/\d+/)
                    .and('match', /[?&]search=Student2/);
            });

            it('should be used in the navbar on the submission page', () => {
                filterSubmissions('Student');

                cy.get('.submissions-table tbody tr td:first-child')
                    .then($el => $el.get().map(el => el.textContent.trim()))
                    .as('users');
                cy.get('.submissions-table tbody tr:first').click();

                cy.get('.submission-nav-bar .btn.prev').should('be.disabled');

                cy.get('@users').each((user, i, list) => {
                    cy.get('.submission-nav-bar').should('contain', user);

                    if (i < list.length - 1) {
                        cy.get('.submission-nav-bar .btn.next').click();
                    } else {
                        cy.get('.submission-nav-bar .btn.next').should('be.disabled');
                    }
                });
            });
        });

        context('Sorting', () => {
            function gradeOrder(order) {
                const els = cy.get('.submission-grade').each((item, index) => {
                    cy.wrap(item).contains(order[index]);
                });
            }

            before(() => {
                cy.login('admin', 'admin');
                visitSubmissions();

                giveGrade('Robin', 0);
                giveGrade('Student4', 1);
                giveGrade('Student3', 5);
                giveGrade('Student2', 10);
                giveGrade('Student1', null);
            });

            it('should sort correctly', () => {
                cy.get('.submissions-table thead').contains('Grade').click();
                gradeOrder(['-', '0.00', '1.00', '5.00', '10.00']);

                cy.get('.submissions-table thead').contains('Grade').click();
                gradeOrder(['10.00', '5.00', '1.00', '0.00', '-']);
            })

            it('should be kept when going to a submission and back', () => {
                cy.get('.submissions-table thead').contains('Grade').click();
                cy.url()
                    .should('match', /[?&]sortBy=grade/)
                    .should('match', /[?&]sortAsc=true/);

                getStudent('Student2').click();
                cy.get('.file-viewer')
                    .should('be.visible');
                cy.url()
                    .should('match', /[?&]sortBy=grade/)
                    .should('match', /[?&]sortAsc=true/);

                cy.get('.local-header .back-button').click();
                cy.get('.submissions-table')
                    .should('be.visible')
                cy.url()
                    .should('match', /[?&]sortBy=grade/)
                    .should('match', /[?&]sortAsc=true/);
                gradeOrder(['-', '0.00', '1.00', '5.00', '10.00']);
            });

            it('should be kept when going to a submission and back after a page reload', () => {
                cy.get('.submissions-table thead').contains('Grade').click();
                cy.url()
                    .should('match', /[?&]sortBy=grade/)
                    .should('match', /[?&]sortAsc=true/);

                cy.reload();

                cy.get('.submissions-table')
                    .should('be.visible')
                    .find('tbody tr')
                    .first()
                    .click();

                cy.get('.file-viewer')
                    .should('be.visible');
                cy.url()
                    .should('match', /[?&]sortBy=grade/)
                    .should('match', /[?&]sortAsc=true/);

                cy.get('.local-header .back-button').click();
                cy.get('.submissions-table')
                    .should('be.visible')
                cy.url()
                    .should('match', /[?&]sortBy=grade/)
                    .should('match', /[?&]sortAsc=true/);
            });

            it('should be used in the navbar on the submission page', () => {
                cy.get('.submissions-table thead').contains('Grade').click();
                cy.get('.submissions-table tbody tr td:first-child')
                    .then($el => $el.get().map(el => el.textContent.trim()))
                    .as('users');
                cy.get('.submissions-table tbody tr:first').click();

                cy.get('.submission-nav-bar .btn.prev').should('be.disabled');

                cy.get('@users').each((user, i, list) => {
                    cy.get('.submission-nav-bar').should('contain', user);

                    if (i < list.length - 1) {
                        cy.get('.submission-nav-bar .btn.next').click();
                    } else {
                        cy.get('.submission-nav-bar .btn.next').should('be.disabled');
                    }
                });
            });

            it('should sort based on creation date correct', () => {
                cy.createSubmission(
                    assignments.withSubs.id,
                    'test_submissions/hello.py',
                    { author: 'student2' },
                ).then(() => {
                    return cy.createSubmission(
                        assignments.withSubs.id,
                        'test_submissions/hello.py',
                        { author: 'student1' });
                }).then(() => {
                    cy.get('.local-header .submit-button[name="refresh-button"]').click();

                    // TODO: Don't sort oldest first when clicking the label the
                    // first time.
                    cy.get('.submissions-table thead').contains('Created at').click();
                    cy.get('.submissions-table thead').contains('Created at').click();
                    cy.get('tbody tr:first-child').contains('Student1');
                    cy.get('tbody tr:nth-child(2)').contains('Student2');

                    cy.get('.submissions-table thead').contains('Created at').click();
                    cy.get('tbody tr:last-child').contains('Student1');
                    cy.get('tbody tr:nth-last-child(2)').contains('Student2');

                    // This should become the new latest submission, so it
                    // should be last in the list.
                    return cy.createSubmission(
                        assignments.withSubs.id,
                        'test_submissions/hello.py',
                        { author: 'student4' },
                    );
                }).then(() => {
                    cy.get('.local-header .submit-button[name="refresh-button"]').click();
                    cy.get('.local-header .submit-button[name="refresh-button"]').should('not.be.disabled');
                    cy.get('tbody tr:last-child').contains('Student4');
                    // Show be the same after a reload
                    cy.reload();
                    cy.get('tbody tr:last-child').contains('Student4');
                });
            });
        });
    });

    context('As a student', () => {
        function loginStudent() {
            return cy.login('student1', 'Student1').then(() => {
                visitSubmissions();
            });
        }

        function getAction(name) {
            return cy.get('.wizard-buttons')
                .contains('.wizard-button', name);
        }

        function doAction(name) {
            return getAction(name).click();
        }

        function goBack(opts) {
            return cy.get('.local-header .back-button', opts).click();
        }

        beforeEach(() => {
            loginStudent();;
        });

        it('should be on the submissions page', () => {
            cy.url().should('contain', 'submissions');
            cy.get('.submissions-table').should('not.exist');
            cy.get('.wizard-buttons').should('exist');
        })

        it('should not have a button to go to the assignment management page', () => {
            cy.get('.manage-assignment-button').should('not.exist');
        });

        it('should show a message when the assignment does not exist', () => {
            cy.visit(`/courses/${course.id}/assignments/1000000000/submissions`);
            cy.get('.page.submissions').within(() => {
                cy.get('.local-header .title').should('contain', 'Unknown assignment');
                cy.get('.cat-container .alert-danger')
                    .should('contain', 'The requested assignment does not exist or you do not have permission');
            });
        });

        it('should show a message when the assignment is hidden', () => {
            cy.tempPatchAssignment(assignments.withSubs, { state: 'hidden' }, () => {
                visitSubmissions();
                cy.get('.page.submissions').within(() => {
                    cy.get('.local-header .title').should('contain', 'Unknown assignment');
                    cy.get('.cat-container .alert-danger')
                        .should('contain', 'The requested assignment does not exist or you do not have permission');
                });
            });
        });

        context('Action buttons', () => {
            it('should not show the category selector', () => {
                cy.get('.local-header .categories')
                    .should('exist')
                    .should('not.be.visible');
            });

            it('should show a back button on all the second-level pages', () => {
                const assigId = assignments.withSubs.id;

                cy.login('admin', 'admin');
                cy.patchAssignment(assigId, {
                    webhook_upload_enabled: true,
                });
                createRubric(assigId);
                cy.connectGroupSet(course.id, assigId);
                loginStudent();

                doAction('Latest submission');
                goBack();

                doAction('Upload files');
                goBack();

                doAction('Set up Git');
                goBack({ timeout: 10000 });

                doAction('Rubric');
                goBack();

                doAction('Groups');
                goBack();
            });

            context('Latest submission', () => {
                it('should not be disabled when the student has submissions', () => {
                    getAction('Latest submission')
                        .should('not.be.disabled');
                    doAction('Latest submission');

                    cy.url().should('contain', '/files/');
                });

                it('should go to the latest submission', () => {
                    doAction('Latest submission');

                    cy.url()
                        .should('contain', '/files/')
                        .then($url => cy.createSubmission(
                                assignments.withSubs.id,
                                'test_submissions/hello.py',
                                { author: 'student1' },
                            ).then(
                                res => [$url, res],
                            ),
                        ).then(([$url, newSub]) => {
                            visitSubmissions();
                            doAction('Latest submission');

                            cy.url()
                                .should('contain', '/files/')
                                .should('not.eq', $url);
                        });
                });

                it('should be disabled when the student has no submissions', () => {
                    visitSubmissions(assignments.withoutSubs);
                    getAction('Latest submission')
                        .should('be.disabled');
                });

                it('should not show a grade by default', () => {
                    cy.createSubmission(
                        assignments.withSubs.id,
                        'test_submissions/hello.py',
                    ).then(() => {
                        getAction('Latest submission')
                            .find('.grade')
                            .should('not.exist');
                    });
                });

                it('should show a grade when the assignment is done', () => {
                    cy.login('admin', 'admin');
                    giveGrade('Student1', 6.66);
                    cy.patchAssignment(assignments.withSubs.id, {
                        state: 'done',
                    });

                    loginStudent();
                    getAction('Latest submission')
                        .contains('p.grade', 'Grade')
                        .should('contain', '6.66');
                });

                it('should indicate whether the submission is late', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        deadline: 'yesterday',
                    });

                    cy.createSubmission(
                        assignments.withSubs.id,
                        'test_submissions/hello.py',
                        { author: 'student1' },
                    ).then(() => {
                        loginStudent();
                        getAction('Latest submission')
                            .should('have.class', 'btn-danger');
                    });
                });
            });

            context('Upload files', () => {
                it('should not be disabled when the assignment allows file uploads', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        deadline: 'tomorrow',
                        files_upload_enabled: true,
                    });

                    loginStudent();
                    doAction('Upload files');
                    cy.get('.submission-uploader').should('be.visible');
                });

                it('should be disabled when the assignment does not allow file uploads', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        files_upload_enabled: false,
                        webhook_upload_enabled: true,
                    });

                    loginStudent();
                    getAction('Upload files')
                        .should('be.disabled');
                });

                it('should be disabled when the assignment\'s deadline has passed', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        deadline: 'yesterday',
                    });

                    loginStudent();
                    getAction('Upload files')
                        .should('be.disabled');
                });
            });

            context('Set up Git', () => {
                it('should exist when the assignment allows webhook uploads', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        deadline: 'tomorrow',
                        files_upload_enabled: false,
                        webhook_upload_enabled: true,
                    });

                    loginStudent();
                    doAction('Set up Git');
                    cy.get('.webhook-instructions').should('be.visible');
                });

                it('should be disabled when the assignment\'s deadline has passed', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        deadline: 'yesterday',
                        webhook_upload_enabled: true,
                    });

                    loginStudent();
                    getAction('Set up Git')
                        .should('be.disabled');
                });

                it('should not exist when the assignment does not allow webhook uploads', () => {
                    cy.login('admin', 'admin');
                    cy.patchAssignment(assignments.withSubs.id, {
                        files_upload_enabled: true,
                        webhook_upload_enabled: false,
                    });

                    loginStudent();
                    getAction('Set up Git').should('not.exist');
                });
            });

            context('Rubric', () => {
                it('should exist when the assignment has a rubric', () => {
                    cy.login('admin', 'admin');
                    createRubric(assignments.withSubs.id);

                    loginStudent();
                    doAction('Rubric');
                    cy.get('.rubric-editor').should('exist');
                });

                it('should not exist when the assignment does not have a rubric', () => {
                    cy.login('admin', 'admin');
                    cy.deleteRubric(assignments.withSubs.id);

                    loginStudent();
                    getAction('Rubric').should('not.exist');
                });
            });

            context('Groups', () => {
                it('should exist when the assignment is a groups assignment', () => {
                    cy.login('admin', 'admin');
                    cy.connectGroupSet(course.id, assignments.withSubs.id);

                    loginStudent();
                    doAction('Groups');
                    cy.get('.groups-management').should('exist');
                });

                it('should not exist when the assignment is not a group assignment', () => {
                    cy.login('admin', 'admin');
                    cy.disconnectGroupSet(assignments.withSubs.id);

                    loginStudent();
                    getAction('Groups').should('not.exist');
                });
            });
        });
    });
});
