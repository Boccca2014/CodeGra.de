INSERT INTO "LTIProvider" (id,
                           key)
VALUES ('lti_prov_1', 'key_1'),
       ('lti_prov_2', 'key_2');


INSERT INTO "Course" (id,
                      created_at,
                      name)
VALUES (1, NOW(), 'course 1'),
       (2, NOW(), 'course 2'),
       (3, NOW(), 'course 3'),
       (4, NOW(), 'non lti course');


INSERT INTO course_lti_provider (id, created_at, updated_at, lti_course_id, deployment_id, lti_provider_id, course_id)
VALUES (uuid_generate_v4(), NOW(), NOW(), 'lti_course_1', 'lti_course_1', 'lti_prov_1', 1),
       (uuid_generate_v4(), NOW(), NOW(), 'lti_course_2', 'lti_course_2', 'lti_prov_1', 2),
       (uuid_generate_v4(), NOW(), NOW(), 'lti_course_3', 'lti_course_3', 'lti_prov_2', 3);
