from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import ShoppingCartItemModel, ProductItemModel

from api.serializers import CartItemSerializer

class ShoppingCartViewSet(viewsets.ViewSet):
  permission_classes = [IsAuthenticated]

  def list(self, request):
    """
    GET /api/cart?location=AU
    get the cart of the authenticated user
    Required query params:
    - location (string) e.g. ?location=AU for location-specific pricing
    """
    # Get location from query parameters
    location_param = request.query_params.get("location")
    if not location_param:
        return HttpResponseBadRequest("Location parameter is required")
    
    location_param = location_param.upper()
    
    cart_items = ShoppingCartItemModel.objects.filter(user=request.user)
    serializer = CartItemSerializer(
        cart_items, 
        many=True, 
        context={"country_code": location_param}
    )

    return Response(serializer.data)

  def create(self, request):
    """
    POST /api/cart?location=AU
    add a product item to the cart
    Required query params:
    - location (string) e.g. ?location=AU for location-specific pricing
    Body:
    {
      "productItemId": string,
      "quantity": integer
    }
    """
    # Get location from query parameters
    location_param = request.query_params.get("location")
    if not location_param:
        return HttpResponseBadRequest("Location parameter is required")
    
    location_param = location_param.upper()
    
    product_item_id = request.data.get("productItemId")
    quantity = request.data.get("quantity", 1)

    product_item = get_object_or_404(ProductItemModel, id=product_item_id)
    
    # Check if item already exists in cart
    cart_item, created = ShoppingCartItemModel.objects.get_or_create(
        user=request.user,
        productItem=product_item,
        defaults={"quantity": quantity}
    )

    if not created:
        # increment quantity if item already exists
        cart_item.quantity += quantity
        cart_item.save()

    serializer = CartItemSerializer(cart_item, context={"country_code": location_param})

    return Response(serializer.data, status=status.HTTP_201_CREATED)

  def update(self, request, pk=None):
    """
    PUT /api/cart/{id}?location=AU
    update quantity of a cart item
    Required query params:
    - location (string) e.g. ?location=AU for location-specific pricing
    Body:
    {
      "quantity": integer
    }
    """
    # Get location from query parameters
    location_param = request.query_params.get("location")
    if not location_param:
        return HttpResponseBadRequest("Location parameter is required")
    
    location_param = location_param.upper()
    
    cart_item = get_object_or_404(ShoppingCartItemModel, id=pk, user=request.user)
    quantity = request.data.get("quantity")

    if quantity is None:
        return HttpResponseBadRequest("Quantity is required")

    cart_item.quantity = quantity
    cart_item.save()

    serializer = CartItemSerializer(cart_item, context={"country_code": location_param})

    return Response(serializer.data)

  def destroy(self, request, pk=None):
    """
    DELETE /api/cart/{id}
    remove an item from the cart
    """
    cart_item = get_object_or_404(ShoppingCartItemModel, id=pk, user=request.user)
    cart_item.delete()

    return Response(status=status.HTTP_204_NO_CONTENT)
