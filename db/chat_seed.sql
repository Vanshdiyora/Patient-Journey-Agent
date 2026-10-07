-- Synthetic demonstration history only; no live assistant calls or actions.
INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
SELECT md5('demo-chat-session:' || id)::uuid, id,
       'Synthetic demo: care journey overview', NOW() - interval '1 hour', NOW()
FROM users WHERE is_active;

INSERT INTO chat_messages (id, session_id, role, content, meta, created_at)
SELECT md5('demo-chat-question:' || id)::uuid, id, 'user',
       'How can I view my care journeys?', '{"synthetic_demo":true}'::jsonb,
       created_at
FROM chat_sessions;

INSERT INTO chat_messages (id, session_id, role, content, meta, created_at)
SELECT md5('demo-chat-answer:' || id)::uuid, id, 'assistant',
       'Open the journeys page to review the care plan, step status, and due dates. This is a synthetic demonstration conversation.',
       '{"synthetic_demo":true}'::jsonb, created_at + interval '1 second'
FROM chat_sessions;

INSERT INTO chat_audit_log (
    id, user_id, conversation_id, message_id, tool_name, event,
    parameters, permission_result, detail, created_at
)
SELECT md5('demo-chat-audit:' || id)::uuid, user_id, id,
       md5('demo-chat-answer:' || id)::uuid, 'seed_database', 'demo_seeded',
       '{"synthetic_demo":true}'::jsonb, 'not_applicable',
       'Synthetic history created by the seed; no tool or clinical action executed.',
       created_at + interval '1 second'
FROM chat_sessions;
