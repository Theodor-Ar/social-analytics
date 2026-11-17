WITH latest_metrics AS (
    SELECT post_id, likes, comments, shares, views,
        ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY metric_date DESC) AS rn
    FROM activity_metrics
)
SELECT c.name AS company, COUNT(DISTINCT p.post_id) AS posts_count,
    COALESCE(SUM(lm.likes), 0) AS total_likes, COALESCE(SUM(lm.comments), 0) AS total_comments,
    COALESCE(SUM(lm.shares), 0) AS total_shares, COALESCE(SUM(lm.views), 0) AS total_views
FROM companies c
JOIN accounts a ON a.company_id = c.company_id
JOIN posts p ON p.account_id = a.account_id
LEFT JOIN latest_metrics lm ON lm.post_id = p.post_id AND lm.rn = 1
GROUP BY c.company_id, c.name
ORDER BY total_likes DESC;


WITH latest_metrics AS (
    SELECT post_id, likes, comments, shares, views,
        ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY metric_date DESC) AS rn
    FROM activity_metrics
)
SELECT t.name AS topic, COUNT(p.post_id) AS posts_count,
    SUM(lm.likes) AS total_likes, SUM(lm.comments) AS total_comments,
    SUM(lm.shares) AS total_shares, SUM(lm.views) AS total_views,
    ROUND(AVG(lm.likes + lm.comments + lm.shares), 2) AS avg_engagement
FROM topics t
JOIN posts p ON p.topic_id = t.topic_id
JOIN latest_metrics lm ON lm.post_id = p.post_id AND lm.rn = 1
GROUP BY t.topic_id, t.name
ORDER BY avg_engagement DESC;


WITH latest_metrics AS (
    SELECT post_id, likes, comments, shares, views,
        ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY metric_date DESC) AS rn
    FROM activity_metrics
)
SELECT DATE_TRUNC('month', p.published_at)::DATE AS month,
    COUNT(DISTINCT p.post_id) AS posts_count, SUM(lm.likes) AS likes,
    SUM(lm.comments) AS comments, SUM(lm.shares) AS shares, SUM(lm.views) AS views
FROM posts p
JOIN latest_metrics lm ON lm.post_id = p.post_id AND lm.rn = 1
GROUP BY DATE_TRUNC('month', p.published_at)
ORDER BY month;


WITH latest_metrics AS (
    SELECT post_id, likes, comments, shares, views,
        ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY metric_date DESC) AS rn
    FROM activity_metrics
)
SELECT c.name AS company, COALESCE(t.name, 'Без темы') AS topic,
    LEFT(p.post_text, 100) AS short_text, p.published_at,
    lm.likes, lm.comments, lm.shares, lm.views,
    (lm.likes + lm.comments + lm.shares) AS engagement
FROM posts p
JOIN accounts a ON a.account_id = p.account_id
JOIN companies c ON c.company_id = a.company_id
LEFT JOIN topics t ON t.topic_id = p.topic_id
JOIN latest_metrics lm ON lm.post_id = p.post_id AND lm.rn = 1
ORDER BY engagement DESC LIMIT 10;


WITH latest_metrics AS (
    SELECT post_id, likes, comments, shares, views, saves,
        ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY metric_date DESC) AS rn
    FROM activity_metrics
)
SELECT p.post_id, c.name AS company, t.name AS topic,
    lm.views, lm.likes, lm.comments, lm.shares,
    ROUND((lm.likes + lm.comments + lm.shares + COALESCE(lm.saves, 0)) * 100.0 / NULLIF(lm.views, 0), 2) AS engagement_rate
FROM posts p
JOIN accounts a ON a.account_id = p.account_id
JOIN companies c ON c.company_id = a.company_id
LEFT JOIN topics t ON t.topic_id = p.topic_id
JOIN latest_metrics lm ON lm.post_id = p.post_id AND lm.rn = 1
WHERE lm.views > 0 ORDER BY engagement_rate DESC;


WITH latest_metrics AS (
    SELECT post_id, likes, comments, shares, views,
        ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY metric_date DESC) AS rn
    FROM activity_metrics
)
SELECT c.name AS company, sn.name AS social_network,
    COUNT(DISTINCT p.post_id) AS posts_count, SUM(lm.likes) AS likes,
    SUM(lm.comments) AS comments, SUM(lm.shares) AS shares, SUM(lm.views) AS views
FROM companies c
JOIN accounts a ON a.company_id = c.company_id
JOIN social_networks sn ON sn.social_network_id = a.social_network_id
JOIN posts p ON p.account_id = a.account_id
JOIN latest_metrics lm ON lm.post_id = p.post_id AND lm.rn = 1
GROUP BY c.name, sn.name ORDER BY c.name, views DESC;


SELECT post_id, metric_date, views,
    views - LAG(views, 1, 0) OVER (PARTITION BY post_id ORDER BY metric_date) AS views_delta,
    likes, likes - LAG(likes, 1, 0) OVER (PARTITION BY post_id ORDER BY metric_date) AS likes_delta
FROM activity_metrics ORDER BY post_id, metric_date;