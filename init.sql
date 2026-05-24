-- init.sql
-- This script runs when the PostgreSQL container is first created

-- Create Credentials table
CREATE TABLE IF NOT EXISTS Credentials (
    ID SERIAL PRIMARY KEY,
    NEW_CREDENTIAL_PAIR TEXT NULL,
    GROK_API_KEY TEXT NULL,
    GROK_MANAGEMENT_KEY TEXT NULL
);

-- Create Topics table
CREATE TABLE IF NOT EXISTS Topics (
    ID SERIAL PRIMARY KEY,
    TOPIC TEXT NOT NULL,
    COLLECTION_NAME TEXT NOT NULL,
    COLLECTION_ID TEXT NULL,
    KNOWLEDGE_BASE_FILES TEXT NULL
);

-- Create Conversations table
CREATE TABLE IF NOT EXISTS Conversations (
    id SERIAL PRIMARY KEY,
    Topic_Name TEXT,
    DateTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Content TEXT,
    Is_User BOOLEAN,
    Is_Bot BOOLEAN
);

-- Create Current Topic table (stores the active/current topic)
CREATE TABLE IF NOT EXISTS CURRENT_TOPIC (
    ID SERIAL PRIMARY KEY,
    TOPIC_NAME TEXT NOT NULL,
    CONSTRAINT single_active_topic CHECK (ID = 1) -- Ensures only one record exists
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_conversations_topic_name ON Conversations(Topic_Name);
CREATE INDEX IF NOT EXISTS idx_conversations_datetime ON Conversations(DateTime);
CREATE INDEX IF NOT EXISTS idx_topics_topic ON Topics(TOPIC);
CREATE INDEX IF NOT EXISTS idx_current_topic_name ON CURRENT_TOPIC(TOPIC_NAME);

-- Verify table creation
SELECT 'Tables created successfully!' AS Status;