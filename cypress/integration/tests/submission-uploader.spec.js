context('Submission uploader', () => {
    let course;
    let assignment;

    function goToManage() {
        cy.visit(`/courses/${course.id}/assignments/${assignment.id}`);
        return cy.get('.page.manage-assignment').should('be.visible');
    }

    function goToSubmissions() {
        cy.visit(`/courses/${course.id}/assignments/${assignment.id}/submissions`);
        return cy.get('.page.submissions').should('be.visible');
    }

    function toggleTestSubmission() {
        cy.get('.submission-uploader')
            .contains('.custom-checkbox', 'Test submission')
            .find('input')
            .click({ force: true });
    }

    function setUploadAuthor(author) {
        cy.get('.submission-uploader')
            .find('.multiselect')
            .multiselect([author]);
    }

    function getGitCheck() {
        return cy.get('.manage-assignment')
            .contains('.custom-checkbox', 'GitHub/GitLab')
            .find('input[type="checkbox"]');
    }

    function toggleGitSubs(value = true) {
        return getGitCheck()
            .should(value ? 'not.be.checked' : 'be.checked')
            .click({ force: true }) // Actual <input> is invisible.
            .parentsUpto('.assignment-submission-settings')
            .find('.submit-button')
            .submit('success');
    }

    function getFileCheck() {
        return cy.get('.manage-assignment')
            .contains('.custom-checkbox', 'File uploader')
            .find('input[type="checkbox"]');
    }

    function toggleFileSubs(value = true) {
        return getFileCheck()
            .should(value ? 'not.be.checked' : 'be.checked')
            .click({ force: true })
            .parentsUpto('.assignment-submission-settings')
            .find('.submit-button')
            .submit('success');
    }

    function selectFile(fileName) {
        cy.get('.multiple-files-uploader .dropzone')
            .should('be.visible')
            .as('dropzone');

        return cy.fixture(fileName, 'utf8').then(fileContent => {
            cy.get('@dropzone').upload(
                {
                    fileName,
                    fileContent,
                    mimeType: 'text/x-python',
                    encoding: 'utf8',
                },
                { subjectType: 'drag-n-drop' },
            );

            return cy.wrap([fileName, fileContent]);
        });
    }

    function uploadFiles(opts) {
        const { author, testSub, submitOpts } = Object.assign({
            author: '',
            testSub: false,
            submitOpts: { waitForState: false },
        }, opts);

        return selectFile('test_submissions/hello.py').then(
            async ([fileName, fileContent]) => {
                if (testSub) {
                    await cy.get('.submission-uploader')
                        .contains('.custom-control', 'Test submission')
                        .click();
                } else if (author) {
                    await cy.get('.submission-uploader .user-selector').multiselect([author]);
                }

                await cy.get('.submission-uploader .submit-button').submit('success', Object.assign({
                    waitForState: false,
                }, submitOpts));

                await cy.url().should('contain', '/files/');

                return cy.wrap([fileName, fileContent]);
            },
        );
    }

    before(() => {
        cy.visit('/');
        cy.createCourse('SubmissionUploader', [
            { name: 'student1', role: 'Student' },
            { name: 'student3', role: 'Student' },
            { name: 'robin', role: 'Teacher' },
        ]).then(res => {
            course = res;
        });
    });

    beforeEach(() => {
        cy.login('admin', 'admin');
    });

    context('No deadline set', () => {
        before(() => {
            cy.createAssignment(course.id, 'NoDeadline', {
                state: 'open',
            }).then(res => {
                assignment = res;
            });
        });

        beforeEach(() => {
            goToSubmissions();
        });

        it('should be visible to teachers when the assignment has no deadline', () => {
            cy.login('robin', 'Robin');

            cy.get('.submission-uploader')
                .should('be.visible');
            cy.get('.page.submissions .no-deadline-alert')
                .should('be.visible')
                .text()
                .should('contain', 'The deadline for this assignment has not yet been set. You can update the deadline here.');
            cy.get('.page.submissions .no-deadline-alert')
                .contains('a', 'here')
                .should('be.visible');
        });

        it('should be possible to do test submissions', () => {
            cy.get('.submission-uploader')
                .should('be.visible');
            cy.get('.submission-uploader .user-selector')
                .should('have.class', 'disabled')
                .find('input')
                .should('be.disabled');
            cy.get('.submission-uploader .test-student-checkbox input')
                .should('be.disabled');
            cy.get('.submission-uploader .submit-button')
                .should('be.disabled');

            uploadFiles();

            cy.get('.page.submission').should('exist');
            cy.get('.submission-nav-bar').should('contain', 'Test Student');
        });

        it('should not be visible to students when the assignment has no deadline', () => {
            cy.login('student1', 'Student1');
            goToSubmissions();

            cy.get('.page.submissions')
                .should('be.visible');
            cy.get('.action-buttons')
                .contains('.action-button', 'Upload files')
                .find('.disabled')
                .should('exist');
            cy.get('.submission-uploader')
                .should('not.be.visible');
        });
    });

    context('Test student checkbox', () => {
        before(() => {
            cy.createAssignment(course.id, 'TestStudentCheckbox', {
                state: 'open',
                deadline: 'tomorrow',
            }).then(res => {
                assignment = res;
            });
        });

        beforeEach(() => {
            goToSubmissions();
        });

        it('should not be visible for students', () => {
            cy.login('student1', 'Student1');

            cy.get('.submission-uploader')
                .contains('.custom-checkbox', 'Test submission')
                .should('not.exist');
        });

        it('should be visible for teachers', () => {
            cy.login('admin', 'admin');

            cy.get('.submission-uploader')
                .contains('.custom-checkbox', 'Test submission')
                .should('exist');
        });

        it('should be disabled if a submission author is set', () => {
            cy.login('admin', 'admin');

            setUploadAuthor('Student1');

            cy.get('.submission-uploader')
                .contains('.custom-checkbox', 'Test submission')
                .find('input[type="checkbox"]')
                .should('be.disabled');
        });
    });

    context('Other author', () => {
        before(() => {
            cy.createAssignment(course.id, 'OtherAuthorCheckbox', {
                state: 'open',
                deadline: 'tomorrow',
            }).then(res => {
                assignment = res;
            });
        });

        beforeEach(() => {
            goToSubmissions();
        });

        it('should not be visible for students', () => {
            cy.login('student1', 'Student1');

            cy.get('.submission-uploader')
                .find('.user-selector')
                .should('not.exist');
            cy.get('.submission-uploader')
                .find('.deadline-information')
                .should('exist');
        });

        it('should be visible for teachers', () => {
            cy.login('admin', 'admin');

            cy.get('.submission-uploader')
                .find('.user-selector')
                .should('exist');
            cy.get('.submission-uploader')
                .find('.deadline-information')
                .should('not.exist');
        });

        it('should be disabled if the Test Student checkbox is selected', () => {
            cy.login('admin', 'admin');

            toggleTestSubmission();

            cy.get('.submission-uploader')
                .find('.user-selector input')
                .should('be.disabled');
        });
    });

    context('File submissions', () => {
        before(() => {
            cy.createAssignment(course.id, 'FileSubmissions', {
                state: 'open',
                deadline: 'tomorrow',
            }).then(res => {
                assignment = res;
            });
        });

        it('should hide the file uploader when file submissions are disabled', () => {
            goToManage();
            // We must enable git submissions to be able to disable file
            // submissions.
            toggleGitSubs();
            toggleFileSubs(false);
            cy.get('.submission-uploader')
                .find('.multiple-files-uploader')
                .should('not.exist');
            toggleFileSubs();
            cy.get('.submission-uploader')
                .find('.multiple-files-uploader')
                .should('exist');
        });

        it('should disable the submit button when no files are selected', () => {
            goToSubmissions();

            cy.get('.submission-uploader .submit-button')
                .should('be.disabled');

            selectFile('test_submissions/hello.py');

            cy.get('.submission-uploader .submit-button')
                .should('not.be.disabled');
        });

        it('should be possible to upload something', () => {
            goToSubmissions();

            uploadFiles({
                submitOpts: { hasConfirm: true },
            }).then(([fileName, fileContent]) => {
                const lines = fileContent.split('\n');

                cy.openCategory('Code');
                cy.get('.file-tree').contains('li', 'hello.py').click();

                cy.get('.inner-code-viewer .line').each(($line, i) => {
                    cy.wrap($line).should('contain', lines[i]);
                });
            });
        });

        it('should be possible to upload something as someone else', () => {
            goToSubmissions();

            uploadFiles({
                author: 'Student1',
            }).then(() => {
                cy.get('.submission-nav-bar').should('contain', 'Student1');
            });
        });

        it('should be possible to upload something as test student', () => {
            goToSubmissions();

            uploadFiles({
                testSub: true,
            }).then(() => {
                cy.get('.submission-nav-bar').should('contain', 'Test Student');
            });
        });

        it('should show and update submission limits', () => {
            let amount;
            return cy.authRequest({
                url: `/api/v1/assignments/${assignment.id}`,
                method: 'PATCH',
                body: {
                    max_submissions: 10,
                    cool_off_period: 0,
                },
            }).then(() => {
                goToSubmissions();

                cy.get('.submission-limiting')
                    .find('.loader')
                    .should('not.exist');

                cy.get('.submission-limiting')
                    .text()
                    .then(($div) => {
                        const $txt = $div.replace(/\n/g, ' ').replace(/  +/g, ' ');
                        expect($txt).to.match(/You have [0-9]+ submissions left out of 10\./);
                        amount = $txt.match(/You have ([0-9]+)/)[1];
                        expect(amount).to.be.gt(1);
                    });

                // Should not be visible when the test student is active.
                cy.get('.submission-uploader')
                    .contains('.custom-checkbox', 'Test submission')
                    .click();
                cy.get('.submission-limiting').should('not.exist')
                cy.get('.submission-uploader')
                    .contains('.custom-checkbox', 'Test submission')
                    .click();

                return uploadFiles({ submitOpts: { hasConfirm: true } })
            }).then(() => {
                cy.get('.local-header .back-button').click();

                cy.get('.submission-limiting')
                    .find('.loader')
                    .should('not.exist');
                cy.get('.submission-limiting')
                    .text()
                    .should('contain', `You have ${amount - 1} submissions left out of 10.`);
            });
        });

        it('should show and update cool off periods', () => {
            function checkSubmissionText(txt) {
                cy.get('.submission-limiting').find('.loader').should('not.exist');
                cy.get('.submission-limiting')
                    .text()
                    .then($txt => {
                        if (txt instanceof RegExp) {
                            expect($txt.trim()).to.match(txt);
                        } else {
                            expect($txt.trim()).to.eq(txt);
                        }
                    });
            }

            function goBack() {
                cy.get('.local-header .back-button').click();
            }

            return cy.authRequest({
                url: `/api/v1/assignments/${assignment.id}`,
                method: 'PATCH',
                body: {
                    max_submissions: null,
                    cool_off_period: 60,
                    amount_in_cool_off_period: 2,
                },
            }).then(() => {
                goToSubmissions();
                setUploadAuthor('Student3');
                checkSubmissionText('Student3 has 0 submissions. You may submit twice every minute.');

                return uploadFiles();
            }).then(() => {
                goBack();

                setUploadAuthor('Student3');
                checkSubmissionText('Student3 has 1 submission. You may submit twice every minute.');

                return uploadFiles();
            }).then(() => {
                goBack();

                setUploadAuthor('Student3');
                checkSubmissionText(
                    'Student3 has 2 submissions. You may submit twice every minute. ' +
                        'Student3 submitted twice in the past few seconds, ' +
                        'therefore must wait for a minute.'
                );

                cy.login('student3', 'Student3');

                goToSubmissions();
                cy.get('.action-buttons')
                    .contains('.action-button', 'Upload files')
                    .click();
                checkSubmissionText(
                    new RegExp('You have 2 submissions. You may submit twice every minute. ' +
                        'You submitted twice in the past few seconds, ' +
                        'therefore you must wait for (a minute|a few seconds).')
                );


            });
        });
    });

    context('Git submissions', () => {
        let i = 0;

        beforeEach(() => {
            cy.server();

            cy.createAssignment(course.id, `GitSubmissions${i++}`, {
                state: 'open',
                deadline: 'tomorrow',
            }).then(res => {
                assignment = res;
            });
        });

        function getGitLink(shouldFind = true) {
            return cy.get('.submission-uploader').find('.git-link').should(
                shouldFind ? 'exist' : 'not.exist',
            );
        }

        function openWebhookModal() {
            cy.route({
                method: 'POST',
                url: '/api/v1/assignments/*/webhook_settings?*',
            }).as('webhookRequest');

            getGitLink().click();
            cy.wait('@webhookRequest', { timeout: 10000 });

            return cy.get('#git-instructions-modal').should('be.visible');
        }

        function closeWebhookModal() {
            cy.get('#git-instructions-modal')
                .find('button.close')
                .click();
            cy.get('#git-instructions-modal')
                .should('not.be.visible');
        }

        function getWebhookData(provider = 'github') {
            cy.wrap({}).as('webhookData');

            openWebhookModal().as('modal');

            cy.get('@modal')
                .find(`.logo.${provider}`)
                .click();
            cy.get('@modal')
                .find('.public-key')
                .text()
                .then(publicKey =>
                    cy.get('@webhookData').then(data => { data.publicKey = publicKey }),
                );
            cy.get('@modal')
                .find('.next-button').click();
            cy.get('@modal')
                .find('.webhook-url .form-control')
                .text()
                .then(url =>
                    cy.get('@webhookData').then(data => { data.url = url }),
                );
            cy.get('@modal')
                .find('.webhook-secret .form-control')
                .text()
                .then(secret =>
                    cy.get('@webhookData').then(data => { data.secret = secret }),
                );

            closeWebhookModal();

            return cy.get('@webhookData');
        }

        function doAction(name) {
            cy.get('.action-buttons')
                .contains('.action-button', name)
                .click();
        }

        it('should not show git instructions when git submissions are disabled', () => {
            goToManage();
            getGitCheck().should('not.be.checked');
            getGitLink(false);
            goToSubmissions();
            getGitLink(false);
        });

        it('should show git instructions when git submissions are enabled', () => {
            goToManage();
            toggleGitSubs();
            getGitLink();
            goToSubmissions();
            getGitLink();

            cy.login('student1', 'Student1');
            goToSubmissions();
            doAction('Upload files');
            getGitLink(false);
        });

        it('should show a modal upon clicking the git instructions link', () => {
            goToManage();
            toggleGitSubs();

            function checkPages(provider) {
                openWebhookModal().as('modal');

                cy.get('@modal')
                    .find(`.logo.${provider}`)
                    .should('exist')
                    .click();
                cy.get('@modal')
                    .find('.next-button')
                    .click()
                    .should('be.visible')
                    .click()
                    .should('not.be.visible');
                cy.get('@modal')
                    .find('.prev-button')
                    .click()
                    .should('be.visible')
                    .click()
                    .should('be.visible')
                    .click()
                    .should('not.be.visible');

                closeWebhookModal();
            }

            checkPages('github');
            checkPages('gitlab');
        });

        it('should show the same values for GitHub and GitLab', () => {
            goToManage();
            toggleGitSubs();

            getWebhookData('github').then(githubData => {
                getWebhookData('gitlab').should('deep.eq', githubData);
            });
        });

        it('should show different values for the current user, other user, test user', () => {
            goToManage();
            toggleGitSubs();

            getWebhookData().as('currentUserData');

            toggleTestSubmission();
            getWebhookData().as('testStudentData');
            toggleTestSubmission();

            setUploadAuthor('student1');
            getWebhookData().as('realStudentData');

            cy.getAll(['@currentUserData', '@testStudentData', '@realStudentData']).then(
                ([currUser, testUser, realUser]) => {
                    expect(currUser).not.to.deep.equal(testUser);
                    expect(testUser).not.to.deep.equal(realUser);
                    expect(realUser).not.to.deep.equal(currUser);
                });
        });

        it('should change the instruction link text when test submission is checked', () => {
            goToManage();
            toggleGitSubs();

            getGitLink().text().then(gitLinkText => {
                toggleTestSubmission();
                getGitLink().text()
                    .should('not.eq', gitLinkText)
                    .should('contain', 'test student');
            });
        });

        it('should change the instruction link text when an author has been specified', () => {
            goToManage();
            toggleGitSubs();

            getGitLink().text().then(gitLinkText => {
                setUploadAuthor('student1');
                getGitLink().text()
                    .should('not.eq', gitLinkText)
                    .should('contain', 'Student1');
            });
        });
    });
});
