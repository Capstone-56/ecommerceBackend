### Populating Database with example data
initial_data.json provides a json object to supply to the database as fake
data. To use it and populate the product table with two fake products, run the
following command:

-> python manage.py loaddata base/fixtures/final_client_product_data.json
