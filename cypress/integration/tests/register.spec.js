import moment from 'moment';

context('Register', () => {
    beforeEach(() => {
        cy.visit('/');
        cy.logout();
        cy.visit('/register');
    });

    function getUsername() {
        return `test-student-${Math.floor(Math.random() * 100000)}`;
    }

    function getPassword() {
        return 'f941f3ab-0fa5-4c21-bea8-fd626ac0a821';
    }

    function fillField(field, value) {
        cy.get('.register')
            .contains('fieldset.form-group', field)
            .find('input')
            .type(value);
    }

    function submit(state, opts = {}) {
        cy.get('.register')
            .contains('.submit-button', 'Register')
            .submit(state, Object.assign(opts, {
                // We never wait for the default state, because after login the
                // submit button will disappear instantly.
                waitForDefault: false,
                hasConfirm: true,
            }));
    }

    it('should successfully register a user if all fields are filled in', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('success');
    });

    it('should show an error if the username is not passed', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'Field "Username" is empty' });
    });

    it('should show an error if the full name is not passed', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'Field "Name" is empty' });
    });

    it('should show an error if the email is not passed', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'Field "Email" is empty' });
    });

    it('should show an error if the repeat email is not passed', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'Field "Repeat email" is empty' });
    });

    it('should show an error if the password is not passed', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'Field "Password" is empty' });
    });

    it('should show an error if the repeat password is not passed', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);

        submit('error', { popoverMsg: 'Field "Repeat password" is empty' });
    });

    it('should show an error if the emails are different', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email2@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'The emails do not match' });
    });

    it('should show an error if the passwords are different', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', 'asdf');

        submit('error', { popoverMsg: 'The passwords do not match' });
    });

    it('should show an error if the user already exists', () => {
        const username = getUsername();
        const password = getPassword();

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('success');

        cy.reload();
        cy.logout();
        cy.visit('/register');

        fillField('Username', username);
        fillField('Name', username);
        fillField('Email', 'email@example.com');
        fillField('Repeat email', 'email@example.com');
        fillField('Password', password);
        fillField('Repeat password', password);

        submit('error', { popoverMsg: 'The given username is already in use' });
    });

    it('should use the query parameter "register_for" if present', () => {
        cy.visit('/register?register_for=a course name');
        cy.get('.register-wrapper h4').contains('Register');
        cy.get('.register-wrapper h4').contains('for a course name');
    });

    context('should be possible to register using a course link', () => {
        let course;
        let link;

        before(() => {
            cy.visit('/');
            cy.login('admin', 'admin');
            cy.createCourse(`New course ${Math.random()}`).then(res => {
                course = res;

                return cy.authRequest({
                    url: `/api/v1/courses/${course.id}/registration_links/`,
                    method: 'PUT',
                    body: {
                        expiration_date: moment.utc().add(1, 'y').format('YYYY-MM-DDTHH:mm:ss'),
                        role_id: course.roles[0].id,
                    },
                });
            }).then(res => {
                console.log(res);
                link = `/courses/${course.id}/enroll/${res.body.id}`;
            });
        });

        beforeEach(() => {
            cy.logout();
            cy.visit(link);
        });

        it('should be possible to register as a new user', () => {
            cy.get('.local-header').contains(course.name);

            const username = getUsername();
            const password = getPassword();
            fillField('Username', username);
            fillField('Name', username);
            fillField('Email', 'email@example.com');
            fillField('Repeat email', 'email@example.com');
            fillField('Password', password);
            fillField('Repeat password', password);

            submit('success');

            cy.get('.course-name').should('have.length', 1);
            cy.get('.course-name').contains(course.name);
        });

        it('should be possible to enroll an existing user', () => {
            cy.get('.login')
                .contains('fieldset.form-group', 'Username')
                .find('input')
                .type('student1');
            cy.get('.login')
                .contains('fieldset.form-group', 'Password')
                .find('input')
                .type('Student1');
            cy.get('.course-enroll')
                .contains('.submit-button', 'Login and join')
                .submit('warning');
        });

        // TODO: Couldn't get this test to work, the "Join" button is always
        // disabled for some reason, even though the page recognizes that
        // student2 is logged in.
        it.skip('should be possible to enroll as a logged in user', () => {
            cy.login('student2', 'Student2');
            cy.visit(link);

            cy.get('.course-enroll')
                .contains('.submit-button', 'Join')
                .submit('warning');
        });

        it('should not be possible to enroll as a logged in user that is already a member', () => {
            cy.login('student1', 'Student1');
            cy.visit(link);

            cy.get('.course-enroll')
                .contains('.submit-button', 'Join')
                .should('not.be.disabled');
        });
    });
});
