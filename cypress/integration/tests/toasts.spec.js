context('General messages', () => {
    // It is not possible to stub a "no response" in Cypress, so we can't
    // really test this.
    it.skip('Should show a toast if the server does not respond within a few seconds', () => {
        cy.visit('/');
        cy.login('admin', 'admin');

        cy.server();
        cy.route({
            method: 'GET',
            url: '/api/v1/**',
            response: '',
            status: 0,
        });

        // A request must be sent to the server, so just reload the courses.
        cy.get('.sidebar').within(() => {
            cy.get('.sidebar-entry-courses').click();
            cy.get('.submenu:last .refresh-button').click();
        });

        cy.wait(10000);
        cy.get('.toast')
            .should('contain', 'Unknown error')
            .should('be.visible');
    });

    it('should not show a toast with the same tag twice', () => {
        cy.visit('/');
        cy.login('admin', 'admin');

        const toastData = {
            tag: 'TestToast',
            title: 'Test Toast',
            message: 'Test Toast',
        };

        cy.window().then($window => {
            $window.__app__.$emit('cg::app::toast', toastData);
        });

        cy.get('.toast')
            .should('contain', 'Test Toast')
            .should('be.visible');

        cy.window().then($window => {
            $window.__app__.$emit('cg::app::toast', toastData);
        });

        cy.get('.toast')
            .should('have.length', 1)
            .should('contain', 'Test Toast')
            .should('be.visible');
    });

    it('should show the same toast for a second time, after it has been closed', () => {
        cy.visit('/');
        cy.login('admin', 'admin');

        const toastData = {
            tag: 'TestToast',
            title: 'Test Toast',
            message: 'Test Toast',
        };

        cy.window().then($window => {
            $window.__app__.$emit('cg::app::toast', toastData);
        });

        cy.get('.toast')
            .should('contain', 'Test Toast')
            .should('be.visible')
            .find('.close')
            .click();

        cy.get('.toast').should('not.exist');

        cy.window().then($window => {
            $window.__app__.$emit('cg::app::toast', toastData);
        });

        cy.get('.toast')
            .should('contain', 'Test Toast')
            .should('be.visible')
    });

    it('Should show a toast if the session has expired', () => {
        cy.visit('/');
        cy.login('admin', 'admin');

        cy.server();
        cy.route({
            method: 'GET',
            url: '/api/v1/**',
            response: '',
            status: 401,
        });

        cy.get('.toast')
            .should('contain', 'Not logged in')
            .should('contain', 'Your session has expired')
            .should('be.visible');
    });

    it('should show a toast if the jwt token is invalid', () => {
        cy.visit('/');
        cy.login('admin', 'admin');

        cy.window().then($window => {
            $window.__app__.$store.commit('user/SET_ACCESS_TOKEN', 'xxx');
        });

        // A request must be sent to the server, so just reload the courses.
        cy.get('.sidebar').within(() => {
            cy.get('.sidebar-entry-assignments').click();
        });

        cy.get('.toast')
            .should('contain', 'Not logged in')
            .should('contain', 'Your session has expired')
            .should('be.visible');
    });

    it('should show a toast if a non logged-in user requests a resource that needs authorization', () => {
        cy.visit('/');
        cy.login('admin', 'admin');

        cy.window().then($window => {
            $window.__app__.$store.commit('user/SET_ACCESS_TOKEN', null);
        });

        // A request must be sent to the server, so just reload the courses.
        cy.get('.sidebar').within(() => {
            cy.get('.sidebar-entry-assignments').click();
        });

        cy.get('.toast')
            .should('contain', 'Not logged in')
            .should('contain', 'You are currently not logged in.')
            .should('be.visible');
    });
});
