from django.shortcuts import get_object_or_404
from django.db.models import Min, Max, Count, Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from base.abstractModels import PagedList
from base.models import ProductModel, VariantModel, CategoryModel
from api.serializers import ProductModelSerializer, CategoryModelSerializer

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
        
        # find the min and max price of all related productItems. These will be used to filter and sort the products.
        querySet = querySet.annotate(
            minPrice=Min("items__price"),
            maxPrice=Max("items__price")
        )

        # filter by min_price and max_price
        priceMin = request.query_params.get("priceMin")
        priceMax = request.query_params.get("priceMax")
        if priceMin:
            querySet = querySet.filter(items__price__gte=priceMin)
        if priceMax:
            querySet = querySet.filter(items__price__lte=priceMax)
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

        # Search name and description using full-text search and fuzzy matching
        searchQuery = request.query_params.get("search")
        if searchQuery:
            # Create search vector for full-text search
            search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
            search_query = SearchQuery(searchQuery, config='english')
            
            # rank products based on weight of search terms
            full_text_results = querySet.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).filter(rank__gte=0.1)
            
            # fuzzy matching
            trigram_results = querySet.annotate(
                similarity=TrigramSimilarity('name', searchQuery) + 
                          TrigramSimilarity('description', searchQuery)
            ).filter(similarity__gt=0.1)
            
            # Combine results, prioritizing full-text search
            if full_text_results.exists():
                querySet = full_text_results.order_by('-rank')
            elif trigram_results.exists():
                querySet = trigram_results.order_by('-similarity')
            else:
                # Fallback to basic icontains search
                querySet = querySet.filter(
                    Q(name__icontains=searchQuery) | Q(description__icontains=searchQuery)
                )

        paginator = PagedList()
        pagedQuerySet = paginator.paginate_queryset(querySet, request)

        serializer = ProductModelSerializer(pagedQuerySet, many=True, context={"sort": sort})
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], url_path="cat")
    def listProductsByCategory(self, request, pk=None):
        """
        Retrieve all products under a category and its subcategories,
        and generate a breadcrumb trail of parent categories.
        this should replace the current GET /api/product endpoint in the near future
        unless admins might need to list the full table of products
        GET /api/product/{internalName}/cat
        """
        category = get_object_or_404(CategoryModel, internalName=pk)

        # Get all descendant categories including the current one
        categories = category.get_descendants(include_self=True)

        # Retrieve products in these categories
        products = ProductModel.objects.filter(category__in=categories)

        serializer = ProductModelSerializer(products, many=True)

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
        GET /api/product/{id}
        """
        product = get_object_or_404(ProductModel, id=pk)
        serializer = ProductModelSerializer(product)

        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='featured')
    def featured(self, request):
        """
        Retrieve a set of three featured products.
        GET /api/product/featured
        """
        featured_products = ProductModel.objects.filter(featured=True)[:3]
        serializer = ProductModelSerializer(featured_products, many=True)

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

        serializer = ProductModelSerializer(related_products, many=True)
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
            "avgRating": 4.5,
            "category": "mens",
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
        serializer = ProductModelSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductModelSerializer(product).data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
