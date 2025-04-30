from django.shortcuts import get_object_or_404
from django.db.models import Min, Max
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

from base.abstractModels import PagedList
from base.models import ProductModel
from base.models.variant_model import VariantModel
from .serializers import ProductModelSerializer

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
        - page_size (int)
        - price_min (float) e.g. ?price_min=10
        - price_max (float) e.g. ?price_max=100
        - sort (string) e.g. ?sort=priceAsc
        - sort (string) e.g. ?sort=priceDesc
        - colour (string) e.g. ?colour=red
        - categories (comma‑separated UUIDs) e.g. ?categories=id1,id2

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
            min_price=Min("items__price"),
            max_price=Max("items__price")
        )

        # filter by min_price and max_price
        price_min = request.query_params.get("price_min")
        price_max = request.query_params.get("price_max")
        if price_min:
            querySet = querySet.filter(items__price__gte=price_min)
        if price_max:
            querySet = querySet.filter(items__price__lte=price_max)
        querySet = querySet.distinct()
        
        # sort by highest or lowest price
        sort = request.query_params.get("sort")
        if sort == "priceAsc":
            querySet = querySet.order_by("min_price")
        elif sort == "priceDesc":
            querySet = querySet.order_by("-max_price")

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
