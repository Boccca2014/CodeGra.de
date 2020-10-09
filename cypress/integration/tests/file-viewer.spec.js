context('FileViewer', () => {
    const uniqueName = `FileViewer ${Math.floor(Math.random() * 100000)}`;
    let course;
    let assignment;
    let submission;
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
                'test_submissions/hello.py',
                { author: 'student1' },
            );
        }).then(res => {
            return cy.createSubmission(
                assignment.id,
                'test_submissions/all_filetypes.zip',
                { author: 'student1' },
            );
        }).then(res => {
            submission = res;
            submissionURL = `/courses/${course.id}/assignments/${assignment.id}/submissions/${submission.id}`;
            cy.login('admin', 'admin');
            cy.visit(submissionURL);
            toggleDirectory('nested');
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

        before(() => {
            openFile('timer.c')
            addComment('.inner-code-viewer .line');

            openFile('Graaf vinden');
            addComment('.inner-code-viewer .line');
            addComment('.result-cell .feedback-button');
            addComment('.markdown-wrapper .feedback-button');

            openFile('venn1.png');
            addComment('.image-viewer .feedback-button');

            openFile('thomas-schaper');
            addComment('.pdf-viewer .feedback-button');

            openFile('README.md');
            addComment('.markdown-viewer .feedback-button');
        });

        it('should hide feedback when disabled', () => {
            function hideCommentsCheck() {
                hideComments();
                cy.get('.feedback-area').should('not.exist');
                showComments();
                cy.get('.feedback-area').should('exist');
            }

            openFile('timer.c')
            hideCommentsCheck();

            openFile('Graaf vinden');
            hideCommentsCheck();

            openFile('venn1.png');
            hideCommentsCheck();

            openFile('thomas-schaper');
            hideCommentsCheck();

            openFile('README.md');
            hideCommentsCheck();
        });

        it('should not show a warning when toggled manually', () => {
            openFile('timer.c');
            hideComments();
            cy.get('.file-viewer')
                .contains('.alert', 'Inline feedback is currently hidden')
                .should('not.exist');
        });

        it('should show a warning after reloading the page', () => {
            openFile('timer.c');
            hideComments();
            cy.reload();
            cy.get('.file-viewer')
                .contains('.alert', 'Inline feedback is currently hidden')
                .should('exist');
        });

        it('should be remembered when going to another submission', () => {
            hideComments();
            cy.get('.submission-nav-bar').within(() => {
                cy.get('.dropdown').click();
                cy.get('.dropdown-menu .loader').should('not.exist');
                cy.get('.dropdown-menu li:last').click();
            });
            cy.url().should('not.contain', '/submissions/' + String(submission.id));
            cy.get('.file-viewer')
                .contains('.alert', 'Inline feedback is currently hidden')
                .should('exist');
        });

        it('should be remembered when going back to the submissions list', () => {
            hideComments();
            cy.get('.local-header .back-button').click();
            cy.get('.submission-list')
                .contains('tr', 'Student1')
                .click();
            cy.get('.file-viewer')
                .contains('.alert', 'Inline feedback is currently hidden')
                .should('exist');
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
