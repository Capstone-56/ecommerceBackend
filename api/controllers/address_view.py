from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseServerError

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from base.models import *

from api.serializers import AddressSerializer, UserAddressSerializer

class AddressViewSet(viewsets.ViewSet):
    addressSerializer = AddressSerializer
    userAddressSerializer = UserAddressSerializer
    
    def get_permissions(self):
        """
        Allow createForCheckout for both authenticated and non-authenticated users.
        All other endpoints require authentication.
        """
        if self.action == "createForCheckout":
            return [AllowAny()]
        
        return [IsAuthenticated()]
    
    def create(self, request):
        """
        POST /api/address
        Body:
        {
            "addressLine": string,
            "city": string,
            "state": string,
            "postcode": string,
            "country": string,
            "makeDefault": boolean (optional, defaults to False)
        }
        create a user's stored address in the database
        """
        user = request.user
        makeDefault = request.data.get("makeDefault", False)

        body = {
            "addressLine": request.data.get("addressLine"),
            "city": request.data.get("city"),
            "state": request.data.get("state"),
            "postcode": request.data.get("postcode"),
            "country": request.data.get("country")
        }

        addressSerializer = self.addressSerializer(data=body)
        if not addressSerializer.is_valid():
            return HttpResponseBadRequest(addressSerializer.errors)

        try:
            with transaction.atomic():
                # Check if exact address already exists in address table
                existingAddress = AddressModel.objects.filter(**body).first()
                
                if existingAddress:
                    # Check if user already has this address         
                    if UserAddressModel.objects.filter(
                        user=user, address=existingAddress
                    ).exists():
                        return HttpResponseBadRequest("You already have this address in your address book")
                    
                    # Link existing address to user
                    if makeDefault:
                        UserAddressModel.objects.filter(user=user, isDefault=True).update(isDefault=False)
                    
                    userAddress = UserAddressModel.objects.create(
                        user=user,
                        address=existingAddress,
                        isDefault=makeDefault
                    )
                else:
                    # Create new address
                    addr = AddressModel.objects.create(**body)

                    # Clear existing default
                    if makeDefault:
                        UserAddressModel.objects.filter(user=user, isDefault=True).update(isDefault=False)

                    # Link new address to user
                    userAddress = UserAddressModel.objects.create(
                        user=user,
                        address=addr,
                        isDefault=makeDefault
                    )

                return Response(self.userAddressSerializer(userAddress).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return HttpResponseServerError(str(e))

    def list(self, request):
        """
        GET /api/address
        Get all addresses for the authenticated user
        """
        user = request.user
        userAddresses = UserAddressModel.objects.filter(user=user).select_related("address")
        return Response(self.userAddressSerializer(userAddresses, many=True).data)

    def update(self, request, pk=None):
        """
        PUT /api/address/{id}
        Body:
        {
            "addressLine": string,
            "city": string,
            "state": string,
            "postcode": string,
            "country": string,
            "makeDefault": boolean
        }
        Update one of user's addresses by creating a new entry in the address table,
        and link it to the UserAddress table
        """
        user = request.user
        currentAddress = get_object_or_404(UserAddressModel, id=pk, user=user)
        
        makeDefault = request.data.get("makeDefault", currentAddress.isDefault)
        
        body = {
            "addressLine": request.data.get("addressLine"),
            "city": request.data.get("city"),
            "state": request.data.get("state"),
            "postcode": request.data.get("postcode"),
            "country": request.data.get("country")
        }

        addressSerializer = self.addressSerializer(data=body)
        if not addressSerializer.is_valid():
            return HttpResponseBadRequest(addressSerializer.errors)

        try:
            with transaction.atomic():
                # Check if user already has this address in their other saved addresses
                if UserAddressModel.objects.filter(
                    user=user,
                    address__addressLine=body["addressLine"],
                    address__city=body["city"],
                    address__state=body["state"],
                    address__postcode=body["postcode"],
                    address__country=body["country"]
                ).exclude(id=currentAddress.id).exists():
                    return HttpResponseBadRequest("You already have this address in your address book")

                # Check if exact address already exists in address table
                existingAddress = AddressModel.objects.filter(**body).first()
                
                if existingAddress:
                    # Reuse existing address record - update in place
                    currentAddress.address = existingAddress
                else:
                    # Create new address entry - update in place
                    currentAddress.address = AddressModel.objects.create(**body)
                    
                if makeDefault:
                    UserAddressModel.objects.filter(user=user, isDefault=True).update(isDefault=False)

                currentAddress.isDefault = makeDefault
                currentAddress.save()

                return Response(self.userAddressSerializer(currentAddress).data)
        except Exception as e:
            return HttpResponseServerError(str(e))

    def destroy(self, request, pk=None):
        """
        DELETE /api/address/{id}
        Remove an address from user's address book
        (doesn't delete from address table - maintains immutability)
        """
        user = request.user
        userAddress = get_object_or_404(UserAddressModel, id=pk, user=user)
        
        try:
            with transaction.atomic():
                wasDefault = userAddress.isDefault
                userAddress.delete()
                
                # If this was the default address, make another address default if any exist
                if wasDefault:
                    remainingAddresses = UserAddressModel.objects.filter(user=user)
                    if remainingAddresses.exists():
                        # Make the first remaining address the default
                        firstAddress = remainingAddresses.first()
                        firstAddress.isDefault = True
                        firstAddress.save()

                return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return HttpResponseServerError(str(e))

    @action(detail=True, methods=["put"])
    def setDefault(self, request, pk=None):
        """
        PUT /api/address/{id}/setDefault
        Set a specific address as the user's default address
        """
        user = request.user
        userAddress = get_object_or_404(UserAddressModel, id=pk, user=user)
        
        try:
            with transaction.atomic():
                # Clear existing default
                UserAddressModel.objects.filter(user=user, isDefault=True).update(isDefault=False)
                
                # Set new default
                userAddress.isDefault = True
                userAddress.save()

                return Response(self.userAddressSerializer(userAddress).data)
        except Exception as e:
            return HttpResponseServerError(str(e))

    @action(detail=False, methods=["post"], url_path="checkout")
    def createForCheckout(self, request):
        """
        POST /api/address/checkout
        Body:
        {
            "addressLine": string,
            "city": string,
            "state": string,
            "postcode": string,
            "country": string,
            "saveToAddressBook": boolean  # optional, defaults to False
        }
        Create address for checkout. Optionally save to user's address book.
        Returns the address info needed for order processing.
        """
        user = request.user
        # Only authenticated users can save to address book
        saveToAddressBook = request.data.get("saveToAddressBook", False) and user.is_authenticated
        
        body = {
            "addressLine": request.data.get("addressLine"),
            "city": request.data.get("city"),
            "state": request.data.get("state"),
            "postcode": request.data.get("postcode"),
            "country": request.data.get("country")
        }

        addressSerializer = self.addressSerializer(data=body)
        if not addressSerializer.is_valid():
            return HttpResponseBadRequest(addressSerializer.errors)

        try:
            with transaction.atomic():
                # Check for conflicts if user wants to save to address book (only for authenticated users)
                if saveToAddressBook and UserAddressModel.objects.filter(
                    user=user,
                    address__addressLine=body["addressLine"],
                    address__city=body["city"],
                    address__state=body["state"],
                    address__postcode=body["postcode"],
                    address__country=body["country"]
                ).exists():
                    saveToAddressBook = False
                
                # Get or create address record
                addressRecord, _ = AddressModel.objects.get_or_create(**body)
                
                # Link to user if requested and no conflicts
                if saveToAddressBook:
                    UserAddressModel.objects.create(
                        user=user,
                        address=addressRecord,
                        isDefault=False
                    )

                return Response(self.addressSerializer(addressRecord).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return HttpResponseServerError(str(e))
