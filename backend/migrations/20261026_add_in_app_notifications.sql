CREATE TABLE IF NOT EXISTS in_app_notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    journey_id UUID NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    notification_type VARCHAR(40) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    read_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_in_app_notifications_user_id
    ON in_app_notifications (user_id);
CREATE INDEX IF NOT EXISTS ix_in_app_notifications_journey_id
    ON in_app_notifications (journey_id);
CREATE INDEX IF NOT EXISTS ix_in_app_notifications_user_unread
    ON in_app_notifications (user_id, created_at DESC)
    WHERE read_at IS NULL;
