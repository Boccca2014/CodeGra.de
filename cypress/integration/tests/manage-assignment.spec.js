import moment from 'moment';

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
                cy.get('.assignment-general-settings')
                    .contains('.submit-button', 'Submit')
                    .submit('success');
                cy.get('@header').text().should('contain', headerText + 'abc');
            });

            cy.get('@group').find('input').clear().type(assignment.name);
            cy.get('.assignment-general-settings')
                .contains('.submit-button', 'Submit')
                .submit('success');
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
            cy.get('.flatpickr-calendar:visible .flatpickr-day:not(.prevMonthDay):not(.nextMonthDay).today + .flatpickr-day + .flatpickr-day')
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
                .should('contain', moment().add(2, 'day').format('YYYY-MM-DD'))
                .should('contain', '23:59');
        });

        it('should be possible to upload a BB zip', () => {
            cy.get('.blackboard-zip-uploader').within(() => {
                cy.get('input[type=file]').uploadFixture('test_blackboard/bb.zip', 'application/zip');
                // Wait for submit button to go back to default.
                cy.get('.submit-button').submit('success');
            });
        });

        it('should disable the submit button when nothing was changed', () => {
            cy.reload();
            cy.login('admin', 'admin');

            cy.get('.assignment-general-settings')
                .should('be.visible')
                .as('settings');
            cy.get('@settings')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('be.disabled')
                .as('submit');

            // Should be disabled as we have just reloaded.
            cy.get('@submit').should('be.disabled');

            // Set available at date, otherwise exam mode is invalid and the
            // button will still be disabled if we change the assignment kind.
            cy.get('@settings')
                .find('input[id^="assignment-available-at-"]')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-day.today')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-confirm')
                .click();
            cy.get('@submit').submit('success');

            // Should be disabled as we have just submitted.
            cy.get('@submit').should('be.disabled');

            // Should not be disabled if we change to exam mode.
            cy.get('@settings')
                .find('select[id^="assignment-kind-"]')
                .select('exam');
            cy.get('@submit').should('not.be.disabled');

            // Should be disabled after changing back.
            cy.get('@settings')
                .find('select[id^="assignment-kind-"]')
                .select('normal');
            cy.get('@submit').should('be.disabled');

            // Should not be disabled after changing the assignment name.
            cy.get('@settings')
                .find('input[id^="assignment-name-"]')
                .setText('abc');
            cy.get('@submit').should('not.be.disabled');

            // Should be disabled after changing back.
            cy.get('@settings')
                .find('input[id^="assignment-name-"]')
                .setText(assignment.name);
            cy.get('@submit').should('be.disabled');

            // Should not be disabled after changing available at.
            cy.get('@settings')
                .find('input[id^="assignment-available-at-"]')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-day.today + .flatpickr-day')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-confirm')
                .click();
            cy.get('@submit').should('not.be.disabled');

            // Should be disabled after changing back.
            cy.get('@settings')
                .find('input[id^="assignment-available-at-"]')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-day.today')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-confirm')
                .click();
            cy.get('@submit').should('be.disabled');

            // Should not be disabled after changing deadline.
            cy.get('@settings')
                .find('input[id^="assignment-deadline-"]')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-day.today + .flatpickr-day')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-confirm')
                .click();
            cy.get('@submit').should('not.be.disabled');

            // Should be disabled after changing back.
            cy.get('@settings')
                .find('input[id^="assignment-deadline-"]')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-day.today + .flatpickr-day + .flatpickr-day')
                .click();
            cy.get('.flatpickr-calendar:visible')
                .find('.flatpickr-confirm')
                .click();
            cy.get('@submit').should('be.disabled');

            // Should not be disabled after changing max points.
            cy.get('@settings')
                .find('input[id^="assignment-max-points-"]')
                .setText('10');
            cy.get('@submit').should('not.be.disabled');

            // Should be disabled after changing back.
            cy.get('@settings')
                .find('input[id^="assignment-max-points-"]')
                .clear();
            cy.get('@submit').should('be.disabled');

            // Enable exam mode.
            cy.get('@settings')
                .find('select[id^="assignment-kind-"]')
                .select('exam');
            cy.get('@submit').submit('success');

            cy.get('@settings')
                .find('input[id^="assignment-deadline-"]')
                .invoke('val')
                .then(oldValue => {
                    // Should not be disabled after changing the duration.
                    cy.get('@settings')
                        .find('input[id^="assignment-deadline-hours-"]')
                        .setText('10');
                    cy.get('@submit').should('not.be.disabled');

                    // Should be disabled after changing back.
                    cy.get('@settings')
                        .find('input[id^="assignment-deadline-hours-"]')
                        .setText(oldValue);
                    cy.get('@submit').should('be.disabled');
                });

            // Set deadline early enough that it is accepted in combination
            // with the send login mails option.
            cy.get('@settings')
                .find('input[id^="assignment-deadline-hours-"]')
                .setText('3');
            cy.get('@submit').submit('success');

            // Should not be disabled after changing login links.
            cy.get('@settings')
                .find('.toggle-container[id^="assignment-login-mail-"]')
                .find('.label-on')
                .click();
            cy.get('@submit').should('not.be.disabled');

            // Should be disabled after changing back.
            cy.get('@settings')
                .find('.toggle-container[id^="assignment-login-mail-"]')
                .find('.label-off')
                .click();
            cy.get('@submit').should('be.disabled');
        });

        it('should show errors and disable submit for invalid input', () => {
            cy.reload();
            cy.login('admin', 'admin');

            cy.get('.assignment-general-settings')
                .should('be.visible')
                .as('settings');
            cy.get('@settings')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('be.disabled')
                .as('submit');

            // Empty name is an error.
            cy.get('@settings')
                .find('input[id^="assignment-name-"]')
                .clear();
            cy.get('@settings')
                .contains('.form-group', 'Assignment name')
                .find('.invalid-feedback')
                .should('be.visible')
                .should('contain', 'not be empty');
            cy.get('@submit').should('be.disabled');

            // Error should be hidden when name is set. We choose a name
            // different from the actual assignment name so that the submit
            // button is not disabled.
            cy.get('@settings')
                .find('input[id^="assignment-name-"]')
                .type('xyz');
            cy.get('@settings')
                .contains('.form-group', 'Assignment name')
                .find('.invalid-feedback')
                .should('not.be.visible');
            cy.get('@submit').should('not.be.disabled');

            // Long exam duration with login mails is an error.
            cy.get('@settings')
                .find('.toggle-container[id^="assignment-login-mail-"]')
                .find('.label-on')
                .click();
            cy.get('@settings')
                .find('input[id^="assignment-deadline-hours-"]')
                .setText('1000');
            cy.get('@settings')
                .contains('.form-group', 'Duration')
                .find('.invalid-feedback')
                .should('be.visible')
                .should('contain', 'With "Send login mails" enabled, exams can take at most');
            cy.get('@submit').should('be.disabled');

            // Error should be hidden when login links are turned off.
            cy.get('@settings')
                .find('.toggle-container[id^="assignment-login-mail-"]')
                .find('.label-off')
                .click();
            cy.get('@settings')
                .contains('.form-group', 'Duration')
                .find('.invalid-feedback')
                .should('not.be.visible');
            cy.get('@submit').should('not.be.disabled');

            // Error should be hidden when duration is set correctly.
            cy.get('@settings')
                .find('.toggle-container[id^="assignment-login-mail-"]')
                .find('.label-on')
                .click();
            cy.get('@settings')
                .find('input[id^="assignment-deadline-hours-"]')
                .setText('3');
            cy.get('@settings')
                .contains('.form-group', 'Duration')
                .find('.invalid-feedback')
                .should('not.be.visible');
            cy.get('@submit').should('not.be.disabled');

            // Restore the login mail setting.
            cy.get('@settings')
                .find('.toggle-container[id^="assignment-login-mail-"]')
                .find('.label-off')
                .click();
            cy.get('@submit').should('not.be.disabled');

            // Disable exam mode.
            cy.get('@settings')
                .find('select[id^="assignment-kind-"]')
                .select('normal');
            cy.get('@submit').submit('success');

            // Change assignment name again to enable submit button.
            cy.get('@settings')
                .find('input[id^="assignment-name-"]')
                .setText(assignment.name);
            cy.get('@submit').should('not.be.disabled');

            // Available-at may not be after deadline.
            cy.get('@settings')
                .find('input[id^="assignment-available-at-"]')
                .click();
            cy.get('.flatpickr-calendar:visible').within(() => {
                cy.get('.flatpickr-next-month').click();
                cy.get('.dayContainer')
                    .contains('.flatpickr-day:not(.prevMonthDay)', '10')
                    .click();
                cy.get('.flatpickr-confirm').click();
            });
            cy.get('@settings')
                .contains('.form-group', 'Available at')
                .find('.invalid-feedback')
                .should('be.visible')
                .text()
                .should('contain', 'available at date must be before the deadline');
            cy.get('@settings')
                .contains('.form-group', 'Deadline')
                .find('.invalid-feedback')
                .should('be.visible')
                .text()
                .should('contain', 'deadline must be after the available at date');
            cy.get('@submit').should('be.disabled');

            // Error should be hidden when deadline is changed
            cy.get('@settings')
                .find('input[id^="assignment-deadline-"]')
                .click();
            cy.get('.flatpickr-calendar:visible').within(() => {
                cy.get('.flatpickr-next-month').click();
                cy.get('.dayContainer')
                    .contains('.flatpickr-day:not(.prevMonthDay)', '20')
                    .click();
                cy.get('.flatpickr-confirm').click();
            });
            cy.get('@settings')
                .contains('.form-group', 'Available at')
                .find('.invalid-feedback')
                .should('not.be.visible');
            cy.get('@settings')
                .contains('.form-group', 'Deadline')
                .find('.invalid-feedback')
                .should('not.be.visible');
            cy.get('@submit').should('not.be.disabled');

            // Error should be hidden when available at is reset
            cy.get('@settings')
                .find('input[id^="assignment-available-at-"]')
                .click();
            cy.get('.flatpickr-calendar:visible').within(() => {
                cy.get('.flatpickr-next-month').click();
                cy.get('.dayContainer')
                    .contains('.flatpickr-day:not(.prevMonthDay)', '25')
                    .click();
                cy.get('.flatpickr-confirm').click();
            });
            cy.get('@settings')
                .contains('.form-group', 'Available at')
                .find('.invalid-feedback')
                .should('be.visible');
            cy.get('@settings')
                .find('button[id^="assignment-available-at-"][id$="-reset"]')
                .click();
            cy.get('@settings')
                .contains('.form-group', 'Available at')
                .find('.invalid-feedback')
                .should('not.be.visible');
            cy.get('@submit')
                .should('not.be.disabled')
                .submit('success');
        });
    });

    context('Submission settings', () => {
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

            cy.wrap([
                ['-10', 'should be greater than or equal to 0'],
                ['abcd', 'is not a number'],
            ]).each(([value, error]) => {
                cy.get('@input').clear().type(value);
                cy.get('@maxSubs').find('.invalid-feedback').as('feedback');

                cy.get('@feedback')
                    .should('be.visible')
                    .should('contain', error);
                cy.get('@submit').should('be.disabled');
            });

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

            cy.get('@amount').clear().type('1');
            cy.get('@period').clear().type('0');
            cy.get('@submit').submit('success');

            cy.get('@feedback').should('not.be.visible');
            cy.get('@submit').should('be.disabled');
        });

        it('should show errors and disable submit when no submit type is selected', () => {
            cy.reload();
            cy.login('admin', 'admin');

            cy.get('.assignment-submission-settings')
                .should('be.visible')
                .as('settings');
            cy.get('@settings')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('be.disabled')
                .as('submit');

            // Disabling all submit types is an error.
            cy.get('@settings')
                .find('input[id^="assignment-submit-files-"]')
                .click({ force: true });
            cy.get('@settings')
                .contains('.form-group', 'Allowed upload types')
                .find('.invalid-feedback')
                .should('be.visible')
                .should('contain', 'at least one way of uploading');
            cy.get('@submit').should('be.disabled');

            // Enabling webhook should hide the error, and enable the submit
            // button which we check for in the rest of the test.
            cy.get('@settings')
                .find('input[id^="assignment-submit-webhook-"]')
                .click({ force: true });
        });

        it('should disable the submit button when nothing was changed', () => {
            cy.reload();
            cy.login('admin', 'admin');

            cy.get('.assignment-submission-settings')
                .should('be.visible')
                .as('settings');
            cy.get('@settings')
                .contains('.submit-button', 'Submit')
                .should('be.visible')
                .should('be.disabled')
                .as('submit');

            // Changing allowed upload types should enable submit.
            cy.get('@settings')
                .find('input[id^="assignment-submit-webhook-"]')
                .click({ force: true });
            cy.get('@submit').should('not.be.disabled');

            cy.get('@settings')
                .find('input[id^="assignment-submit-files-"]')
                .click({ force: true });
            cy.get('@submit').should('not.be.disabled');

            // Changing back should disable submit.
            cy.get('@settings')
                .find('input[id^="assignment-submit-files-"]')
                .click({ force: true });
            cy.get('@settings')
                .find('input[id^="assignment-submit-webhook-"]')
                .click({ force: true });
            cy.get('@submit').should('be.disabled');

            // Changing max submissions should enable submit.
            cy.get('@settings')
                .find('input[id^="assignment-max-submissions-"]')
                .type('1000');
            cy.get('@submit').should('not.be.disabled');

            // Resetting should disable the button again.
            cy.get('@settings')
                .find('input[id^="assignment-max-submissions-"]')
                .clear();
            cy.get('@submit').should('be.disabled')

            // Store a value to check that clearing enables submit.
            cy.get('@settings')
                .find('input[id^="assignment-max-submissions-"]')
                .type('1000');
            cy.get('@submit').submit('success');

            // Changing max submissions should enable submit.
            cy.get('@settings')
                .find('input[id^="assignment-max-submissions-"]')
                .clear();
            cy.get('@submit').should('not.be.disabled');

            // Resetting should disable the button again.
            cy.get('@settings')
                .find('input[id^="assignment-max-submissions-"]')
                .type('1000');
            cy.get('@submit').should('be.disabled')

            // Changing cool off amount should enable submit.
            cy.get('@settings')
                .find('input[id^="assignment-cool-off-"][id$="-amount-input"]')
                .setText('1000');
            cy.get('@submit').should('not.be.disabled');

            // Resetting should disable the button again.
            cy.get('@settings')
                .find('input[id^="assignment-cool-off-"][id$="-amount-input"]')
                .setText('1');
            cy.get('@submit').should('be.disabled');

            // Changing cool off period should enable submit.
            cy.get('@settings')
                .find('input[id^="assignment-cool-off-"][id$="-period-input"]')
                .clear();
            cy.get('@submit').should('not.be.disabled');

            cy.get('@settings')
                .find('input[id^="assignment-cool-off-"][id$="-period-input"]')
                .type('1000');
            cy.get('@submit').should('not.be.disabled');

            // Resetting should disable the button again.
            cy.get('@settings')
                .find('input[id^="assignment-cool-off-"][id$="-period-input"]')
                .setText('0');
            cy.get('@submit').should('be.disabled');
        });
    });

    context('Peer feedback', () => {
        it('should be disabled by default', () => {
            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Set up peer feedback')
                .should('be.visible')
                .should('not.be.disabled');
        });

        it('should only save after clicking the submit button', () => {
            function setAliases() {
                cy.get('.peer-feedback-settings')
                    .contains('.btn', 'Set up peer feedback')
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
                .contains('.btn', 'Set up peer feedback')
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
                .contains('.btn', 'Set up peer feedback')
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
                .contains('.btn', 'Set up peer feedback')
                .should('be.visible')
                .should('be.disabled');

            cy.get('.assignment-group')
                .find('.custom-checkbox')
                .click();
            cy.get('.assignment-group')
                .contains('.submit-button', 'Submit')
                .submit('success');

            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Set up peer feedback')
                .should('be.visible')
                .should('not.be.disabled');
        });

        it('should not be possible to connect a group set for peer feedback assignments', () => {
            cy.get('.peer-feedback-settings')
                .contains('.btn', 'Set up peer feedback')
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
