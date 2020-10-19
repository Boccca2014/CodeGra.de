/* -*- mode: sql; sql-product: postgres; -*- */
INSERT INTO "LTIProvider" (id,
                           key)
VALUES ('lti_prov_1', 'key_1'),
       ('lti_prov_2', 'key_2');


INSERT INTO "Course" (id,
                      name,
                      created_at,
                      lti_provider_id,
                      lti_course_id)
VALUES (1, 'course 1', NOW(), 'lti_prov_1', 'lti_course_1'),
       (2, 'course 2', NOW(), 'lti_prov_1', 'lti_course_2'),
       (3, 'course 3', NOW(), 'lti_prov_2', 'lti_course_3'),
       (4, 'non lti course', NOW(), NULL, NULL);
