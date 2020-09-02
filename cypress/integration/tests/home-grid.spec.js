context('HomeGrid', () => {
    beforeEach(() => {
        cy.visit('/');
    });

    it('should show all courses with gear', () => {
        cy.login('robin', 'Robin');
        cy.visit('/');
        cy.get('.page.home .home-grid').should('exist');
        cy.get('.course-wrapper .course-name').should('contain', 'Programmeertalen');
        cy.get('.course-wrapper .course-manage').should('have.length.at.least', 2);
    });

    it('should not show a gear for students', () => {
        cy.login('student1', 'Student1');
        cy.visit('/');
        cy.get('.page.home .home-grid').should('exist');
        cy.get('.course-wrapper .course-name').should('contain', 'Programmeertalen');
        cy.get('.course-wrapper .course-manage').should('have.length', 0);
    });

    it('should go the submissions of an assignment when clicking', () => {
        cy.login('robin', 'Robin');
        cy.visit('/');
        cy.get('.page.home .home-grid').should('exist');
        cy.get('.course-wrapper .assignment-list-item').first().click();
        cy.url().should('match', /.+assignments\/[0-9]+\/submissions.*/);
    });

    it('should go the manage course page when clicking gear', () => {
        cy.login('robin', 'Robin');
        cy.visit('/');
        cy.get('.page.home .home-grid').should('exist');
        cy.get('.course-wrapper .course-manage').first().click();
        cy.url().should('match', /\/courses\/[0-9]+/);
    });

    it('should show the entire date for courses with the same name', () => {
        const now = new Date().toISOString().slice(0, 10);
        const name1 = `Duplicate course - ${Math.random()}`;
        const name2 = `Unique course - ${Math.random()}`;

        cy.login('admin', 'admin');
        cy.createCourse(name1).then(() => {
            return cy.createCourse(name1);
        }).then(() => {
            return cy.createCourse(name2);
        }).then(() => {
            cy.visit('/');

            cy.get(`.course-name:contains(${name1})`).should('have.length', 2);
            cy.get(`.course-name:contains(${name1})`).should('contain', now);

            // There should be a course with name2
            cy.get(`.course-name:contains(${name2})`).should('have.length', 1);

            // But it should not include the date in any way
            cy.get(`.course-name:contains(${name2})`).should('not.contain', '()');
            cy.get(`.course-name:contains(${name2})`).should('not.contain', now);
        });
    });
});
