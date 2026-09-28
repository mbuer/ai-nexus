-- Separate schema ownership from the Birdynator runtime login.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'birdynator_owner') THEN
        CREATE ROLE birdynator_owner NOLOGIN;
    END IF;
END
$$;

ALTER DATABASE birdynator OWNER TO birdynator_owner;
REASSIGN OWNED BY birdynator TO birdynator_owner;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM birdynator;
GRANT CONNECT ON DATABASE birdynator TO birdynator;
GRANT USAGE ON SCHEMA public TO birdynator;
