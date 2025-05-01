from rest_framework import viewsets, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from base.models import *
from api.serializers import AddressBookSerializer, UserAddressSerializer

class AddressViewSet(viewsets.ViewSet):
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
          "make_default": boolean    # optional, defaults to False
        }
        create a user's stored address in the database
        """

    def update(self, request):
        """
        PUT /api/address
        update one of user's default addresses by
        creating a new entry in the AddressBook table,
        link it to the UserAddress table, then make that
        one default and the old one not-default
        """

    def addNewAddress(self, user, address, makeDefault=False):
        """
        Create an AddressBookModel entry and link it to the user.
        If makeDefault is True, clear the old default first.
        Returns the newly created UserAddressModel instance.
        """
        addr = AddressBookModel.objects.create(**address)

        if makeDefault:
            UserAddressModel.objects.filter(user=user, is_default=True).update(is_default=False)

        userAddress = UserAddressModel.objects.create(
            user=user,
            address=addr,
            isDefault=makeDefault
        )

        return userAddress
