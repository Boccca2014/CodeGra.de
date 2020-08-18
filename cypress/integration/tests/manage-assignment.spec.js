context('Manage Assignment', () => {
    const unique = `ManageAssignment ${Math.floor(Math.random() * 10000)}`;
    let course;
    let assignment;

    before(() => {
        cy.visit('/');
        cy.createCourse(unique).then(res => {
            course = res;
            return cy.createAssignment(course.id, unique);
        }).then(res => {
            assignment = res;

            cy.login('admin', 'admin');
            cy.visit(`/courses/${course.id}/assignments/${assignment.id}`);
            cy.get('.page.manage-assignment').should('exist');
            cy.get('.page.manage-assignment .page-loader').should('not.exist');
            cy.openCategory('General');
        });
    });

    context('General', () => {
        it('should only change then name in the header after submit was clicked', () => {
            cy.get('.page.manage-assignment')
                .find('.local-header h4.title span')
                .as('header');
            cy.get('.page.manage-assignment')
                .contains('.form-group', 'Assignment name')
                .as('group');

            cy.get('@header').text().then((headerText) => {
                cy.get('@group').find('input').type('abc');
                cy.get('@header').text().should('not.contain', headerText + 'abc');
                cy.get('.assignment-general-settings').find('.submit-button').submit('success');
                cy.get('@header').text().should('contain', headerText + 'abc');
            });
        });

        it('should be possible to change the state', () => {
            cy.wrap(['hidden', 'open', 'done']).each(state => {
                cy.get(`.assignment-state .state-button.state-${state}`)
                    .submit('success', {
                        hasConfirm: true,
                        waitForState: false,
                    })
                    .should('have.class', 'state-default');
            });
        });

        it('should use the correct deadline after updating it', () => {
            cy.get('.assignment-deadline')
                .click({ force: true });
            cy.get('.flatpickr-calendar:visible .flatpickr-day:not(.prevMonthDay):not(.nextMonthDay).today')
                .click();
            cy.get('.flatpickr-calendar:visible input.flatpickr-hour:visible')
                .should('have.focus')
                .setText('23');
            cy.get('.flatpickr-calendar:visible input.flatpickr-minute:visible')
                .setText('59{enter}');
            cy.get('.assignment-general-settings .submit-button')
                .submit('success');
            cy.reload();

            cy.get('.local-header h4')
                .should('contain', (new Date()).toISOString().slice(0, 10))
                .should('contain', '23:59');
        });

        it('should be possible to upload a BB zip', () => {
            cy.get('.blackboard-zip-uploader').within(() => {
                cy.get('input[type=file]').uploadFixture('test_blackboard/bb.zip', 'application/zip');
                // Wait for submit button to go back to default.
                cy.get('.submit-button').submit('success');
            });
        });

        it('should be possible to set the max amount of submissions', () => {
            function setAliases() {
                cy.get('.form-group[id^="assignment-max-submissions-"]').as('maxSubs');
                cy.get('@maxSubs').find('input').as('input');
                cy.get('.assignment-submission-settings .submit-button').as('submit');
            }

            setAliases();

            cy.get('@input').type('5');
            cy.get('@submit').submit('success');
            cy.get('@input').should('have.value', '5');

            cy.get('.submission-uploader .submission-limiting').as('uploaderLimits');

            for (let i = 0; i < 2; ++i) {
                cy.get('@uploaderLimits').find('.loader').should('not.exist');
                cy.get('@uploaderLimits').text().should('contain', '5 submissions left out of 5.');

                // Should be the same after a reload
                if (i == 0) {
                    cy.reload();
                    setAliases();
                }
            }

            cy.get('@input').should('have.value', '5');
            cy.get('@input').clear();
            cy.get('@input').should('have.value', '');
            cy.get('@submit').submit('success');
            cy.get('.submission-uploader .submission-limiting').should('not.exist');

            cy.get('@input').clear().type('-10');
            cy.get('@maxSubs').find('.invalid-feedback').as('feedback');

            cy.get('@feedback')
                .should('be.visible')
                .should('contain', 'should be greater than or equal to 0');
            cy.get('@submit').should('be.disabled');

            cy.get('@input').clear();
            cy.get('@feedback').should('not.be.visible');
        });

        it('should be possible to update the cool off period', () => {
            function setAliases() {
                cy.get('.form-group[id^="assignment-cool-off-"]').as('coolOff');
                cy.get('@coolOff').find('input.amount-in-cool-off-period').as('amount');
                cy.get('@coolOff').find('input.cool-off-period').as('period');
                cy.get('.assignment-submission-settings .submit-button').as('submit');
            }

            setAliases();

            cy.get('@amount').clear().type('5');
            cy.get('@period').clear().type('2');
            cy.get('@submit').submit('success');

            cy.get('.submission-uploader .submission-limiting').as('uploaderLimits');

            for (let i = 0; i < 2; ++i) {
                cy.get('@uploaderLimits').find('.loader').should('not.exist');
                cy.get('@uploaderLimits').text().should('contain', '5 times every 2 minutes');

                // Should be the same after a reload
                if (i == 0) {
                    cy.reload();
                    setAliases();
                }
            }

            cy.get('@period').clear().type('0{ctrl}{enter}');
            cy.get('@period').should('have.value', '0');
            cy.get('.submission-uploader .submission-limiting').should('not.exist');

            cy.get('@period').clear().type('-1')
            cy.get('@coolOff').find('.invalid-feedback').as('feedback');

            cy.get('@feedback')
                .should('be.visible')
                .should('contain', 'should be greater than or equal to 0.');
            cy.get('@submit').should('be.disabled');

            cy.get('@amount').clear().type('0');
            cy.get('@period').clear().type('1');

            cy.get('@feedback')
                .should('be.visible')
                .should('contain', 'should be greater than or equal to 1.');
            cy.get('@submit').should('be.disabled');

            cy.get('@amount').clear().type('1')
            cy.get('@period').clear().type('0')
            cy.get('@submit').submit('success');

            cy.get('@feedback').should('not.be.visible');
            cy.get('@submit').should('be.disabled');
        });
    });

    context('Peer feedback', () => {
        it('should be disabled by default', () => {
            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Enable peer feedback')
                .should('be.visible')
                .should('not.be.disabled');
        });

        it('should only save after clicking the submit button', () => {
            function setAliases() {
                cy.get('.peer-feedback-settings')
                    .contains('.btn', 'Enable peer feedback')
                    .as('enableBtn');
            }

            setAliases();

            cy.get('@enableBtn').click();
            cy.get('@enableBtn').should('not.exist');

            cy.reload();
            cy.login('admin', 'admin');
            setAliases();

            cy.get('@enableBtn')
                .should('be.visible')
                .click();
            cy.get('@enableBtn')
                .should('not.exist');

            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Amount of students')
                .should('be.visible');
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .should('be.visible');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Disable')
                .should('be.visible')
                .should('have.class', 'btn-danger');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('have.class', 'btn-primary')
                .submit('success', { hasConfirm: true });

            cy.reload();

            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Enable peer feedback')
                .should('not.exist');
        });

        it('should be possible to change the amount of students', () => {
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Amount of students')
                .find('input')
                .setText('10');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .submit('success', {
                    hasConfirm: true,
                    confirmMsg: 'Changing the amount of students will redistribute',
                });
            cy.reload();
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Amount of students')
                .find('input')
                .should('have.value', '10');
        });

        it('should be possible to change the time to give feedback', () => {
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .find('input[name="Days"]')
                .setText('10')
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .find('input[name="Hours"]')
                .setText('0')
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .submit('success');
            cy.reload();

            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .find('input[name="Days"]')
                .should('have.value', '10');
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .find('input[name="Hours"]')
                .should('have.value', '0');
        });

        it('should not be possible to set an invalid amount of students', () => {
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Amount of students')
                .as('group');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .as('submit');

            cy.get('@group')
                .find('input')
                .setText('abc');
            cy.get('@group')
                .find('.invalid-feedback')
                .should('contain', 'is not a number');
            cy.get('@submit')
                .should('be.disabled');

            cy.get('@group')
                .find('input')
                .clear();
            cy.get('@group')
                .find('.invalid-feedback')
                .should('contain', 'may not be empty');
            cy.get('@submit')
                .should('be.disabled');
        });

        it('should not be possible to set an invalid time to give feedback', () => {
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .as('group');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .as('submit');

            cy.get('@group')
                .find('input[name="Days"]')
                .setText('abc');
            cy.get('@group')
                .find('.invalid-feedback')
                .should('contain', 'Days is not a number');
            cy.get('@submit')
                .should('be.disabled');

            cy.get('@group')
                .find('input[name="Hours"]')
                .setText('abc');
            cy.get('@group')
                .find('.invalid-feedback')
                .should('contain', 'Hours is not a number');
            cy.get('@submit')
                .should('be.disabled');

            cy.get('@group')
                .find('input[name="Days"]')
                .clear();
            cy.get('@group')
                .find('.invalid-feedback')
                .should('contain', 'Days may not be empty');
            cy.get('@submit')
                .should('be.disabled');

            cy.get('@group')
                .find('input[name="Hours"]')
                .clear();
            cy.get('@group')
                .find('.invalid-feedback')
                .should('contain', 'Hours may not be empty');
            cy.get('@submit')
                .should('be.disabled');
        });

        it('should be possible to disable peer feedback', () => {
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Disable')
                .submit('success',  {
                    hasConfirm: true,
                    waitForDefault: false,
                });

            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Amount of students')
                .should('not.exist');
            cy.get('.peer-feedback-settings')
                .contains('.form-group', 'Time to give peer feedback')
                .should('not.exist');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Disable')
                .should('not.exist');
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .should('not.exist');
            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Enable peer feedback')
                .should('be.visible');
        });

        it('should not be possible to enable peer feedback for group assignments', () => {
            cy.createGroupSet(course.id);
            cy.login('admin', 'admin');

            cy.get('.assignment-group')
                .find('.custom-checkbox')
                .click();
            cy.get('.assignment-group')
                .contains('.submit-button', 'Submit')
                .submit('success');

            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Enable peer feedback')
                .should('be.visible')
                .should('be.disabled');

            cy.get('.assignment-group')
                .find('.custom-checkbox')
                .click();
            cy.get('.assignment-group')
                .contains('.submit-button', 'Submit')
                .submit('success');

            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Enable peer feedback')
                .should('be.visible')
                .should('not.be.disabled');
        });

        it('should not be possible to connect a group set for peer feedback assignments', () => {
            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Enable peer feedback')
                .click();
            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Submit')
                .submit('success', { hasConfirm: true });

            cy.get('.assignment-group')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('be.disabled');

            cy.get('.peer-feedback-settings')
                .contains('.submit-button', 'Disable')
                .submit('success',  {
                    hasConfirm: true,
                    waitForDefault: false,
                });

            cy.get('.assignment-group')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('not.be.disabled');
        });
    });

    context('DANGER ZONE!!!', () => {
        it('should be possible to delete an assignment', () => {
            cy.get('.sidebar .sidebar-top a:nth-child(1)').click();
            cy.get('.sidebar .sidebar-top a:nth-child(2)').click();
            cy.get('.course-list').contains(course.name).click();
            cy.get('.assignment-list').should('contain', assignment.name);

            cy.get('.danger-zone-wrapper')
                .contains('.submit-button', 'Delete assignment')
                .submit('success', {
                    hasConfirm: true,
                    confirmInModal: true,
                    doConfirm: false,
                    confirmMsg: 'Deleting this assignment cannot be reversed',
                });

            cy.get('.danger-zone-wrapper')
                .contains('.submit-button', 'Delete assignment')
                .submit('success', {
                    hasConfirm: true,
                    confirmInModal: true,
                    waitForDefault: false,
                    confirmMsg: 'Deleting this assignment cannot be reversed',
                });

            cy.url().should('eq', Cypress.config().baseUrl + '/');
            cy.get('.assig-list').should('not.contain', assignment.name);
            cy.get('.course-wrapper').should('contain', course.name);

            cy.get('.sidebar .sidebar-top a:nth-child(2)').click();
            cy.get('.course-list').contains(course.name).click();
            cy.get('.assignment-list').should('not.contain', assignment.name);
        });
    });
});
