@echo off
echo Starting PostgreSQL 16 server...
"C:\postgreSQL_16\pgsql\bin\pg_ctl.exe" -D "C:\postgreSQL_16\data" -l "C:\postgreSQL_16\data\server.log" start
"C:\postgreSQL_16\pgsql\bin\pg_isready.exe" -h localhost -p 5432 -U postgres
echo Done.
