# eCommerce Server
This repo is responsible for developing the server for the eCommerce Website

## Local Database Setup
### Install Postgres server and PgAdmin4
#### For Windows
Download PostgreSQL (v17.4): https://www.enterprisedb.com/downloads/postgres-postgresql-downloads

Download PgAdmin4 (v9.2): https://www.pgadmin.org/download/pgadmin-4-windows/

#### For Mac
Download Postgres.app: https://postgresapp.com/downloads.html!

`Postgres.app with PostgreSQL 17 (Universal)`

### Creating local DB schema
Go to Tools -> Query Tool
```sql
CREATE DATABASE ecommerce_db;
```

Second query
```sql
CREATE USER ecommerce_admin WITH LOGIN SUPERUSER CREATEDB CREATEROLE INHERIT NOREPLICATION BYPASSRLS PASSWORD "capstone56";
GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_admin;
```

## Local Server Setup
__Step 1:__

python -m venv .venv

__Step2:__

Windows: .venv\Scripts\activate

MacOS: source .venv/bin/activate

__Step 3:__

In an IDE of your choice (PyCharm Community, Visual Studio, Intellij, etc.), there should be a run config called runserver, choose that one and run.

## Verify server's working with DB
Go to PgAdmin, checks if this exist under the correct database![image](https://github.com/user-attachments/assets/9acc25f4-f9e5-419f-8a66-4bad7cb920e4)

Right click on the table -> View/Edit data -> All Rows

Add one or more entry to the table![image](https://github.com/user-attachments/assets/62938376-56f9-402a-b195-70c4bf36cb3f)

Save data changes -> enter into the browser http://localhost:8000/api/user to see if the API returned the correct data from your local DB




