CREATE TABLE IF NOT EXISTS companies (
    company_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS social_networks (
    social_network_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(company_id),
    social_network_id BIGINT NOT NULL REFERENCES social_networks(social_network_id),
    account_name VARCHAR(200) NOT NULL,
    account_url TEXT NOT NULL,
    UNIQUE (social_network_id, account_url)
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS posts (
    post_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(account_id),
    topic_id BIGINT REFERENCES topics(topic_id),
    published_at TIMESTAMPTZ NOT NULL,
    post_text TEXT,
    post_url TEXT,
    UNIQUE (account_id, post_url)
);

CREATE TABLE IF NOT EXISTS activity_metrics (
    metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    likes BIGINT NOT NULL DEFAULT 0 CHECK (likes >= 0),
    comments BIGINT NOT NULL DEFAULT 0 CHECK (comments >= 0),
    shares BIGINT NOT NULL DEFAULT 0 CHECK (shares >= 0),
    views BIGINT NOT NULL DEFAULT 0 CHECK (views >= 0),
    reach BIGINT CHECK (reach >= 0),
    impressions BIGINT CHECK (impressions >= 0),
    saves BIGINT CHECK (saves >= 0),
    clicks BIGINT CHECK (clicks >= 0),
    reactions BIGINT CHECK (reactions >= 0),
    UNIQUE (post_id, metric_date)
);


CREATE INDEX IF NOT EXISTS idx_accounts_company ON accounts(company_id);
CREATE INDEX IF NOT EXISTS idx_accounts_network ON accounts(social_network_id);
CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts(topic_id);