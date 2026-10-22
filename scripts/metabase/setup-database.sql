-- The database users for Metabase. Run once on the server, after the
-- analytics views exist (migration accounts 0023_analytics_views):
--
--   sudo -u postgres psql -d campus_ride \
--     -v reader_password='…' -v app_password='…' -f scripts/metabase/setup-database.sql
--
-- metabase_reader: what Metabase asks questions as. It can only read the
--   analytics views, not the app's tables.
-- metabase_app: owns metabase_app, Metabase's own database (its users,
--   questions and dashboards).
\set ON_ERROR_STOP on

CREATE ROLE metabase_reader LOGIN PASSWORD :'reader_password';
GRANT CONNECT ON DATABASE campus_ride TO metabase_reader;
GRANT USAGE ON SCHEMA analytics TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO metabase_reader;
-- Views added by later migrations (run as postgres) can be read too
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA analytics GRANT SELECT ON TABLES TO metabase_reader;
-- A slow question cannot hold up the app
ALTER ROLE metabase_reader SET statement_timeout = '30s';

CREATE ROLE metabase_app LOGIN PASSWORD :'app_password';
CREATE DATABASE metabase_app OWNER metabase_app;
