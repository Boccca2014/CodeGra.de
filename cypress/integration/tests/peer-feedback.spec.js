function daysToSeconds(days) {
    return days * 24 * 60 * 60;
}

context('Peer feedback', () => {
    const unique = Math.floor(100000 * Math.random());
    let course;
    let assignment;
    let submission1;
    let submission2;
    let baseUrl;

    function patchSettings({ deadline, state, time, amount, auto_approved }) {
        if (deadline != null) {
            cy.patchAssignment(assignment.id, { deadline });
        }

        if (state != null) {
            cy.patchAssignment(assignment.id, { state });
        }

        if (time != null && amount != null && auto_approved != null) {
            cy.patchPeerFeedback(assignment.id, { time, amount, auto_approved });
        } else if (time === null && amount === null && auto_approved === null) {
            cy.patchPeerFeedback(assignment.id, null);
        }
    }

    before(() => {
        cy.visit('/');

        cy.createCourse(
            `Peer Feedback Course ${unique}`,
            [
                { name: 'student1', role: 'Student' },
                { name: 'student2', role: 'Student' },
                { name: 'student3', role: 'Student' },
                { name: 'student4', role: 'Student' },
            ],
        ).then(res => {
            course = res;
            return cy.createAssignment(
                course.id,
                `Peer Feedback Assignment ${unique}`,
                { deadline: 'tomorrow', state: 'open' },
            );
        }).then(res => {
            assignment = res;
            baseUrl = `/courses/${course.id}/assignments/${assignment.id}/submissions`;
            return cy.createSubmission(
                assignment.id,
                'test_submissions/all_filetypes.zip',
                { author: 'student1' },
            );
        }).then(res => {
            submission1 = res;
            return cy.createSubmission(
                assignment.id,
                'test_submissions/all_filetypes.zip',
                { author: 'student2' },
            );
        }).then(res => {
            submission2 = res;
            patchSettings({ time: daysToSeconds(7), amount: 1, auto_approved: false });
        });
    });

    context('Giving peer feedback', () => {
        before(() => {
            cy.login('student1', 'Student1');
            cy.visit(baseUrl);
        });

        it('should not be possible before the deadline', () => {
            cy.wait(2000);
            cy.get('.page.submissions')
                .should('be.visible')
                .contains('.wizard-button', 'Peer feedback')
                .should('be.disabled');
        });

        it('should show who the logged in user must give feedback to', () => {
            patchSettings({ deadline: 'yesterday' });
            cy.login('student1', 'Student1');

            // Go to peer feedback overview.
            cy.get('.page.submissions')
                .should('be.visible')
                .contains('.wizard-button', 'Peer feedback')
                .click();

            // Make sure we're connected to the only other student with
            // a submission.
            cy.get('.peer-feedback-overview table tbody tr')
                .should('have.length', 1)
                .should('contain', 'Student2')
                .click();

            // Verify we can see the other student's submission.
            cy.get('.page.submission')
                .should('be.visible')
                .find('.submission-nav-bar')
                .should('contain', 'Student2');
        });

        it('should be possible on regular code', () => {
            // Open nested/timer.c
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Wait until file is loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Start editing comment on first line.
            cy.get('.code-viewer li.line:first')
                .click();

            // Write a commit and submit.
            cy.get('.feedback-area textarea')
                .type('peer feedback');
            cy.get('.feedback-area')
                .contains('.submit-button', 'Save')
                .submit('success', { waitForDefault: false });
        });

        it('should be possible on other filetypes (images, PDFs, etc.)', () => {
            // Open image file.
            cy.get('.file-tree')
                .contains('li', 'venn1.png')
                .click();

            // Wait for image to be loaded.
            cy.get('.image-viewer')
                .should('be.visible')
                .find('.img')
                .should('be.visible');

            // Start editing comment.
            cy.get('.floating-feedback-button .feedback-button')
                .click({ force: true });

            // Write comment and submit.
            cy.get('.feedback-area textarea')
                .type('peer feedback');
            cy.get('.feedback-area')
                .contains('.submit-button', 'Save')
                .submit('success', { waitForDefault: false });
        });

        it('should be visible to the author after reload', () => {
            // A regular reload logs us out, but this triggers a reload as
            // well.
            cy.login('student1', 'Student1');

            // Make sure nested/timer.c is visible.
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Check that author and comment are correct.
            cy.get('.code-viewer')
                .should('be.visible')
                .find('.feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });

            // Open an image.
            cy.get('.file-tree')
                .contains('li', 'venn1.png')
                .click();

            // Wait for the image to be loaded.
            cy.get('.image-viewer')
                .should('be.visible')
                .find('.img')
                .should('be.visible');

            // Check that author and comment are correct.
            cy.get('.floating-feedback-button .feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });
        });

        it('should not be possible to approve your own feedback', () => {
            cy.get('.feedback-reply .peer-feedback-assessment')
                .should('be.visible')
                .find('.toggle-container')
                .should('have.class', 'disabled');
        });

        it('should be visible in the feedback overview', () => {
            cy.openCategory('Feedback Overview');

            // Check that the author and feedback are correct for nested/timer.c.
            cy.get('.feedback-overview')
                .contains('.inner-feedback-viewer', 'nested/timer.c')
                .find('.feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });

            // Check that the author and feedback are correct for venn1.png.
            cy.get('.feedback-overview')
                .contains('.inner-feedback-viewer', 'venn1.png')
                .find('.feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });

            cy.openCategory('Code');
        });

        it('should not show the peer feedback overview for the other student', () => {
            cy.get('.categories')
                .contains('.category', 'Peer feedback')
                .should('not.exist');
        });

        it('should not be possible after the peer feedback deadline', () => {
            patchSettings({ amount: 1, time: 1, auto_approved: false });
            cy.login('student1', 'Student1');

            // Open nested/timer.c
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Check that author and comment are correct.
            cy.get('.code-viewer')
                .should('be.visible')
                .find('li:nth(2)')
                .click();

            // Check that a 2nd feedback area did not open
            cy.get('.feedback-area')
                .should('have.length', 1);
        });

        it('should not be possible if the assignment state is "done"', () => {
            patchSettings({ state: 'done', amount: 1, time: daysToSeconds(7), auto_approved: false });
            cy.login('student1', 'Student1');

            // The feedback overview tab is focused by default now.
            cy.openCategory('Code');

            // Open nested/timer.c
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Check that author and comment are correct.
            cy.get('.code-viewer')
                .should('be.visible')
                .find('li:nth(2)')
                .click();

            // Check that a 2nd feedback area did not open
            cy.get('.feedback-area')
                .should('have.length', 1);
        });

        it('should be visible on the student\'s own submission page "Peer feedback" tab', () => {
            cy.visit(`${baseUrl}/${submission1.id}`);
            cy.login('student1', 'Student1');
            cy.openCategory('Peer Feedback');

            cy.wait(2000);

            // Check the feedback in nested/timer.c
            cy.get('.peer-feedback-by-user')
                .contains('.inner-inline-feedback-file', 'nested/timer.c')
                .find('.feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });

            // Check the feedback in venn1.png
            cy.get('.peer-feedback-by-user')
                .contains('.inner-feedback-viewer', 'venn1.png')
                .find('.feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });
        });
    });

    context('Viewing peer feedback before approval', () => {
        before(() => {
            patchSettings({ deadline: 'tomorrow', state: 'open' });
            cy.login('student2', 'Student2');
            cy.visit(baseUrl);
        });

        it('should not be visible before the deadline', () => {
            cy.wait(2000);

            cy.get('.page.submissions')
                .should('be.visible')
                .contains('.wizard-button', 'Latest submission')
                .click();
            cy.get('.page.submission')
                .should('be.visible');

            // Open nested/timer.c
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Wait for file to be loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Check that the peer feedback is not visible.
            cy.get('.code-viewer .feedback-area')
                .should('not.exist');
        });

        it('should not be visible before the peer feedback deadline', () => {
            patchSettings({ deadline: 'yesterday' });
            cy.login('student2', 'Student2');

            // Wait for file to be loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Check that the peer feedback is not visible.
            cy.get('.code-viewer .feedback-area')
                .should('not.exist');
        });

        it('should not be visible when the assignment is "done"', () => {
            patchSettings({ state: 'done' });
            cy.login('student2', 'Student2');

            cy.wait(2000);
            cy.openCategory('Code');

            // Wait for file to be loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Check that the peer feedback is not visible.
            cy.get('.code-viewer .feedback-area')
                .should('not.exist');
        });
    });

    context('Approving peer feedback', () => {
        before(() => {
            patchSettings({ state: 'open', 'deadline': 'tomorrow' });
            cy.login('admin', 'admin');
            cy.visit(`${baseUrl}/${submission2.id}`);
        });

        it('should be possible before the deadline', () => {
            // Open nested/timer.c
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Wait for file to be loaded.
            cy.get('.file-viewer')
                .should('be.visible');

            // Check that peer feedback is visible and approve it.
            cy.get('.code-viewer .feedback-area')
                .should('be.visible')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.info-text-wrapper .badge')
                        .should('contain', 'peer feedback');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                    cy.get('.peer-feedback-assessment .toggle-container')
                        .should('not.have.attr', 'checked', 'checked')
                        .find('.label-on')
                        .click();
                });
        });

        it('should be possible before the peer feedback deadline', () => {
            patchSettings({ deadline: 'yesterday' });
            cy.login('admin', 'admin');

            // Wait for file to be loaded.
            cy.get('.file-viewer')
                .should('be.visible');

            // Check that peer feedback is visible disapprove it.
            cy.get('.code-viewer .feedback-area')
                .should('be.visible')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.info-text-wrapper .badge')
                        .should('contain', 'peer feedback');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                    cy.get('.peer-feedback-assessment .toggle-container')
                        .should('have.attr', 'checked', 'checked')
                        .find('.label-off')
                        .click();
                });
        });

        it('should be possible when the assignment is "done"', () => {
            patchSettings({ state: 'done' });
            cy.login('admin', 'admin');
            cy.openCategory('Code');

            // Wait for file to be loaded.
            cy.get('.file-viewer')
                .should('be.visible');

            // Check that peer feedback is visible approve it.
            cy.get('.code-viewer .feedback-area')
                .should('be.visible')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.info-text-wrapper .badge')
                        .should('contain', 'peer feedback');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                    cy.get('.peer-feedback-assessment .toggle-container')
                        .should('not.have.attr', 'checked', 'checked')
                        .find('.label-on')
                        .click();
                });
        });
    });

    context('Viewing approved peer feedback', () => {
        before(() => {
            patchSettings({ state: 'open', deadline: 'tomorrow' });
            cy.login('student2', 'Student2');
            cy.visit(`${baseUrl}/${submission2.id}`);
        });

        it('should not be visible before the deadline', () => {
            // Open nested/timer.c
            cy.get('.file-tree')
                .contains('li', 'nested')
                .click()
                .contains('li', 'timer.c')
                .click();

            // Wait for file to be loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Check that peer feedback is visible.
            cy.get('.code-viewer .feedback-area')
                .should('not.exist');
        });

        it('should not be visible before the peer feedback deadline', () => {
            patchSettings({ deadline: 'yesterday' });
            cy.login('student2', 'Student2');

            // Wait for file to be loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Check that peer feedback is visible.
            cy.get('.code-viewer .feedback-area')
                .should('not.exist');
        });

        it('should not be visible before the assignment is "done"', () => {
            patchSettings({ amount: 1, time: 1, auto_approved: false });
            cy.login('student2', 'Student2');

            // Wait for file to be loaded.
            cy.get('.file-viewer .loader')
                .should('not.exist');

            // Check that peer feedback is visible.
            cy.get('.code-viewer .feedback-area')
                .should('not.exist');
        });

        it('should be visible in the code viewer', () => {
            patchSettings({ state: 'done', deadline: 'yesterday' });
            cy.login('student2', 'Student2');
            cy.openCategory('Code');

            // Wait for file to be loaded.
            cy.get('.file-viewer')
                .should('be.visible');

            // Check that peer feedback is visible.
            cy.get('.code-viewer .feedback-area')
                .should('be.visible')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.info-text-wrapper .badge')
                        .should('contain', 'peer feedback');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });

            // Check that the unapproved comment on venn1.png is not visible.
            cy.get('.file-tree')
                .contains('li', 'venn1.png')
                .click();

            // Wait for image to be loaded.
            cy.get('.image-viewer')
                .should('be.visible')
                .find('.img')
                .should('be.visible');

            // Check that the unapproved comment on venn1.png is not visible.
            cy.get('.floating-feedback-button .feedback-area')
                .should('not.exist');
        });

        it('should be visible in the feedback overview', () => {
            cy.openCategory('Feedback Overview');

            // Check that the author and feedback are correct for nested/timer.c.
            cy.get('.feedback-overview')
                .contains('.inner-feedback-viewer', 'nested/timer.c')
                .find('.feedback-area')
                .within(() => {
                    cy.get('.info-text-wrapper .user')
                        .should('contain', 'Student1');
                    cy.get('.feedback-reply-message-wrapper')
                        .should('contain', 'peer feedback');
                });

            // Check that the unapproved comment on venn1.png is not visible.
            cy.get('.feedback-overview')
                .contains('.inner-feedback-viewer', 'venn1.png')
                .should('not.exist');
        });
    });
});
