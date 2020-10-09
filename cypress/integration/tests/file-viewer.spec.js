context('FileViewer', () => {
    const uniqueName = `FileViewer ${Math.floor(Math.random() * 100000)}`;
    let course;
    let assignment;
    let submissionURL;

    before(() => {
        cy.visit('/');

        cy.createCourse(uniqueName, [
            { name: 'student1', role: 'Student' },
        ]).then(res => {
            course = res;

            return cy.createAssignment(course.id, uniqueName, {
                state: 'open',
                deadline: 'tomorrow',
            })
        }).then(res => {
            assignment = res;
            return cy.createSubmission(
                assignment.id,
                'test_submissions/all_filetypes.zip',
                { author: 'student1' },
            );
        }).then(res => {
            submissionURL = `/courses/${course.id}/assignments/${assignment.id}/submissions/${res.id}`;
        });
    });

    beforeEach(() => {
        cy.login('admin', 'admin');
        cy.visit(submissionURL);
        toggleDirectory('nested');
    });

    function toggleDirectory(dirname) {
        cy.get('.file-tree').contains('li', dirname).click();
    }

    function openFile(filename) {
        cy.get('.file-tree').contains('li', filename).click();
        cy.url().should('match', /\/files\/\d+/);
        cy.get('.file-viewer .loader').should('not.be.visible');
    }

    function addComment(selector, comment = 'comment') {
        cy.get(selector).first().click({ force: true });
        cy.get('.feedback-reply.editing').first().within(() => {
            cy.get('textarea').type(comment);
            cy.get('.submit-button[name=submit-feedback]').submit('success', {
                waitForDefault: false,
            });
        });
        cy.get('.feedback-reply.editing').should('not.exist');
    }

    context('Floating feedback button', () => {
        it('should open a scrollable feedback area', () => {
            cy.wrap([
                'venn1.png',
                'README.md',
                'thomas-schaper',
            ]).each(filename => {
                openFile(filename);
                cy.get('.file-viewer .feedback-button')
                    .click({ force: true });

                cy.get('.feedback-area-wrapper')
                    .should('be.visible');

                cy.get('.feedback-area-wrapper .save-button-wrapper .submit-button.btn-primary')
                    .as('save-button');

                // The save button should be visible right after opening the
                // feedback area.
                cy.get('@save-button')
                    .should('be.visible');

                // Resize the feedback area, making it smaller.  We need to
                // drag to somewhere _within_ the .rs-panes because rs-panes
                // listens to the mouseup event on the .rs-panes element. The
                // `force` is needed because cypress complains that the resizer
                // is blocked by another element, even though it isn't.
                cy.get('.file-viewer .Resizer')
                    .dragTo('@save-button', { force: true });

                // The save button should not be visible anymore because the
                // pane containing the feedback area has shrunk.
                cy.get('@save-button')
                    .should('not.be.visible');

                // The pane containing the feedback area should be scrollable.
                cy.get('.file-viewer .row.Pane:last-child')
                    .shouldBeScrollable('y');

                cy.get('.file-viewer .feedback-area-wrapper textarea')
                    .setText('comment');
                cy.get('@save-button')
                    .submit('success', { waitForDefault: false });

                // Wait for the feedback area to become non-editable.
                cy.get('.file-viewer .add-reply')
                    .should('be.visible');

                // Resize the feedback area.
                cy.get('.file-viewer .Resizer')
                    .dragTo('.file-viewer .add-reply', { force: true });

                cy.get('.file-viewer .add-reply')
                    .should('not.be.visible');

                // The feedback area should now be scrollable.
                cy.get('.file-viewer .row.Pane:last-child')
                    .shouldBeScrollable('y');

                cy.get('.file-viewer .submit-button[name="delete-feedback"]')
                    .submit('success', { hasConfirm: true, waitForDefault: false });
            });
        });
    });

    context('Inline feedback preference', () => {
        function openSettings() {
            cy.get('.local-header .settings-toggle')
                .click();
            cy.get('[id^="settings-popover"]')
                .should('not.have.class', 'fade')
                .should('be.visible');
            return cy.get('.settings-content')
                .should('be.visible');
        }

        function closeSettings() {
            cy.get('.local-header .settings-toggle')
                .click();
            cy.get('[id^="settings-popover"]')
                .should('not.be.visible');
            return cy.get('.settings-content')
                .should('not.be.visible');
        }

        function getSettingsToggle(name) {
            return openSettings()
                .contains('tr', name)
                .find('.toggle-container');
        }

        function hideComments() {
            getSettingsToggle('Inline feedback')
                .as('toggle')
                .find('.label-off')
                .click();
            cy.get('@toggle')
                .should('not.have.attr', 'checked');
            closeSettings();
        }

        function showComments() {
            getSettingsToggle('Inline feedback')
                .as('toggle')
                .find('.label-on')
                .click();
            cy.get('@toggle')
                .should('have.attr', 'checked');
            closeSettings();
        }

        it('should hide feedback when disabled', () => {
            function hideCommentsCheck() {
                hideComments();
                cy.get('.feedback-area').should('not.exist');
                showComments();
                cy.get('.feedback-area').should('exist');
            }

            openFile('timer.c')
            addComment('.inner-code-viewer .line');
            hideCommentsCheck();

            openFile('Graaf vinden');
            addComment('.inner-code-viewer .line');
            addComment('.result-cell .feedback-button');
            addComment('.markdown-wrapper .feedback-button');
            hideCommentsCheck();

            openFile('venn1.png');
            addComment('.image-viewer .feedback-button');
            hideCommentsCheck();

            openFile('thomas-schaper');
            addComment('.pdf-viewer .feedback-button');
            hideCommentsCheck();

            openFile('README.md');
            addComment('.markdown-viewer .feedback-button');
            hideCommentsCheck();
        });

        it('should be reset when going to another file', () => {
            openFile('timer.c');
            hideComments();
            openFile('lemon.c');
            getSettingsToggle('Inline feedback')
                .should('have.attr', 'checked')
                .should('eq', 'checked');
        });

        it('should make it impossible to add comments', () => {
            openFile('timer.c');
            hideComments();
            cy.get('.inner-code-viewer').should('not.have.class', 'editable');
            cy.get('.inner-code-viewer .line:nth-child(10)').click();
            cy.get('.feedback-area').should('not.exist');

            openFile('Graaf vinden');
            hideComments();
            cy.get('.inner-code-viewer').should('not.have.class', 'editable');
            cy.get('.inner-code-viewer .line').first().click();
            cy.get('.feedback-area').should('not.exist');
            cy.get('.inner-result-cell + .feedback-button').should('not.exist');
            cy.get('.inner-markdown-viewer + .feedback-button').should('not.exist');

            openFile('venn1.png');
            hideComments();
            cy.get('.image-viewer .feedback-button').should('not.exist');

            openFile('thomas-schaper');
            hideComments();
            cy.get('.pdf-viewer .feedback-button').should('not.exist');

            openFile('README.md');
            hideComments();
            cy.get('.markdown-viewer .feedback-button').should('not.exist');
        });
    });
});
