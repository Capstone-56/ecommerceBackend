from django.shortcuts import get_object_or_404
from django.db.models import Min, Max, Count
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from base.abstractModels import PagedList
from base.models import ProductModel, VariantModel, CategoryModel
from api.serializers import ProductModelSerializer

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

        If categories is provided, returns products linked to *all* of those categories.
        """
        querySet = ProductModel.objects.all()

        categoriesParam = request.query_params.get("categories")
        if categoriesParam:
            # split on comma and strip whitespace
            categoryIds = [c.strip() for c in categoriesParam.split(",") if c.strip()]
            for cat in categoryIds:
                querySet = querySet.filter(category_links__category=cat)
            querySet = querySet.distinct()
        
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

        paginator = PagedList()
        pagedQuerySet = paginator.paginate_queryset(querySet, request)

        serializer = ProductModelSerializer(pagedQuerySet, many=True, context={"sort": sort})
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"], url_path="cat")
    def listProductsByCategory(self, request, pk=None):
        """
        Retrieve all products under a category and its subcategories,
        and generate a breadcrumb trail of parent categories.
        GET /api/product/{internalName}/cat
        """
        category = get_object_or_404(CategoryModel, internalName=pk)

        # Get all descendant categories including the current one
        categories = category.get_descendants(include_self=True)

        # Retrieve products in these categories
        products = ProductModel.objects.filter(category__in=categories)

        # Serialize products
        serializer = ProductModelSerializer(products, many=True)

        # Generate breadcrumb trail
        breadcrumb = category.get_ancestors(include_self=True).values_list("name", flat=True)

        return Response({
            "breadcrumb": list(breadcrumb),
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
