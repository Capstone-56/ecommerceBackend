### Populating Database with example data
initial_data.json provides a json object to supply to the database as fake
data. To use it and populate the product table with two fake products, run the
following command:

-> python manage.py loaddata base/fixtures/initial_data.json

or run -> python manage.py loaddata base/fixtures/additional_data.json (temp fixtures for testing the new product and category schema)

### To recalculate the MPTT tree run the following (after loading fixtures):
python manage.py shell -c "from base.models import CategoryModel; CategoryModel.objects.rebuild()"