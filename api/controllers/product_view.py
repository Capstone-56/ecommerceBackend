import json
import os
import boto3
from django.utils.text import slugify
from django.shortcuts import get_object_or_404
from django.db.models import Min, Max, Count, Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from base.abstractModels import PagedList
from base.models import ProductModel, VariantModel, CategoryModel
from api.serializers import ProductModelSerializer, CategoryModelSerializer
from ecommerceBackend import settings

class ProductViewSet(viewsets.ViewSet):
    """
    A ViewSet for the ProductModel, enabling CRUD operations to be used on
    product data.
    """

    def list(self, request):
        """
        GET /api/product/
        Optional query params:
        - page (int)
        - pageSize (int)
        - priceMin (float) e.g. ?priceMin=10
        - priceMax (float) e.g. ?priceMax=100
        - sort (string) e.g. ?sort=priceAsc, ?sort=priceDesc
        - colour (string) e.g. ?colour=red
        - categories (comma‑separated strings) e.g. ?categories=cat1, cat2
        - search (string) e.g. ?search=pants
        - Location (string) e.g. ?location=au
        
        If categories is provided, returns products linked to *all* of those categories.
        """
        querySet = ProductModel.objects.all()

        categoriesParam = request.query_params.get("categories")
        if categoriesParam:
            categoryIds = [c.strip() for c in categoriesParam.split(",") if c.strip()]
            # Find all categories matching those internalNames (with descendants)
            from base.models import CategoryModel
            all_category_ids = set()
            for internal_name in categoryIds:
                try:
                    cat = CategoryModel.objects.get(internalName=internal_name)
                    descendants = cat.get_descendants(include_self=True)
                    all_category_ids.update(descendants.values_list("internalName", flat=True))
                except CategoryModel.DoesNotExist:
                    pass  # Ignore invalid categories, or handle as needed
            if all_category_ids:
                querySet = querySet.filter(category__in=all_category_ids)
            else:
                querySet = querySet.none()
        
        # Get user's location for price filtering
        location_param = request.query_params.get("location", "au").upper()
        
        # Find the min and max price from ProductLocation for the user's location
        # Note: Since price is now in ProductLocation, we annotate differently
        querySet = querySet.annotate(
            minPrice=Min("locations__price", filter=Q(locations__location__country_code=location_param)),
            maxPrice=Max("locations__price", filter=Q(locations__location__country_code=location_param))
        )

        # Filter by min_price and max_price from ProductLocation
        priceMin = request.query_params.get("priceMin")
        priceMax = request.query_params.get("priceMax")
        if priceMin:
            querySet = querySet.filter(
                locations__price__gte=priceMin,
                locations__location__country_code=location_param
            )
        if priceMax:
            querySet = querySet.filter(
                locations__price__lte=priceMax,
                locations__location__country_code=location_param
            )
        querySet = querySet.distinct()
        
        # sort by highest or lowest price
        sort = request.query_params.get("sort")
        if sort == "priceAsc":
            querySet = querySet.order_by("minPrice")
        elif sort == "priceDesc":
            querySet = querySet.order_by("-maxPrice")
        elif sort == "featured":
            querySet = querySet.order_by("-featured", "name")

        colour = request.query_params.get("colour") or request.query_params.get("color")
        if colour:
            # Find all Variant IDs for this colour
            variant_ids = VariantModel.objects.filter(
                value__iexact=colour,
                variationType__name__iexact="colour"
            ).values_list("id", flat=True)
            # Filter products linked to these variants via ProductConfig
            querySet = querySet.filter(items__productconfigmodel__variant__in=variant_ids).distinct()

        # Search name and description from ProductLocation (supports translations)
        searchQuery = request.query_params.get("search")
        if searchQuery:
            # Search in ProductLocation names/descriptions for the user's location
            # Create search vector for full-text search on ProductLocation
            search_vector = SearchVector('locations__name', weight='A') + SearchVector('locations__description', weight='B')
            search_query = SearchQuery(searchQuery, config='english')
            
            # rank products based on weight of search terms
            full_text_results = querySet.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(
                search=search_query,
                locations__location__country_code=location_param
            ).filter(rank__gte=0.1)
            
            # fuzzy matching on ProductLocation
            trigram_results = querySet.annotate(
                similarity=TrigramSimilarity('locations__name', searchQuery) + 
                          TrigramSimilarity('locations__description', searchQuery)
            ).filter(
                similarity__gt=0.1,
                locations__location__country_code=location_param
            )
            
            # Combine results, prioritizing full-text search
            if full_text_results.exists():
                querySet = full_text_results.order_by('-rank')
            elif trigram_results.exists():
                querySet = trigram_results.order_by('-similarity')
            else:
                # Fallback to basic icontains search on ProductLocation
                querySet = querySet.filter(
                    Q(locations__name__icontains=searchQuery) | 
                    Q(locations__description__icontains=searchQuery),
                    locations__location__country_code=location_param
                )

        # Filter by user's country if provided (ensure products have location data)
        location = request.query_params.get("location")
        if location:
            querySet = querySet.filter(locations__location__country_code__iexact=location)

        paginator = PagedList()
        pagedQuerySet = paginator.paginate_queryset(querySet, request)

        # Pass country_code to serializer for location-specific pricing/translation
        serializer = ProductModelSerializer(
            pagedQuerySet, 
            many=True, 
            context={"sort": sort, "country_code": location_param, "request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], url_path="cat")
    def listProductsByCategory(self, request, pk=None):
        """
        Retrieve all products under a category and its subcategories,
        and generate a breadcrumb trail of parent categories.
        this should replace the current GET /api/product endpoint in the near future
        unless admins might need to list the full table of products
        GET /api/product/{internalName}/cat?location=au
        Optional query params:
        - location (string) e.g. ?location=AU for location-specific pricing and currency
        """
        category = get_object_or_404(CategoryModel, internalName=pk)

        # Get all descendant categories including the current one
        categories = category.get_descendants(include_self=True)

        # Retrieve products in these categories
        products = ProductModel.objects.filter(category__in=categories)
        
        # Get location from query parameters for location-specific pricing and currency
        location_param = request.query_params.get("location", "au").upper()

        serializer = ProductModelSerializer(
            products, 
            many=True,
            context={"country_code": location_param, "request": request}
        )

        # Use the CategoryModelSerializer to get the breadcrumb
        category_serializer = CategoryModelSerializer(category)
        breadcrumb = category_serializer.data.get("breadcrumb", [])

        return Response({
            "breadcrumb": breadcrumb,
            "products": serializer.data
        })
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a specific ProductModel record based on an id.
        GET /api/product/{id}?location=au
        Optional query params:
        - location (string) e.g. ?location=AU for location-specific pricing and currency
        """
        product = get_object_or_404(ProductModel, id=pk)
        
        # Get location from query parameters for location-specific pricing and currency
        location_param = request.query_params.get("location", "au").upper()
        
        serializer = ProductModelSerializer(
            product,
            context={"country_code": location_param, "request": request}
        )

        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='featured')
    def featured(self, request):
        """
        Retrieve a set of three featured products.
        GET /api/product/featured?location=au
        """
        featured_products = ProductModel.objects.filter(featured=True)
        
        # Apply location filtering via ProductLocation
        location = request.query_params.get("location", "au").upper()
        if location:
            # Filter products that have ProductLocation entries for this location
            featured_products = featured_products.filter(
                locations__location__country_code__iexact=location
            ).distinct()
            
        featured_products = featured_products[:3]
        
        # Pass location to serializer for proper pricing
        serializer = ProductModelSerializer(
            featured_products, 
            many=True,
            context={"country_code": location, "request": request}
        )

        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='related')
    def retrieveRelatedProducts(self, request, pk):
        """
        Retrieve related products based on their categories.
        GET /api/product/{id}/related
        """
        product = get_object_or_404(ProductModel, id=pk)

        # Get the category of current product
        category = product.category

        # Retrieve all child categories if any, including the current one
        child_categories = category.get_descendants(include_self=True)

        # Fetch products in these categories, excluding the current product
        related_products = ProductModel.objects.filter(
            category__in=child_categories
        ).exclude(id=product.id)
        
        # Apply location filtering if provided via ProductLocation
        location = request.query_params.get("location", "au").upper()
        if location:
            # Filter products that have ProductLocation entries for this location
            related_products = related_products.filter(
                locations__location__country_code__iexact=location
            ).distinct()

        # Pass location to serializer for proper pricing
        serializer = ProductModelSerializer(
            related_products, 
            many=True,
            context={"country_code": location, "request": request}
        )
        return Response(serializer.data)

    def create(self, request):
        """
        Creates a new product with its associated product items and variant configurations.
        POST /api/product
        Body:
        {
            "name": "Awesome T-Shirt 3",
            "description": "100% cotton",
            "images": ["http://example.com/image1.jpg", "http://example.com/image2.jpg"],
            "featured": true,
            "category": "mens",
            "locations": ["US", "CA"],
            "product_items": [
                {
                    "sku": "TSHIRT-001",
                    "stock": 10,
                    "price": 19.99,
                    "imageUrls": ["http://example.com/item1.jpg"],
                    "variations": [
                        {"variant": "ebeb487d-67d5-498e-948f-02896e24526c"},
                        {"variant": "82c5da0e-6dd1-474b-8f7c-69410cca7a62"}
                    ]
                }
            ]
        } 
        """
        # Need to copy the object as changes to the request object
        # cause issues for the S3 upload. 
        data = request.data.copy()

        # Create S3 client with our credentials.
        s3_client = boto3.client(
            service_name='s3',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY
        )

        # For each image we want to get the name of the file, upload the object
        # and then return the CloudFront CDN URL to append to the uploaded image
        # URLs. This is because we don't want items stored in the bucket to be publicly
        # available. The Cloud front service will allow us to serve these images on
        # our frontend without users or any part of the system needing to be authenticated.
        uploaded_image_urls = []
        for img in request.FILES.getlist("images"):
            name, ext = os.path.splitext(img.name)
            safe_name = slugify(name) + ext

            s3_client.upload_fileobj(
                Fileobj=img,
                Bucket=settings.AWS_S3_BUCKET_NAME,
                Key=f"products/{safe_name}",
            )
            uploaded_image_urls.append(f"https://{settings.AWS_CLOUD_FRONT_DOMAIN}/products/{safe_name}")

        # Create a payload JSON object to have proper format for our serializers.
        # The POST request now takes in a multipart/form-data to properly handle 
        # file uploads. This was causing issues when serializing and can be alleviated
        # by doing the following.
        payload = {
            "name": data.get("name"),
            "description": data.get("description"),
            "featured": data.get("featured"),
            "category": data.get("category"),
            "images": uploaded_image_urls,
            "product_items": json.loads(data.get('product_items')),
            "locations": [data.get("location")]
        }

        serializer = ProductModelSerializer(data=payload)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductModelSerializer(product).data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """
        Updates an existing product with its associated product items and variant configurations.
        PUT /api/product/{id}
        Body:
        {
            "name": "Updated T-Shirt Name",
            "description": "Updated description",
            "images": ["http://example.com/new-image.jpg"],
            "featured": false,
            "category": "womens",
            "product_items": [
                {
                    "id": "existing-item-id",  // Include ID to update existing item
                    "sku": "TSHIRT-001-UPDATED",
                    "stock": 15,
                    "price": 24.99,
                    "imageUrls": ["http://example.com/updated-item.jpg"],
                    "variations": [
                        {"variant": "new-variant-id"}
                    ]
                },
                {
                    // If no ID is provided, a new item will be created.
                    "sku": "TSHIRT-002",
                    "stock": 5,
                    "price": 29.99,
                    "imageUrls": ["http://example.com/new-item.jpg"],
                    "variations": [
                        {"variant": "another-variant-id"}
                    ]
                }
            ]
        }
        Note: Product items not included in the request will be deleted. 
        (For example if a product has small, medium, and large, and the 
        request only includes small and medium items, the large item will be deleted.)
        """
        product = get_object_or_404(ProductModel, id=pk)
        serializer = ProductModelSerializer(product, data=request.data)
        if serializer.is_valid():
            updated_product = serializer.save()
            return Response(ProductModelSerializer(updated_product).data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        """
        Partially updates an existing product with only the provided fields.
        PATCH /api/product/{id}
        Body (only include fields you want to update):
        {
            "name": "New Product Name"
        }
        OR
        {
            "product_items": [
                {
                    "id": "existing-item-id", // you need to specify the id, otherwise new item will be created.
                    "stock": 25 
                }
            ]
        }
        OR
        {
            "featured": true,
            "locations": ["US", "CA"]  // Update multiple fields
        }
        
        Note: For product_items, only items with IDs will be updated. 
        Items without IDs will be created as new items.
        For product_items, if the Stock, price or imageUrls are not included in the request, an error will be thrown. (only applies to new products/products with no id defined)
        Items not included in the request will remain unchanged (not deleted).
        """
        product = get_object_or_404(ProductModel, id=pk)
        serializer = ProductModelSerializer(product, data=request.data, partial=True)
        if serializer.is_valid():
            updated_product = serializer.save()
            return Response(ProductModelSerializer(updated_product).data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        

    @action(detail=True, methods=['post'], url_path='upload/image')
    def upload_image(self, request, pk):
        """
        Specific upload endpoint for single image uploads. Primarily used for
        updating the images in the admin dashboard.
        GET /api/product/{id}/upload/image
        """
        # Create S3 client with our credentials.
        s3_client = boto3.client(
            service_name='s3',
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY
        )

        # For each image we want to get the name of the file, upload the object
        # and then return the CloudFront CDN URL to append to the uploaded image
        # URLs. This is because we don't want items stored in the bucket to be publicly
        # available. The Cloud front service will allow us to serve these images on
        # our frontend without users or any part of the system needing to be authenticated.
        uploaded_image_urls = []
        for img in request.FILES.getlist("images"):
            name, ext = os.path.splitext(img.name)
            safe_name = slugify(name) + ext

            s3_client.upload_fileobj(
                Fileobj=img,
                Bucket=settings.AWS_S3_BUCKET_NAME,
                Key=f"products/{safe_name}",
            )
            uploaded_image_urls.append(f"https://{settings.AWS_CLOUD_FRONT_DOMAIN}/products/{safe_name}")
        

        return Response(data=uploaded_image_urls, status=status.HTTP_200_OK)
