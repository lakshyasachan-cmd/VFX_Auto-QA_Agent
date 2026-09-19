@echo off
echo Stopping PostgreSQL 16 server...
"C:\postgreSQL_16\pgsql\bin\pg_ctl.exe" -D "C:\postgreSQL_16\data" -m fast stop
echo Done.
