context('Rubric Editor', () => {
    let unique = Math.floor(Math.random() * 100000);
    let course;
    let assignment;

    class RubricItem {
        constructor(points) {
            this.points = points;
            this.header = `${points} points`;
            this.description = `${points} points`;
        }
    }

    class RubricRow {
        constructor(type, header, items) {
            this.type = type;
            this.header = header;
            this.description = header;
            this.items = items;
        }
    }

    class NormalRow extends RubricRow {
        constructor(header, items) {
            super('normal', header, items);
        }
    }

    class ContinuousRow extends RubricRow {
        constructor(header, items) {
            super('continuous', header, items);
        }
    }

    class Rubric extends Array {
        constructor(...rows) {
            super(...rows.map((rowItems, i) => {
                const items = rowItems.map(points => new RubricItem(points));
                return items.length > 1 ?
                    new NormalRow(`rubric row ${i}`, items) :
                    new ContinuousRow(`rubric row ${i}`, items);
            }));
        }
    }

    before(() => {
        cy.visit('/');
        cy.createCourse(
            `Rubric Editor Course ${unique}`,
            [{ name: 'student1', role: 'Student' }],
        ).then(res => {
            course = res;
            cy.createAssignment(
                course.id,
                `Rubric Editor Assignment ${unique}`,
                { state: 'open', deadline: 'tomorrow' },
            ).then(res => {
                assignment = res;
            });
        });
    });

    beforeEach(() => {
        cy.login('admin', 'admin');
        cy.deleteRubric(assignment.id, {
            failOnStatusCode: false,
        });
    });

    context('Creating a new rubric', () => {
        beforeEach(() => {
            cy.visit(`/courses/${course.id}/assignments/${assignment.id}#rubric`);
            cy.get('.page.manage-assignment')
                .should('exist')
                .find('.loader')
                .should('not.be.visible');
        });

        it('should be an option when an assignment has no rubric', () => {
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Create new rubric')
                .should('be.visible');
        });

        it('should show a back button when no categories have been created yet', () => {
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Create new rubric')
                .click();
            cy.get('.rubric-editor')
                .contains('.btn', 'Go back')
                .should('be.visible');
            cy.get('.rubric-editor .btn.add-row.normal')
                .click();
            cy.get('.rubric-editor')
                .contains('.btn', 'Go back')
                .should('not.exist');
            cy.get('.rubric-editor')
                .find('.submit-button.delete-category')
                .submit('success', {
                    hasConfirm: true,
                    waitForDefault: false,
                });
            cy.get('.rubric-editor')
                .contains('.btn', 'Go back')
                .should('be.visible')
                .click();
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Create new rubric')
                .should('be.visible');
        });

        it('should create an empty rubric', () => {
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Create new rubric')
                .click();

            cy.get('.rubric-editor .category-item')
                .should('not.exist');
            cy.get('.rubric-editor .btn.add-row')
                .should('be.visible')
                .should('have.length', 2);
            cy.get('.rubric-editor .no-categories')
                .should('be.visible');
            cy.get('.rubric-editor input.max-points')
                .should('have.value', '');
        });

        it('should not be possible to submit an empty rubric', () => {
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Create new rubric')
                .click();

            cy.get('.rubric-editor .submit-button.submit-rubric')
                .should('be.disabled');
        });
    });

    context('Copying a rubric', () => {
        let copyAssig;

        function loadPage(reload=false) {
            if (reload) {
                cy.reload();
            } else {
                cy.visit(`/courses/${course.id}/assignments/${copyAssig.id}#rubric`);
            }
            cy.get('.page.manage-assignment')
                .should('exist')
                .find('.loader')
                .should('not.be.visible');
            cy.get('.rubric-editor .loader')
                .should('not.be.visible');
        }

        before(() => {
            cy.createAssignment(course.id, `Copy Rubric Assignment ${unique}`).then(res => {
                copyAssig = res;
            });
        });

        beforeEach(() => {
            cy.deleteRubric(copyAssig.id, {
                failOnStatusCode: false,
            });
            loadPage();
        });

        it('should be an option when an assignment has no rubric', () => {
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Copy a rubric')
                .should('be.visible');
        });

        it('should show a back button after clicking the copy button', () => {
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Copy a rubric')
                .click();
            cy.get('.rubric-editor')
                .contains('.btn', 'Go back')
                .click();
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Copy a rubric')
                .should('be.visible');
        });

        it('should copy the contents of normal rows', () => {
            const rubric = new Rubric([0, 1, 2], [4, 8, 16]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Copy a rubric')
                .click()
            cy.get('.rubric-editor')
                .find('.assignment-selector')
                .multiselect([assignment.name]);
            cy.get('.rubric-editor')
                .contains('.submit-button', 'Import')
                .submit('success', { waitForDefault: false });

            for (let i = 0; i < rubric.length; i++) {
                const row = rubric[i];

                cy.get(`.rubric-editor .category-item:nth(${i})`)
                    .as('row')
                    .click();
                cy.get('@row')
                    .find('.category-name')
                    .should('have.value', row.header);
                cy.get('@row')
                    .find('.category-description textarea')
                    .should('have.value', row.description);

                for (let j = 0; j < row.items.length; j++) {
                    const item = row.items[j];
                    cy.get('@row')
                        .find(`.rubric-item:nth-child(${j + 1})`)
                        .within(() => {
                            cy.get('.points')
                                .should('have.value', item.points.toString());
                            cy.get('.header')
                                .should('have.value', item.header);
                            cy.get('.description textarea')
                                .should('have.value', item.description);
                        });
                }
            }
        });

        it('should copy the contents of continuous rows', () => {
            const rubric = new Rubric([1], [4]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Copy a rubric')
                .click()
            cy.get('.rubric-editor')
                .find('.assignment-selector')
                .multiselect([assignment.name]);
            cy.get('.rubric-editor')
                .contains('.submit-button', 'Import')
                .submit('success', { waitForDefault: false });

            for (let i = 0; i < rubric.length; i++) {
                const row = rubric[i];

                cy.get(`.rubric-editor .category-item:nth(${i})`)
                    .as('row')
                    .click();
                cy.get('@row')
                    .find('.category-name')
                    .should('have.value', row.header);
                cy.get('@row')
                    .find('.category-description textarea')
                    .should('have.value', row.description);
                cy.get('@row')
                    .find('.points')
                    .should('have.value', row.items[0].points.toString());
            }
        });
    });

    context('Editing an existing rubric', () => {
        const rubricPoints = [[1], [0, 1, 2, 3], [2], [0, 4, 5, 6]];
        const rubric = new Rubric(...rubricPoints);

        function addRow(type) {
            cy.get(`.rubric-editor .btn.add-row.${type}`)
                .click();
            cy.get('.rubric-editor .category-item:last')
                .should('contain', 'Unnamed')
                .should('not.have.class', 'rubric-row-enter-active');
        }

        function addNormalRow(header, description) {
            addRow('normal');

            if (header != null) {
                cy.get('.rubric-editor-row:last .category-name')
                    .type(header);
            }

            if (description != null) {
                cy.get('.rubric-editor-row:last .category-description textarea')
                    .type(description);
            }
        }

        function addContinuousRow(header, description, points) {
            addRow('continuous');

            if (header != null) {
                cy.get('.rubric-editor-row:last .category-name')
                    .type(header);
            }

            if (description != null) {
                cy.get('.rubric-editor-row:last .category-description textarea')
                    .type(description);
            }

            if (points != null) {
                cy.get('.rubric-editor-row:last .points')
                    .type(points.toString());
            }
        }

        function addItem(points, header, description, row=null) {
            row = row == null ? 'last' : `nth(${row})`;

            cy.get(`.rubric-editor-row:${row}`).as('row');
            cy.get('@row').find('.rubric-item.add-button').click();
            cy.get('@row').find('.rubric-item:nth-last-child(2)').as('item');

            if (points != null) {
                cy.get('@item').find('.points').type(points.toString());
            }

            if (header != null) {
                cy.get('@item').find('.header').type(header);
            }

            if (description != null) {
                cy.get('@item').find('.description textarea').type(description);
            }
        }

        function getRow(name) {
            return cy.get('.rubric-editor').contains('.category-item', name);
        }

        function showRow(name) {
            return getRow(name).click();
        }

        function deleteRow(name) {
            getRow(name)
                .find('.submit-button.delete-category')
                .submit('success', {
                    hasConfirm: true,
                    waitForDefault: false,
                });
            getRow(name).should('not.exist');
        }

        function submit(...args) {
            return cy.get('.rubric-editor .submit-button.submit-rubric')
                .should('not.be.disabled')
                .submit(...args);
        }

        function loadPage(reload=false) {
            if (reload) {
                cy.reload();
            } else {
                cy.visit(`/courses/${course.id}/assignments/${assignment.id}#rubric`);
            }
            cy.get('.page.manage-assignment')
                .should('exist')
                .find('.loader')
                .should('not.be.visible');
            cy.get('.rubric-editor .loader')
                .should('not.be.visible');
        }

        beforeEach(() => {
            cy.createRubric(assignment.id, rubric);
            loadPage();
        });

        it('should render the correct type of row', () => {
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor .rubric-editor-row').each(($row, i) => {
                cy.wrap($row).should('have.class', rubric[i].type);
            });
        });

        it('should be possible to add a normal rubric row', () => {
            addNormalRow('Normal Row', 'Description');
            addItem(0, '0 points');
            addItem(1, '1 point');
            submit('success');
            loadPage(true);

            showRow('Normal Row').within(() => {
                cy.get('.category-name')
                    .should('have.value', 'Normal Row');
                cy.get('.category-description textarea')
                    .should('have.value', 'Description');
            });
        });

        it('should be possible to delete a normal rubric row', () => {
            addNormalRow('Normal Row');
            addItem(0, '0 points');
            addItem(1, '1 point');
            submit('success');
            loadPage(true);

            deleteRow('Normal Row');
            getRow('Normal Row').should('not.exist');
            submit('success', {
                hasConfirm: true,
            });
            loadPage(true);

            getRow('Normal Row').should('not.exist');
        });

        it('should only delete normal rows after submitting the rubric', () => {
            addNormalRow('Normal Row');
            addItem(0, '0 points');
            addItem(1, '1 point');
            submit('success');
            loadPage(true);

            deleteRow('Normal Row');
            getRow('Normal Row').should('not.exist');
            loadPage(true);

            getRow('Normal Row').should('exist');
        });

        it('should be possible to add items to a normal rubric row', () => {
            addNormalRow('Normal Row');
            addItem(0, '0 points', '0 points');
            addItem(1, '1 point', '1 point');
            submit('success');
            loadPage(true);

            showRow('Normal Row').within(() => {
                cy.get('.rubric-item:nth-child(1)').within(() => {
                    cy.get('.points').should('have.value', '0');
                    cy.get('.header').should('have.value', '0 points');
                    cy.get('.description textarea').should('have.value', '0 points');
                });
                cy.get('.rubric-item:nth-child(2)').within(() => {
                    cy.get('.points').should('have.value', '1');
                    cy.get('.header').should('have.value', '1 point');
                    cy.get('.description textarea').should('have.value', '1 point');
                });
            });
        });

        it('should be possible to add items with negative points to a normal rubric row', () => {
            addNormalRow('Normal Row');
            addItem(-1, '-1 points', '-1 points');
            addItem(0, '0 points', '0 points');
            submit('success');
            loadPage(true);

            showRow('Normal Row').within(() => {
                cy.get('.rubric-item:nth-child(1) .points')
                    .should('have.value', '-1');
            });
        });

        it('should be possible to delete items from a normal rubric row', () => {
            addNormalRow('Normal Row');
            addItem(0, '0 points', '0 points');
            addItem(1, '1 point', '1 point');
            submit('success');
            loadPage(true);

            showRow('Normal Row').within(() => {
                cy.get('.rubric-item:nth-child(1) .delete-item')
                    .click();
                cy.get('.rubric-item:not(.add-button)')
                    .should('have.length', 1);
            });
            submit('success', {
                hasConfirm: true,
            });
            loadPage(true);

            showRow('Normal Row').within(() => {
                cy.get('.rubric-item:not(.add-button)')
                    .should('have.length', 1);
            });
        });

        it('should be possible to add a continuous rubric row', () => {
            addContinuousRow('Continuous Row', 'Description', 10);
            submit('success');
            loadPage(true);

            showRow('Continuous Row').within(() => {
                cy.get('.category-name')
                    .should('have.value', 'Continuous Row');
                cy.get('.category-description textarea')
                    .should('have.value', 'Description');
                cy.get('.points')
                    .should('have.value', '10');
            });
        });

        it('should be possible to delete a continuous rubric row', () => {
            addContinuousRow('Continuous Row', 'Description', 10);
            submit('success');
            loadPage(true);

            deleteRow('Continuous Row');
            getRow('Continuous Row').should('not.exist');
            submit('success', {
                hasConfirm: true,
            });
            loadPage(true);

            getRow('Continuous Row').should('not.exist');
        });

        it('should only delete continuous rows after submitting the rubric', () => {
            addContinuousRow('Continuous Row', null, 10);
            submit('success');
            loadPage(true);

            deleteRow('Continuous Row');
            getRow('Continuous Row').should('not.exist');
            loadPage(true);

            getRow('Continuous Row').should('exist');
        });

        it('should be possible to reorder rows', () => {
            cy.get('.rubric-editor').within(() => {
                cy.get('.category-item:nth(0) .drag-handle')
                    .dragTo('.category-item:nth(1) .drag-handle');

                cy.get('.category-item:nth(0)')
                    .find('.category-name')
                    .should('have.value', 'rubric row 1');

                cy.get('.category-item:nth(1)')
                    .find('.category-name')
                    .should('have.value', 'rubric row 0');
            });

            submit('success');
            loadPage(true);

            cy.get('.rubric-editor').within(() => {
                cy.get('.category-item:nth(0)')
                    .find('.category-name')
                    .should('have.value', 'rubric row 1');

                cy.get('.category-item:nth(1)')
                    .find('.category-name')
                    .should('have.value', 'rubric row 0');
            });
        });

        it('should not be possible to reorder rows by dragging anything else than the drag handle', () => {
            function checkNoDrag(selector) {
                cy.get('.rubric-editor').within(() => {
                    cy.get('.category-item:nth(0)')
                        .find(selector)
                        .dragTo('.category-item:nth(1) .drag-handle');

                    cy.get('.category-item:nth(0)')
                        .find('.category-name')
                        .should('have.value', 'rubric row 0');

                    cy.get('.category-item:nth(1)')
                        .find('.category-name')
                        .should('have.value', 'rubric row 1');
                });
            }

            cy.get('.category-item:nth(0)').click();

            checkNoDrag('.card-header');
            checkNoDrag('textarea:first');
            checkNoDrag('input:first');
        });

        it('should not be possible to submit a category without a name',  () => {
            addRow('continuous');

            submit('error', {
                popoverMsg: 'There are unnamed categories',
            });
        });

        it('should not be possible to submit a category without items', () => {
            addNormalRow('Category Without Items');

            submit('error', {
                hasConfirm: true,
                confirmMsg: [
                    'Rows without items with 0 points',
                    'Category Without Items',
                ],
                popoverMsg: [
                    'The following category has no items',
                    'Category Without Items',
                ],
            });
        });

        it('should not be possible to submit an item without a name', () => {
            addNormalRow('Item Without Name');
            addItem(0);
            addItem(1, 'Item With Name');

            submit('error', {
                popoverMsg: [
                    'The following category has items without a name',
                    'Item Without Name',
                ],
            });
        });

        it('should not be possible to submit an item without points', () => {
            addNormalRow('Item Without Points');
            addItem(null, 'Item Without Points');
            addItem(0, 'Item Without Points');

            submit('error', {
                popoverMsg: [
                    'Make sure "points" is a number for the following item',
                    'Item Without Points',
                ],
            });
        });

        it('should not be possible to submit a continuous row with non-positive points', () => {
            addContinuousRow('Continuous Row With Zero Points', null, 0);
            addContinuousRow('Continuous Row With Negative Points', null, -1);

            submit('error', {
                popoverMsg: [
                    'The following continuous category has a score less than 0 which is not supported',
                    'Continuous Row With Zero Points',
                    'Continuous Row With Negative Points',
                ],
            });
        });

        it('should show a confirmation popover when a normal category contains only a single item', () => {
            addNormalRow('Single Item');
            addItem(1, 'First Item');

            submit('success', {
                waitForState: false,
                hasConfirm: true,
                confirmMsg: [
                    'Rows with only a single item',
                    'Single Item',
                ],
            });
        });

        it('should show a confirmation popover when a normal category does not contain an item with 0 points', () => {
            addNormalRow('No 0 Item');
            addItem(1, 'First Item');
            addNormalRow('No 0 Item 2');
            addItem(-1, 'First Item');

            submit('success', {
                waitForState: false,
                hasConfirm: true,
                confirmMsg: [
                    'Rows without items with 0 points',
                    'No 0 Item',
                    'No 0 Item 2',
                ],
            });
        });

        it('should show a confirmation popover when multiple items in the same category have the same amount of points', () => {
            addNormalRow('Multiple Items With Same Points');
            addItem(1, 'First Item');
            addItem(1, 'Second Item');

            submit('success', {
                waitForState: false,
                hasConfirm: true,
                confirmMsg: [
                    'Rows with items with equal points',
                    'Multiple Items With Same Points',
                ],
            });
        });

        it('should show a confirmation popover when items were deleted from the rubric', () => {
            addNormalRow('Row With Deleted Items');
            addItem(0, 'First Item');
            addItem(1, 'Second Item');
            addItem(2, 'Third Item');
            submit('success');
            loadPage(true);

            showRow('Row With Deleted Items').within(() => {
                cy.get('.rubric-item:first .delete-item')
                    .click();
            });

            submit('success', {
                waitForState: false,
                hasConfirm: true,
                confirmMsg: [
                    'The following item was removed from the rubric',
                    'Row With Deleted Items - First Item',
                ],
            });
        });

        it('should be possible to delete a rubric', () => {
            cy.get('.submit-button.delete-rubric')
                .submit('success', {
                    hasConfirm: true,
                    confirmInModal: true,
                    waitForDefault: false,
                });
            cy.get('.rubric-editor')
                .contains('.wizard-button', 'Create new rubric')
                .should('be.visible');
        });

        it('should be possible to reset the rubric to the state on the server', () => {
            showRow('rubric row 0').within(() => {
                cy.get('.category-name').clear().type('XXX');
                cy.get('.category-description textarea').clear().type('XXX');
                cy.get('.points').clear().type('10');
            });

            showRow('rubric row 1').within(() => {
                cy.get('.category-name').clear().type('XXX');
                cy.get('.category-description textarea').clear().type('XXX');
                cy.get('.rubric-item:first-child .points').clear().type('3');
                cy.get('.rubric-item:first-child .header').clear().type('XXX');
                cy.get('.rubric-item:first-child .description textarea')
                    .clear().type('XXX');
            });

            deleteRow('rubric row 2');

            deleteRow('rubric row 3');

            addNormalRow('Normal row X');

            cy.get('.rubric-editor .category-item')
                .should('have.length', 3);

            cy.get('.rubric-editor .submit-button.reset-rubric').submit('success', {
                hasConfirm: true,
            });

            cy.get('.rubric-editor .category-item')
                .should('have.length', 4);

            showRow('rubric row 0').within(() => {
                cy.get('.category-name').should('have.value', 'rubric row 0');
                cy.get('.category-description textarea').should('have.value', 'rubric row 0');
                cy.get('.points').should('have.value', '1');
            });

            showRow('rubric row 1').within(() => {
                cy.get('.category-name').should('have.value', 'rubric row 1');
                cy.get('.category-description textarea').should('have.value', 'rubric row 1');
                cy.get('.rubric-item:first-child .points').should('have.value', '0');
                cy.get('.rubric-item:first-child .header').should('have.value', '0 points');
                cy.get('.rubric-item:first-child .description textarea')
                    .should('have.value', '0 points');
            });

            showRow('rubric row 2').within(() => {
                cy.get('.category-name').should('have.value', 'rubric row 2');
                cy.get('.category-description textarea').should('have.value', 'rubric row 2');
                cy.get('.points').should('have.value', '2');
            });

            showRow('rubric row 3').within(() => {
                cy.get('.category-name').should('have.value', 'rubric row 3');
                cy.get('.category-description textarea').should('have.value', 'rubric row 3');
                cy.get('.rubric-item:first-child .points').should('have.value', '0');
                cy.get('.rubric-item:first-child .header').should('have.value', '0 points');
                cy.get('.rubric-item:first-child .description textarea').should('have.value', '0 points');
            });
        });

        it('should indicate which rows are connected to AutoTest', () => {
            const rubricData = new Rubric([1], [1], [0, 1, 2], [0, 1, 2]);
            cy.createRubric(assignment.id, rubricData).then(rubric =>
                cy.createAutoTestFromFixture(
                    assignment.id,
                    'single_cat_two_items',
                    rubric,
                ),
            ).then(autoTest => {
                loadPage(true);

                getRow('rubric row 0').find('.card-header').within(() => {
                    cy.get('.badge')
                        .should('contain', 'AT')
                    cy.get('.btn.delete-category')
                        .should('be.disabled')
                        .find('.fa-icon.lock')
                        .should('exist');
                });

                getRow('rubric row 1').find('.card-header').within(() => {
                    cy.get('.badge')
                        .should('not.exist')
                    cy.get('.btn.delete-category')
                        .should('not.be.disabled')
                        .find('.fa-icon.lock')
                        .should('not.exist');
                });

                getRow('rubric row 2').find('.card-header').within(() => {
                    cy.get('.badge')
                        .should('contain', 'AT')
                    cy.get('.btn.delete-category')
                        .should('be.disabled')
                        .find('.fa-icon.lock')
                        .should('exist');
                });

                getRow('rubric row 3').find('.card-header').within(() => {
                    cy.get('.badge')
                        .should('not.exist')
                    cy.get('.btn.delete-category')
                        .should('not.be.disabled')
                        .find('.fa-icon.lock')
                        .should('not.exist');
                });

                cy.deleteAutoTest(autoTest.id);
            });
        });

        it('should show a message when "max points" was changed', () => {
            const maxPoints = rubricPoints.reduce((acc, row) => acc + Math.max(...row), 0);

            cy.get('.rubric-editor .advanced-collapse .collapse-toggle')
                .click();

            cy.get('.rubric-editor .max-points')
                .clear()
                .type('1');
            cy.get('.rubric-editor .max-points-warning')
                .text()
                .should('contain', `To achieve a 10 students need to score 1 out of ${maxPoints} rubric points.`);

            cy.get('.rubric-editor .max-points')
                .clear()
                .type('100');
            cy.get('.rubric-editor .max-points-warning')
                .text()
                .should('contain', `It is not possible to achieve a 10 for this rubric; a ${(maxPoints / 10).toFixed(2)} is the maximum grade that can be achieved.`);
        });

        it('should expand the advanced options when "max points" is set', () => {
            cy.get('.rubric-editor .advanced-collapse .collapse-toggle')
                .click();

            cy.get('.rubric-editor .max-points')
                .clear()
                .type('1');
            submit('success');
            loadPage(true);

            cy.get('.rubric-editor .max-points')
                .should('be.visible');
        });
    });

    context('Viewing a rubric on the submissions page', () => {
        function loadPage(reload=false) {
            if (reload) {
                cy.reload();
            } else {
                cy.visit(`/courses/${course.id}/assignments/${assignment.id}/submissions#rubric`);
            }
            cy.get('.page.submissions')
                .should('exist')
                .find('.loader')
                .should('not.be.visible');
        }

        beforeEach(() => {
            cy.deleteRubric(assignment.id, {
                failOnStatusCode: false,
            });
            loadPage();
        });

        it('should indicate when an assignment has no rubric', () => {
            cy.get('.rubric-editor')
                .should('be.visible')
                .should('contain', 'There is no rubric for this assignment.');
        });

        it('should show the non-editable rubric editor when an assignment has a rubric', () => {
            const rubric = new Rubric([0, 1, 2], [4, 8, 16]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor')
                .should('be.visible')
                .should('not.have.class', 'editable')
                .should('not.contain', 'There is no rubric for this assignment.')
                .within(() => {
                    cy.get('.category-item')
                        .should('have.length', rubric.length);
                    cy.get('.category-item:first .rubric-item')
                        .should('have.length', 3)
                    cy.get('.category-item:last .rubric-item')
                        .should('have.length', 3);
                });
        });

        it('should render the correct type of row', () => {
            const rubric = new Rubric([0, 1, 2], [4, 8, 16], [1], [2]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor .rubric-editor-row').each(($row, i) => {
                cy.wrap($row).should('have.class', rubric[i].type);
            });
        });

        it('should show the amount of points needed for the maximum grade', () => {
            function checkMaxPoints(amount) {
                cy.get('.rubric-editor .max-points')
                    .should('contain', amount);
            }

            const rubric = new Rubric([0, 1, 2], [4, 8, 16]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);
            checkMaxPoints(18);

            cy.createRubric(assignment.id, rubric, 10);
            loadPage(true);
            checkMaxPoints(10);

            cy.createRubric(assignment.id, rubric, 30);
            loadPage(true);
            checkMaxPoints(30);
        });

        it('should sort rubric items by the amount of points in normal rows', () => {
            const rubric = new Rubric([2, 1, 0], [-4, -8, 0]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor .rubric-editor-row').each($row => {
                let prev = -Infinity;
                cy.wrap($row).find('.rubric-item').each($item => {
                    cy.wrap($item).find('.points').text().then($text => {
                        const points = Number($text);
                        expect(points).to.be.greaterThan(prev);
                        prev = points;
                    });
                });
            });
        });

        it('should display the max amount of achievable points in continuous rows', () => {
            const rubric = new Rubric([1], [3]);
            cy.createRubric(assignment.id, rubric);
            loadPage(true);

            cy.get('.rubric-editor .rubric-editor-row').each(($row, i) => {
                cy.wrap($row).contains('b', `${rubric[i].items[0].points} points`)
            });
        });

        it('should indicate which rows are connected to AutoTest', () => {
            const rubricData = new Rubric([1], [1], [0, 1, 2], [0, 1, 2]);
            cy.createRubric(assignment.id, rubricData).then(rubric =>
                cy.createAutoTestFromFixture(
                    assignment.id,
                    'single_cat_two_items',
                    rubric,
                ),
            ).then(autoTest => {
                loadPage(true);

                cy.get('.category-item:nth(0)').within(() => {
                    cy.get('.badge').should('contain', 'AT');
                    cy.get('.fa-icon.lock')
                        .should('exist');
                    cy.get('.rubric-editor-row')
                        .should('have.class', 'continuous')
                });

                cy.get('.category-item:nth(1)').within(() => {
                    cy.get('.badge').should('not.exist');
                    cy.get('.fa-icon.lock')
                        .should('not.exist');
                    cy.get('.rubric-editor-row')
                        .should('have.class', 'continuous')
                });

                cy.get('.category-item:nth(2)').within(() => {
                    cy.get('.badge').should('contain', 'AT');
                    cy.get('.fa-icon.lock')
                        .should('exist');
                    cy.get('.rubric-editor-row')
                        .should('have.class', 'normal')
                });

                cy.get('.category-item:nth(3)').within(() => {
                    cy.get('.badge').should('not.exist');
                    cy.get('.fa-icon.lock')
                        .should('not.exist');
                    cy.get('.rubric-editor-row')
                        .should('have.class', 'normal')
                });

                cy.deleteAutoTest(autoTest.id);
            });
        });

        it('should wrap text instead of overflowing', () => {
            cy.fixture('test_rubrics/long_description.json').then(
                rubricData => cy.createRubric(assignment.id, rubricData),
            ).then(() => {
                loadPage(true);
                cy.get('.rubric-editor .category-item')
                    .click({ multiple: true });
                cy.get('.rubric-editor .rubric-editor-row.normal p')
                    .shouldNotOverflow();
                cy.get('.rubric-editor .rubric-editor-row.continuous p')
                    .shouldNotOverflow();
            });
        });

        it('should be visible even if the user does not have the permission to see the AutoTest', () => {
            const rubricData = new Rubric([1], [1], [0, 1, 2], [0, 1, 2]);
            cy.createRubric(assignment.id, rubricData).then(rubric =>
                cy.createAutoTestFromFixture(
                    assignment.id,
                    'no_continuous',
                    rubric,
                ),
            ).then(autoTest => {
                loadPage(true);
                cy.get('.rubric-editor')
                    .should('not.have.class', 'alert')
                    .should('be.visible');

                cy.login('student1', 'Student1');
                loadPage(false);
                cy.get('.rubric-editor')
                    .should('not.have.class', 'alert')
                    .should('be.visible')
                    .find('[id^="rubric-lock-"]:first')
                    .trigger('mouseenter');
                cy.get('.popover')
                    .should('be.visible')
                    .should('have.length', 1)
                    .should('not.contain', 'Grade calculation');

                cy.deleteAutoTest(autoTest.id);
            });
        });
    });
});
