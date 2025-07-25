from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from base.models import ShoppingCartItemModel, ProductItemModel

from api.serializers import CartItemSerializer

class ShoppingCartViewSet(viewsets.ViewSet):
  permission_classes = [IsAuthenticated]

  def list(self, request):
    """
    GET /api/cart
    get the cart of the authenticated user
    """
    cart_items = ShoppingCartItemModel.objects.filter(user=request.user)
    serializer = CartItemSerializer(cart_items, many=True)

    return Response(serializer.data)

  def create(self, request):
    """
    POST /api/cart
    add a product item to the cart
    Body:
    {
      "productItemId": string,
      "quantity": integer
    }
    """
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

    serializer = CartItemSerializer(cart_item)

    return Response(serializer.data, status=status.HTTP_201_CREATED)

  def update(self, request, pk=None):
    """
    PUT /api/cart/{id}
    update quantity of a cart item
    Body:
    {
      "quantity": integer
    }
    """
    cart_item = get_object_or_404(ShoppingCartItemModel, id=pk, user=request.user)
    quantity = request.data.get("quantity")

    if quantity is None:
        return Response(
            {"error": "Quantity is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    cart_item.quantity = quantity
    cart_item.save()

    serializer = CartItemSerializer(cart_item)

    return Response(serializer.data)

  def destroy(self, request, pk=None):
    """
    DELETE /api/cart/{id}
    remove an item from the cart
    """
    cart_item = get_object_or_404(ShoppingCartItemModel, id=pk, user=request.user)
    cart_item.delete()

    return Response(status=status.HTTP_204_NO_CONTENT)
