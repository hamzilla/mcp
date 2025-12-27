-- MCP Client Database Schema
-- PostgreSQL 13+

-- ============================================================================
-- Core Conversation Tables
-- ============================================================================

-- Conversations table stores chat sessions
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    mode VARCHAR(50) NOT NULL,  -- 'chat' or 'agent'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Messages table stores individual messages in conversations
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- 'human', 'ai', 'tool'
    content TEXT,
    tool_calls JSONB,  -- Array of tool call objects
    tool_call_id VARCHAR(255),  -- ID for tool result messages
    model_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- ============================================================================
-- Agent Mode Tables (for future autonomous agent implementation)
-- ============================================================================

-- Scheduled tasks for periodic execution
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    schedule_type VARCHAR(50) NOT NULL,  -- 'cron', 'interval', 'continuous'
    schedule_config JSONB NOT NULL,  -- cron expression or interval config
    query_template TEXT NOT NULL,  -- The query to execute
    enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Alert rules for autonomous monitoring
CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    condition_type VARCHAR(50) NOT NULL,  -- 'threshold', 'pattern', 'anomaly'
    condition_config JSONB NOT NULL,
    action_type VARCHAR(50) NOT NULL,  -- 'webhook', 'rerun_pipeline', 'notify'
    action_config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Webhook configurations for event notifications
CREATE TABLE IF NOT EXISTS webhook_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    event_types TEXT[] NOT NULL,  -- Array of event types to trigger on
    headers JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    retry_config JSONB DEFAULT '{"max_attempts": 3, "backoff_factor": 2}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Task execution history
CREATE TABLE IF NOT EXISTS task_executions (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL,  -- 'running', 'success', 'failed'
    result JSONB,
    error TEXT,
    duration_ms INTEGER
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

-- Conversation and message indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

-- Agent mode indexes
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run ON scheduled_tasks(next_run) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_task_executions_task ON task_executions(task_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_webhook_configs_enabled ON webhook_configs(enabled) WHERE enabled = TRUE;

-- ============================================================================
-- Trigger for updating updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scheduled_tasks_updated_at BEFORE UPDATE ON scheduled_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_alert_rules_updated_at BEFORE UPDATE ON alert_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_webhook_configs_updated_at BEFORE UPDATE ON webhook_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Initial Data / Examples (commented out)
-- ============================================================================

-- Example: Create a test conversation
-- INSERT INTO conversations (user_id, mode) VALUES ('test-user', 'chat');

-- Example: Create a scheduled task
-- INSERT INTO scheduled_tasks (name, description, schedule_type, schedule_config, query_template)
-- VALUES (
--     'Check failed pipelines',
--     'Check for failed pipelines every 5 minutes',
--     'interval',
--     '{"interval_seconds": 300}',
--     'Which pipelines failed in the last 5 minutes?'
-- );
