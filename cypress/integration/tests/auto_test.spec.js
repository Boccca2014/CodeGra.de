context('Manage assignment page', () => {
    let course;
    let assignment;

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

        cy.createCourse('AutoTest').then(res => {
            course = res;

            return cy.createAssignment(course.id, 'AutoTest', {
                state: 'open',
                deadline: 'tomorrow',
            })
        }).then(res => {
            assignment = res;
        });
    });

    beforeEach(() => {
        cy.login('admin', 'admin');
        cy.visit(`/courses/${course.id}/assignments/${assignment.id}`);
        cy.openCategory('AutoTest', { timeout: 8000 });
    });

    context('Creating an AutoTest configuration', () => {
        it('should not be possible to create an AutoTest when there is no rubric', () => {
            cy.openCategory('Rubric');
            cy.get('.rubric-editor')
                .should('contain', 'This assignment does not have a rubric yet.');

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
                .submit('success');

            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.exist');

            cy.get('.auto-test')
                .contains('.submit-button', 'Delete')
                .submit('success', { hasConfirm: true });

            cy.get('.auto-test')
                .contains('.submit-button', 'Create AutoTest')
                .should('not.be.disabled');

            cy.openCategory('Rubric');
            cy.get('.rubric-editor')
                .find('.danger-buttons .btn:first')
                .click();
            cy.get('.modal-dialog')
                .contains('.submit-button', 'Yes')
                .submit('success');

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
                .submit('success');
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

                return (btnText ?  context.contains(btnClass, btnText) : context.find(btnClass))
                    .submit('default', {
                        hasConfirm: true,
                        waitForState: false,
                    });
            }

            submit('.modal-dialog', '', '.delete-step');
            submit('.modal-dialog', 'Delete');
            submit('.auto-test', 'Delete level');
            submit('.auto-test', 'Delete');
        });
    });
});
