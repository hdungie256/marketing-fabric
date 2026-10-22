-- Traditional baseline (Story 9.3): one database, rebuilt in full by every batch, no metadata or policy layer.

CREATE TABLE wh.orders AS
SELECT customer_id, transaction_id, customer_id || '|' || transaction_id AS order_key,
       MIN(transaction_date) AS order_date, SUM(quantity * avg_price) AS gross_value
FROM wh.sales_lines
GROUP BY customer_id, transaction_id;

-- BR01: campaign overview for the whole year.
CREATE TABLE wh.br01_campaign_overview AS
SELECT a.campaign_id, c.campaign_name,
       COUNT(*) AS attributed_orders,
       COUNT(DISTINCT a.customer_id) AS attributed_buyers,
       ROUND(SUM(o.gross_value), 2) AS attributed_gross_value,
       ROUND(SUM(o.gross_value) / COUNT(*), 2) AS average_order_value
FROM wh.attribution a
JOIN wh.orders o ON o.customer_id = a.customer_id AND o.transaction_id = a.transaction_id
JOIN wh.campaigns c ON c.campaign_id = a.campaign_id
GROUP BY a.campaign_id, c.campaign_name;

-- BR10: daily split of online spend, recomputed from the two sources (not read from Spend_Recon).
CREATE TABLE wh.br10_spend_daily AS
SELECT d.spend_date, d.online_spend,
       COALESCE(SUM(s.allocated_online_spend), 0) AS allocated,
       d.online_spend - COALESCE(SUM(s.allocated_online_spend), 0) AS unallocated
FROM wh.daily_spend d
LEFT JOIN wh.campaign_spend s ON s.spend_date = d.spend_date
GROUP BY d.spend_date, d.online_spend;

-- BR10: per campaign budget, cost and efficiency ratios.
CREATE TABLE wh.br10_campaign AS
SELECT c.campaign_id, c.budget AS campaign_budget,
       COALESCE(s.allocated, 0) AS allocated,
       ROUND(b.attributed_gross_value / NULLIF(s.allocated, 0), 2) AS value_per_spend,
       ROUND(s.allocated / NULLIF(b.attributed_orders, 0), 2) AS cost_per_order
FROM wh.campaigns c
LEFT JOIN (SELECT campaign_id, SUM(allocated_online_spend) AS allocated FROM wh.campaign_spend GROUP BY campaign_id) s
  ON s.campaign_id = c.campaign_id
LEFT JOIN wh.br01_campaign_overview b ON b.campaign_id = c.campaign_id;
