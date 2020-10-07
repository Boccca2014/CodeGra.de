INSERT INTO "Course" (id, name, created_at)
VALUES (1, 'course 1', NOW());

INSERT INTO "Assignment" (id, name, state, "Course_id", created_at, visibility_state, is_lti)
VALUES (1, 'assig 1', 'open', 1, NOW(), 'visible', false),
       (2, 'assig 2', 'open', 1, NOW(), 'visible', false);

INSERT INTO "RubricRow" ("Assignment_id",
                         created_at,
                         header,
                         rubric_row_type)
VALUES (1, '2020-01-01T00:00:00', 'row 0', 'normal'),
       (1, '2020-01-02T00:00:00', 'row 1', 'normal'),
       (1, '2020-01-03T00:00:00', 'row 2', 'normal'),
       (2, '2020-01-02T00:00:00', 'row 0', 'continuous'),
       (2, '2020-01-05T00:00:00', 'row 1', 'continuous'),
       (2, '2020-01-06T00:00:00', 'row 2', 'continuous');
