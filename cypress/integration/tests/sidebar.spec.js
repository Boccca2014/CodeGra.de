context('Sidebar', () => {
    before(() => {
        cy.visit('/');
    });

    it('should be possible to create a course', () => {
        const course = `Course ${Math.floor(Math.random() * 10000)}`;

        cy.login('admin', 'admin');

        // Make sure we have the "Create course" permission.
        cy.setSitePermission('can_create_courses', 'Admin', true);
        cy.visit('/');

        cy.get('.sidebar .sidebar-entry-courses').click();
        cy.get('.sidebar .add-course-button').should('be.visible').click();
        cy.get('[id^="course-add-popover"]')
            .should('exist')
            .should('not.have.class', 'fade')
            .within(() => {
                cy.get('input').setText(course);
                cy.get('.submit-button').click();
            });

        // Wait for manage-course page to be loaded.
        cy.get('.page.manage-course').should('exist');
        cy.get('.sidebar .submenu-header').should('contain', course);
    });

    it('should be possible to create an assignment', () => {
        const assig = `Assignment ${Math.floor(Math.random() * 10000)}`;

        cy.login('admin', 'admin');
        cy.createCourse(assig).then(course => {
            cy.visit(`/courses/${course.id}`);
        });

        cy.get('.sidebar .add-assignment-button').should('be.visible').click();
        cy.get('[id^="assignment-add-popover"]')
            .should('exist')
            .should('not.have.class', 'fade')
            .within(() => {
                cy.get('input').setText(assig);
                cy.get('.submit-button').click();
            });

        // Wait for manage-assignment page to be loaded.
        cy.get('.page.manage-assignment').should('exist');
        cy.get('.local-header').should('contain', assig);
    });

    context('Profile page', () => {
        function openProfile() {
            return cy.get('.sidebar-top-item.sidebar-entry-user').click()
        }

        function getSubmit() {
            return cy.get('.submit-button[name=submit-user-info]');
        }

        it('should be possible to change your name', () => {
            const oldName = 'admin';
            const newName = `HAHA A NAME: ${Math.floor(Math.random() * 10000)}`;

            cy.login('admin', 'admin');

            cy.visit('/');
            openProfile();
            cy.get('input[name=full-name]').setText('');
            getSubmit().submit('error', {
                popoverMsg: 'Your new name cannot be empty'
            });
            cy.get('.sidebar-top-item.sidebar-entry-user .name').text().should('eq', oldName);
            cy.get('input[name=full-name]').setText(newName);
            getSubmit().submit('success');
            cy.get('.sidebar-top-item.sidebar-entry-user .name').contains(newName);

            cy.reload();
            cy.get('.sidebar-top-item.sidebar-entry-user .name').text().should('eq', newName);
            openProfile();

            cy.get('input[name=full-name]').focus().setText(oldName);
            getSubmit().submit('success');
            cy.get('.sidebar-top-item.sidebar-entry-user .name').text().should('eq', oldName);
        });

        it('should be possible to change your email', () => {
            const oldEmail = 'admin@example.com';
            const incorrectEmail = 'admin@example';
            const newEmail = `admina-${Math.random()}@example.nl`;

            function submitEmail(email, password) {
                cy.get('input[name=email]').setText(email)
                cy.get('input[name=email]').should('have.value', email);
                cy.get('input[name=old-password]').setText(password);
                cy.get('input[name=old-password]').should('have.value', password);
                return getSubmit();
            }

            cy.login('admin', 'admin');
            openProfile();
            cy.get('input[name=email]').should('have.value', oldEmail);

            submitEmail('', '').submit('error', { popoverMsg: 'not valid' });
            submitEmail(incorrectEmail, '').submit('error', { popoverMsg: 'not valid' });
            submitEmail(newEmail, '').submit('error', { popoverMsg: 'need a correct old password' });
            submitEmail(newEmail, 'incorrect pass').submit('error', { popoverMsg: 'given old password is wrong' });
            submitEmail(newEmail, 'admin').submit('success');

            cy.reload();
            openProfile();
            cy.get('input[name=email]').should('have.value', newEmail);
            submitEmail(oldEmail, 'admin').submit('success');
        });

        it('should be possible to reset the fields', () => {
            cy.login('admin', 'admin');
            openProfile();
            let inputs = [];
            cy.get('.userinfo').find('input').each($el => {
                inputs.push($el.val());
            });
            cy.log(inputs);

            cy.get('.userinfo').find('input').each(($el, $index) => {
                if ($index > 0) {
                    cy.wrap($el).setText(`HELLO! - ${Math.random()}`);
                }
            });

            cy.get('.userinfo .btn.btn-danger').click();
            cy.get('.userinfo').find('input').each(($el, $index) => {
                cy.wrap($el).should('have.value', inputs[$index]);
            });
        });

        it('should be possible to toggle between dark and light mode', () => {
            cy.login('admin', 'admin');
            openProfile();

            cy.get('body').should('not.have.class', 'cg-dark-mode');
            cy.get('.settings-content .toggle-container.colors').should('exist');
            cy.get('.settings-content .toggle-container.colors[checked=checked]').should('not.exist');

            cy.get('.settings-content .toggle-container .label-on').click();
            cy.get('body').should('have.class', 'cg-dark-mode');

            cy.reload();
            cy.get('body').should('have.class', 'cg-dark-mode');
            openProfile();
            cy.get('.settings-content .toggle-container.colors[checked=checked]').should('exist');
            cy.get('.settings-content .toggle-container .toggle').click();
            cy.get('body').should('not.have.class', 'cg-dark-mode');
        });
    });

    context.only('Reloading stuff', () => {
        const seed = Math.floor(100000 * Math.random());
        let course;
        let assignment;

        function delayCoursesRoute(delay = 1000) {
            return cy.delayRoute(
                {
                    url: '/api/v1/courses/?extended=true&no_course_in_assignment=true&limit=1&offset=10',
                    method: 'GET',
                },
                delay,
                {
                    url: /^\/api\/v1\/courses\/\?.*/,
                    method: 'GET',
                },
            );
        }

        before(() => {
            cy.createCourse(
                `Sidebar Reload ${seed}`,
            ).then(res => {
                course = res;
                return cy.createAssignment(
                    course.id,
                    `Sidebar Reload ${seed}`,
                    { state: 'open', deadline: 'tomorrow', bbZip: true },
                );
            }).then(res => {
                assignment = res;
            });
        });

        beforeEach(() => {
            cy.server();
        });

        it('should not crash the home page', () => {
            cy.login('admin', 'admin', '/');

            cy.get('.home-grid')
                .should('be.visible')
                .find('.course-wrapper')
                .should('be.visible');

            delayCoursesRoute().then(() => {
                // Reload from the courses submenu.
                cy.get('.sidebar .sidebar-entry-courses')
                    .click();
                cy.get('.sidebar .submenu:last .course-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Check that the courses are gone.
                cy.get('.home-grid .course-wrapper')
                    .should('not.be.visible');
                // Check that there is a "no courses" message.
                cy.get('.home-grid .extra-load-btn')
                    .should('be.visible')
                    .should('contain', 'Loading');
                // Check that the message disappears...
                cy.get('.home-grid .extra-load-btn')
                    .should('not.contain', 'Loading');
                // ... and that the courses are visible again.
                cy.get('.course-wrapper')
                    .should('be.visible');

                // Reload from the assignments submenu.
                cy.get('.sidebar .sidebar-entry-assignments')
                    .click();
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Check that the courses are gone.
                cy.get('.home-grid .course-wrapper')
                    .should('not.be.visible');
                // ... and that they come back again.
                cy.get('.course-wrapper')
                    .should('be.visible');
            });
        });

        it('should not crash the submissions page', () => {
            cy.login(
                'admin',
                'admin',
                `/courses/${course.id}/assignments/${assignment.id}/submissions/`,
            );
            cy.get('.submission-list')
                .should('be.visible')
                .find('tbody tr')
                .should('not.have.length', 0)
                .should('be.visible');

            delayCoursesRoute().then(() => {
                // Reload from the courses submenu. It is already opened, but on
                // the assignments of the current course. Let's test for that by
                // closing and reopening it.
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('exist');
                cy.get('.sidebar .sidebar-entry-courses.selected')
                    .click();
                cy.get('.sidebar .sidebar-entry-courses')
                    .click();
                cy.get('.sidebar .submenu:last .course-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Perform the check that an actual reload happens.
                // First check that the submission list disappears.
                cy.get('.submission-list')
                    .should('not.exist')
                // Then that a loader appears.
                cy.get('.page.submissions')
                    .find('.loader.page-loader')
                    .should('be.visible');
                // Then that the loader disappears again.
                cy.get('.page.submissions')
                    .find('.loader.page-loader')
                    .should('not.exist');
                // Then that the submissions become visible again.
                cy.get('.submission-list')
                    .should('be.visible')
                    .find('tbody tr')
                    .should('not.have.length', 0)
                    .should('be.visible');

                // Reload from the assignments submenu.
                cy.get('.sidebar .sidebar-entry-assignments')
                    .click();
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Perform the check that an actual reload happens.
                // First check that the submission list disappears.
                cy.get('.submission-list')
                    .should('not.exist')
                // Then that a loader appears.
                cy.get('.page.submissions')
                    .find('.loader.page-loader')
                    .should('be.visible');
                // Then that the loader disappears again.
                cy.get('.page.submissions')
                    .find('.loader.page-loader')
                    .should('not.exist');
                // Then that the submissions become visible again.
                cy.get('.submission-list')
                    .should('be.visible')
                    .find('tbody tr')
                    .should('not.have.length', 0)
                    .should('be.visible');
            });
        });

        it('should not crash the submission page', () => {
            cy.login(
                'admin',
                'admin',
                `/courses/${course.id}/assignments/${assignment.id}/submissions/`,
            );

            cy.get('.submission-list')
                .should('be.visible')
                .find('tbody tr')
                .should('not.have.length', 0)
                .first()
                .click();
            cy.get('.submission-page-loader')
                .should('not.exist');
            cy.get('.page.submission')
                .should('be.visible')
                .find('.file-viewer')
                .should('be.visible')
                .find('.loader')
                .should('not.exist');

            delayCoursesRoute().then(() => {
                // Reload from the courses submenu.
                cy.get('.sidebar .sidebar-entry-courses')
                    .click();
                cy.get('.sidebar .submenu:last .course-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // First check that the file viewer disappears.
                cy.get('.page.submission .file-viewer')
                    .should('not.exist');
                // Then check that the page loader appears.
                cy.get('.submission-page-loader')
                    .should('exist');
                // Then check that the page loader disappears again.
                cy.get('.submission-page-loader')
                    .should('not.exist');
                // And that the file viewer is visible again and that it loads
                // a file.
                cy.get('.page.submission')
                    .should('be.visible')
                    .find('.file-viewer')
                    .should('be.visible')
                    .find('.loader')
                    .should('not.exist');

                // Reload from the assignments submenu.
                cy.get('.sidebar .sidebar-entry-assignments')
                    .click();
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // First check that the file viewer disappears.
                cy.get('.page.submission .file-viewer')
                    .should('not.exist');
                // Then check that the page loader appears.
                cy.get('.submission-page-loader')
                    .should('exist');
                // Then check that the page loader disappears again.
                cy.get('.submission-page-loader')
                    .should('not.exist');
                // And that the file viewer is visible again and that it loads
                // a file.
                cy.get('.page.submission')
                    .should('be.visible')
                    .find('.file-viewer')
                    .should('be.visible')
                    .find('.loader')
                    .should('not.exist');

                cy.url().then(url => {
                    const subId = url.match(/\/submissions\/(\d+)\//)[1];

                    cy.delayRoute({
                        url: `/api/v1/submissions/${subId}/root_file_trees/`,
                        method: 'GET',
                    }).as('filesRoute');
                    cy.delayRoute({
                        url: `/api/v1/submissions/${subId}/feedbacks/?with_replies`,
                        method: 'GET',
                    }).as('feedbackRoute');
                    cy.delayRoute({
                        url: `/api/v1/assignments/${assignment.id}/submissions/?extended&latest_only`,
                        method: 'GET',
                    }).as('subsRoute');
                });

                // I could not get the timing right for this case (and what good is
                // a test anyway if it depends on very specific timings...); for
                // some reason Cypress _can_ detect that the .file-viewer is gone,
                // but if we check for a .submission-page-loader to be visible
                // directly after that, that fails because the .file-viewer is
                // already visible again. Even with the delay set very high (5
                // seconds).
                cy.get('.sidebar .sidebar-entry-submissions')
                    .click();
                cy.get('.sidebar .submenu:last .submissions-sidebar-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // First check that the file viewer disappears.
                cy.get('.page.submission .file-viewer')
                    .should('not.exist');

                // Wait until the submissions have been reloaded (and make sure
                // this happens _after_ the .file-viewer has disappeared).
                cy.wait('@filesRoute');
                cy.wait('@feedbackRoute');
                cy.wait('@subsRoute');

                // Then that the loader disappears again.
                cy.get('.page.submission .submission-page-inner-loader')
                    .should('not.exist');
                // And that the file viewer is visible again and that it loads
                // a file.
                cy.get('.page.submission')
                    .should('be.visible')
                    .find('.file-viewer')
                    .should('be.visible')
                    .find('.loader')
                    .should('not.exist');
            });
        });

        it('should not crash the manage assignment page', () => {
            cy.login('admin', 'admin', `/courses/${course.id}/assignments/${assignment.id}`);

            cy.get('.page.manage-assignment')
                .should('be.visible')
                .find('input')
                .should('not.have.length', 0)
                .should('be.visible');

            delayCoursesRoute(3000).then(() => {
                // Reload from the courses submenu. It is already opened, but on
                // the assignments of the current course. Let's test for that by
                // closing and reopening it.
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('exist');
                cy.get('.sidebar .sidebar-entry-courses.selected')
                    .click();
                cy.get('.sidebar .sidebar-entry-courses')
                    .click();
                cy.get('.sidebar .submenu:last .course-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Check that the inputs disappear.
                cy.get('.manage-assignment input')
                    .should('not.exist');
                // Check that a loader appears.
                cy.get('.manage-assignment .page-content > .loader')
                    .should('be.visible');
                // Then check that the page loader disappears again.
                cy.get('.manage-assignment .page-content > .loader')
                    .should('not.exist');
                // And that the inputs are visible again.
                cy.get('.manage-assignment input')
                    .should('be.visible');

                // Reload from the assignments submenu.
                cy.get('.sidebar .sidebar-entry-assignments')
                    .click();
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Check that the inputs disappear.
                cy.get('.manage-assignment input')
                    .should('not.exist');
                // Check that a loader appears.
                cy.get('.manage-assignment .page-content > .loader')
                    .should('be.visible');
                // Then check that the page loader disappears again.
                cy.get('.manage-assignment .page-content > .loader')
                    .should('not.exist');
                // And that the inputs are visible again.
                cy.get('.manage-assignment input')
                    .should('be.visible');
            });
        });

        it('should not crash the manage course page', () => {
            cy.login('admin', 'admin', `/courses/${course.id}`);

            cy.get('.page.manage-course')
                .should('be.visible')
                .find('.users-manager')
                .should('be.visible');

            delayCoursesRoute().then(() => {
                // Reload from the courses submenu. It is already opened, but on
                // the assignments of the current course. Let's test for that by
                // closing and reopening it.
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('exist');
                cy.get('.sidebar .sidebar-entry-courses.selected')
                    .click();
                cy.get('.sidebar .sidebar-entry-courses')
                    .click();
                cy.get('.sidebar .submenu:last .course-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Check that the inputs disappear.
                cy.get('.manage-course .users-manager')
                    .should('not.exist');
                // Check that a loader appears.
                cy.get('.manage-course > .loader')
                    .should('be.visible');
                // Then check that the page loader disappears again.
                cy.get('.manage-course > .loader')
                    .should('not.exist');
                // And that the inputs are visible again.
                cy.get('.manage-course .users-manager')
                    .should('be.visible');

                // Reload from the assignments submenu.
                cy.get('.sidebar .sidebar-entry-assignments')
                    .click();
                cy.get('.sidebar .submenu:last .assignment-list')
                    .should('be.visible');
                cy.get('.sidebar .submenu:last .refresh-button')
                    .click();

                // Check that the inputs disappear.
                cy.get('.manage-course .users-manager')
                    .should('not.exist');
                // Check that a loader appears.
                cy.get('.manage-course > .loader')
                    .should('be.visible');
                // Then check that the page loader disappears again.
                cy.get('.manage-course > .loader')
                    .should('not.exist');
                // And that the inputs are visible again.
                cy.get('.manage-course .users-manager')
                    .should('be.visible');
            });
        });
    });
});
