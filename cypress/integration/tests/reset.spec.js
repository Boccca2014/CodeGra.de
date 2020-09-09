context('Reset password', () => {
    // We only test errors, as we would need a valid user/token combination to
    // successfully reset the password, but for that we need to receive an
    // email...
    beforeEach(() => {
        cy.visit('/reset_password/?user=1&token=1');
    });

    function fillNew(pw) {
        cy.get('input[name="password"]').type(pw);
    }

    function fillConfirm(pw) {
        cy.get('input[name="repeat-password"]').type(pw);
    }

    function fillBoth(pw1, pw2) {
        fillNew(pw1);
        fillConfirm(pw2 == null ? pw1 : pw2);
    }

    it('should show an error when both inputs are empty', () => {
        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'The new password may not be empty',
        });
    });

    it('should show an error when the new password is empty', () => {
        fillConfirm('abc');

        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'The passwords don\'t match',
        });
    });

    it('should show an error when the confirm password is empty', () => {
        fillNew('abc');

        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'The passwords don\'t match',
        });
    });

    it('should show an error when the passwords are not the same', () => {
        fillBoth('abc', 'def');

        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'The passwords don\'t match',
        });
    });

    it('should show an error when the password is too easy', () => {
        fillBoth('abc');

        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'easy to guess',
        });
    });

    it('should show an error when the user/token combination is invalid', () => {
        fillBoth('b48d36d0-4459-46ef-9afe-c7323441292e');

        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'The given token is not valid',
        });
    });

    it('should show an error when the user does not exist', () => {
        // Invalid user id
        cy.visit('/reset_password/?user=10000000000&token=1');

        fillBoth('b48d36d0-4459-46ef-9afe-c7323441292e');

        cy.get('.submit-button').submit('error', {
            hasConfirm: true,
            popoverMsg: 'The requested "User" was not found',
        });
    });
});
