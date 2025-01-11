ALTER USER postgres PASSWORD 'root@123';
UPDATE pg_database SET datcollate = 'en_US.utf8', datctype = 'en_US.utf8' WHERE datname = 'postgres';
UPDATE pg_database SET datcollate = 'en_US.utf8', datctype = 'en_US.utf8' WHERE datname = 'template0';
UPDATE pg_database SET datcollate = 'en_US.utf8', datctype = 'en_US.utf8' WHERE datname = 'template1';


CREATE USER stocka WITH PASSWORD 'stocka@123';


CREATE DATABASE testdb;
GRANT ALL PRIVILEGES ON DATABASE testdb TO stocka;
\c testdb;
GRANT ALL on schema public to stocka;
