INSERT INTO "LTIProvider" (id,
                           created_at,
                           key,
                           lti_provider_version,
                           finalized,
                           intended_use)
VALUES (uuid_generate_v4(), NOW(), 'lms1', 'lti1.1', true, 'existing lms'),
       (uuid_generate_v4(), NOW(), 'lms1p1_removed', 'lti1.1', true, 'LTI1.1'),
       (uuid_generate_v4(), NOW(), 'lms1p3', 'lti1.3', true, 'LTI1.3');
