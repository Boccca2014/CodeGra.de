context('Rubric Viewer', () => {
    let unique = Math.floor(Math.random() * 100000);
    let course;
    let assignment;
    let submission;

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

    function getRubricItem(rowIdx, itemIdx) {
        if (itemIdx == null) {
            // Get the nth item anywhere in the rubric.
            return cy.get(`.rubric-viewer .rubric-item:nth(${rowIdx})`);
        } else {
            // Get the nth item in the `rowIdx`th row.
            return cy.get(`.rubric-viewer .rubric-viewer-row:nth(${rowIdx}) .rubric-item:nth(${itemIdx})`);
        }
    }

    function selectRubricItem(rowIdx, itemIdx) {
        return getRubricItem(rowIdx, itemIdx)
            .should('not.have.class', 'selected')
            .click({ force: true });
    }

    function deselectRubricItem(rowIdx, itemIdx) {
        return getRubricItem(rowIdx, itemIdx)
            .should('have.class', 'selected')
            .click({ force: true });
    }

    function deselectContinuous(rowIdx) {
        return cy.get(`.rubric-viewer .rubric-viewer-row:nth(${rowIdx}) .percentage`)
            .clear({ force: true });
    }

    function selectContinuous(rowIdx, perc) {
        return deselectContinuous(rowIdx)
            .type(perc.toString(), { force: true });
    }

    function giveMaxGrade() {
        cy.get('.rubric-viewer .rubric-viewer-row.normal').each($row => {
            cy.wrap($row).find('.rubric-item:last').click({ force: true });
        });
        cy.get('.rubric-viewer .rubric-viewer-row.continuous input.percentage')
            .each($input => cy.wrap($input).type('100', { force: true }));
    }

    function gradeInput() {
        return cy.get('.grade-viewer input[name="grade-input"]');
    }

    function giveManualGrade(grade) {
        return gradeInput().clear().type(grade.toString());
    }

    function submitGrade(...args) {
        return cy.get('.grade-viewer .submit-grade-btn')
            .submit(...args);
    }

    function checkGrade(expected) {
        return gradeInput().should('have.value', expected);
    }

    function deleteGrade() {
        cy.get('.grade-viewer .delete-button-group')
            .trigger('mouseenter');

        cy.get('.popover').should('be.visible');

        return cy.get('.grade-viewer .delete-button')
            .submit('success', { hasConfirm: true });
    }

    before(() => {
        cy.visit('/');
        cy.createCourse(
            `Rubric Viewer Course ${unique}`,
            [{ name: 'student1', role: 'Student' }],
        ).then(res => {
            course = res;
            cy.createAssignment(
                course.id,
                `Rubric Viewer Assignment ${unique}`,
                { deadline: 'tomorrow', state: 'open' },
            ).then(res => {
                assignment = res;
                cy.createSubmission(assignment.id, 'test_submissions/hello.py', {
                    author: 'student1',
                }).then(res => {
                    submission = res;
                });
            });
        });
    });

    beforeEach(() => {
        cy.login('admin', 'admin');
        cy.visit(`/courses/${course.id}/assignments/${assignment.id}/submissions/${submission.id}`);
        cy.url().should('contain', '/files/');
    });

    context('Assignment without rubric', () => {
        it('should not be visible', () => {
            cy.get('.rubric-viewer')
                .should('not.exist');
            cy.get('.grade-viewer .btn.rubric-toggle')
                .should('not.exist');
        });
    });

    context('Assignment with a Rubric', () => {
        const rubricPoints = [[1, 2, 3], [4, 5, 6], [1], [2]];
        const rubricRows = new Rubric(...rubricPoints);
        let rubric;

        function setMaxPoints(maxPoints) {
            cy.createRubric(assignment.id, rubricRows, maxPoints);
            cy.reload();
            cy.get('.rubric-viewer').should('be.visible');
        }

        after(() => {
            cy.deleteRubric(assignment.id);
        });

        beforeEach(() => {
            cy.createRubric(assignment.id, rubricRows).then(res => {
                rubric = res;
            });
            cy.patchSubmission(submission.id, { grade: null });
            cy.clearRubricResult(submission.id);
            cy.reload();
            cy.get('.rubric-viewer').should('be.visible');
        });

        it('should be visible when visiting a submission', () => {
            cy.get('.rubric-viewer')
                .should('be.visible');
        });

        it('should render the correct type of row', () => {
            cy.get('.rubric-viewer .rubric-viewer-row').each(($row, i) => {
                cy.wrap($row).should('have.class', rubricRows[i].type);
            });
        });

        it('should update the grade in the grade viewer when an item is selected', () => {
            checkGrade('');
            selectRubricItem(0);
            checkGrade('0.83');
            deselectRubricItem(0);
            checkGrade('');
            selectContinuous(2, '100');
            checkGrade('0.83');
            deselectContinuous(2);
            checkGrade('');
        });

        it('should update the grade in the grade viewer when the grade was overridden', () => {
            checkGrade('');
            selectRubricItem(0);
            checkGrade('0.83');
            giveManualGrade(5);
            submitGrade('success');
            selectRubricItem(1);
            checkGrade('1.67');
        });

        it('should reset to the overridden grade if the rubric was changed', () => {
            checkGrade('');
            selectRubricItem(0);
            checkGrade('0.83');
            giveManualGrade(5);
            submitGrade('success');
            selectRubricItem(1);
            deleteGrade();
            checkGrade('5.00');
        });

        it('should show a warning when the rubric grade has not been submitted yet', () => {
            selectRubricItem(0);
            cy.get('.grade-viewer .rubric-save-warning')
                .should('be.visible');
        });

        it('should give a 10 if the max item is selected in each row', () => {
            giveMaxGrade();
            checkGrade('10.00');
        });

        it('should display the correct max points in the grade viewer', () => {
            function checkMaxPoints(maxPoints) {
                cy.get('.grade-viewer .rubric-score')
                    .should('contain', `/ ${maxPoints}`);
            }

            checkMaxPoints(12);
            setMaxPoints(1);
            checkMaxPoints(1);
            setMaxPoints(10);
            checkMaxPoints(10);
            setMaxPoints(10.12345);
            checkMaxPoints(10.12);
            setMaxPoints(null);
            checkMaxPoints(12);
        });

        it('should take the rubric\'s max points into account calculating the rubric grade', () => {
            setMaxPoints(1);
            selectRubricItem(0);
            checkGrade('10.00');

            setMaxPoints(24);
            giveMaxGrade();
            checkGrade('5.00');
        });

        it('should show the selected amount of points in the category title', () => {
            cy.get('.rubric-viewer .nav-tabs .nav-item:nth(0)')
                .should('not.contain', '1⁄3');
            selectRubricItem(0);
            cy.get('.rubric-viewer .nav-tabs .nav-item:nth(0)')
                .should('contain', '1⁄3');

            cy.get('.rubric-viewer .nav-tabs .nav-item:nth(2)')
                .should('not.contain', '1⁄1');
            selectContinuous(2, '100');
            cy.get('.rubric-viewer .nav-tabs .nav-item:nth(2)')
                .should('contain', '1⁄1');
            selectContinuous(2, '50');
            cy.get('.rubric-viewer .nav-tabs .nav-item:nth(2)')
                .should('contain', '0.5⁄1');
            selectContinuous(2, '0');
            cy.get('.rubric-viewer .nav-tabs .nav-item:nth(2)')
                .should('contain', '0⁄1');
        });

        it('should be possible to deselect an item', () => {
            selectRubricItem(0);
            checkGrade('0.83');
            deselectRubricItem(0);
            checkGrade('');
            selectContinuous(2, '100');
            checkGrade('0.83');
            deselectContinuous(2);
            checkGrade('');
        });

        it('should be possible to clear all selected items', () => {
            giveMaxGrade();
            submitGrade('success');

            // Check that there is an item selected in each normal row.
            cy.get('.rubric-viewer .rubric-item.selected')
                .should('have.length', 2);
            // Check that the progress meter in each continuous is visible.
            cy.get('.rubric-viewer .rubric-viewer-row.continuous .progress-meter')
                .each($progress => {
                    const style = getComputedStyle($progress.get(0));
                    cy.wrap(style.opacity).should('eq', '1');
                });

            deleteGrade();

            // Check that there is no item selected in each normal row.
            cy.get('.rubric-viewer .rubric-item.selected')
                .should('have.length', 0);
            // Check that the progress meter in each continuous is invisible.
            cy.get('.rubric-viewer .rubric-viewer-row.continuous .progress-meter')
                .each($progress => {
                    const style = getComputedStyle($progress.get(0));
                    cy.wrap(style.opacity).should('eq', '0');
                });
        });

        it('should be possible to reset to the rubric grade when the rubric grade was overridden', () => {
            giveMaxGrade();
            giveManualGrade('9');
            submitGrade('success');
            deleteGrade();

            // Check that the max item is selected in each normal row.
            cy.get('.rubric-viewer .rubric-viewer-row.normal')
                .each($row => {
                    cy.wrap($row)
                        .find('.rubric-item:last')
                        .should('have.class', 'selected');
                });
            // Check that the progress meter in each continuous row is 100%.
            cy.get('.rubric-viewer .rubric-viewer-row.continuous .progress-meter')
                .each($progress => {
                    const style = $progress.get(0).style;
                    cy.wrap(style.width).should('eq', '100%');
                });
            checkGrade('10.00');
        });

        it('should wrap text instead of overflowing', () => {
            cy.fixture('test_rubrics/long_description.json').then(
                rubricData => cy.createRubric(assignment.id, rubricData),
            ).then(() => {
                cy.reload();
                cy.get('.rubric-viewer').should('be.visible');

                cy.get('.rubric-viewer .rubric-viewer-row.normal:visible p')
                    .shouldNotOverflow();
                cy.get('.rubric-viewer .nav-tabs .nav-item:nth(1)')
                    .click();
                cy.get('.rubric-viewer .rubric-viewer-row.continuous:visible p')
                    .shouldNotOverflow();
            });
        });
    });

    context('Assignment with Rubric and AutoTest', () => {
        const rubricPoints = [[1, 2, 3], [4, 5, 6], [1], [2]];
        const rubricRows = new Rubric(...rubricPoints);
        let rubric;
        let autoTest;

        before(() => {
            cy.createRubric(assignment.id, rubricRows).then(res => {
                rubric = res;
                return cy.createAutoTestFromFixture(
                    assignment.id,
                    'single_cat_two_items',
                    rubric,
                );
            }).then(res => {
                autoTest = res;
            });
        });

        after(() => {
            cy.deleteAutoTest(autoTest.id).then(() => {
                cy.deleteRubric(assignment.id);
            });
        });

        it('should indicate which categories have an associated AutoTest category', () => {
            cy.get('.rubric-viewer')
                .should('be.visible')
                .within(() => {
                    cy.get('.nav-tabs .nav-item:nth(0)')
                        .click()
                        .contains('.badge', 'AT')
                        .should('be.visible');
                    cy.get('.rubric-viewer-row:visible')
                        .find('.fa-icon[id^="rubric-lock-"]')
                        .should('be.visible');

                    cy.get('.nav-tabs .nav-item:nth(1)')
                        .click()
                        .contains('.badge', 'AT')
                        .should('not.exist');
                    cy.get('.rubric-viewer-row:visible')
                        .find('.fa-icon[id^="rubric-lock-"]')
                        .should('not.exist');

                    cy.get('.nav-tabs .nav-item:nth(2)')
                        .click()
                        .contains('.badge', 'AT')
                        .should('be.visible');
                    cy.get('.rubric-viewer-row:visible')
                        .find('.fa-icon[id^="rubric-lock-"]')
                        .should('be.visible');

                    cy.get('.nav-tabs .nav-item:nth(3)')
                        .click()
                        .contains('.badge', 'AT')
                        .should('not.exist');
                    cy.get('.rubric-viewer-row:visible')
                        .find('.fa-icon[id^="rubric-lock-"]')
                        .should('not.exist');

                });
        });

        it('should not be possible to select item in AutoTest categories', () => {
            cy.get('.rubric-viewer .rubric-item:nth(0)')
                .click();
            cy.get('.rubric-viewer .rubric-item:nth(0)')
                .should('not.have.class', 'selected');
            cy.get('.rubric-viewer input.percentage:nth(0)')
                .should('be.disabled');
        });
    });
});
