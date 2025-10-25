import os
import requests

from django.shortcuts import get_object_or_404
from django.http import HttpResponseBadRequest

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from api.serializers import LocationSerializer
from base.models.location_model import LocationModel

class LocationViewSet(viewsets.ViewSet):
    """
    A ViewSet for location-related operations, including coordinate to country conversion.
    """
    def list(self, request):
        """
        Returns the list of locations to sell products in.
        GET /api/location
        """
        locations = LocationModel.objects.all()
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        Create a new location.
        POST /api/location
        
        Body:
        {
            "country_code": "US",
            "country_name": "United States",
            "currency_code": "USD"
        }
        """
        serializer = LocationSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return HttpResponseBadRequest(serializer.errors)

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific location by country code.
        GET /api/location/{country_code}
        """
        location = get_object_or_404(LocationModel, country_code=pk.upper())
        serializer = LocationSerializer(location)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """
        Update a location (PUT).
        PUT /api/location/{country_code}
        
        Body:
        {
            "country_name": "United States",
            "currency_code": "USD"
        }
        """
        location = get_object_or_404(LocationModel, country_code=pk.upper())
        serializer = LocationSerializer(location, data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return HttpResponseBadRequest(serializer.errors)

    @action(detail=False, methods=['post'], url_path='coordinates-to-country')
    def coordinates_to_country(self, request):
        """
        Convert latitude and longitude coordinates to country code using OpenCage API.
        
        POST /api/location/coordinates-to-country
        Body: {
            "latitude": float,
            "longitude": float
        }
        
        Returns: {
            "country_code": string,
            "country_name": string
        }
        """
        try:
            # Get coordinates from request body
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')
            
            if latitude is None or longitude is None:
                return Response(
                    {'error': 'Both latitude and longitude are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get OpenCage API key from environment
            api_key = os.environ.get('OPENCAGE_API_KEY')
            if not api_key:
                return Response(
                    {'error': 'OpenCage API key not configured'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Make request to OpenCage API
            opencage_url = f"https://api.opencagedata.com/geocode/v1/json"
            params = {
                'q': f"{latitude},{longitude}",
                'key': api_key,
                'limit': 1
            }
            
            response = requests.get(opencage_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get('results'):
                return Response(
                    {'error': 'No location data found for the provided coordinates'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Extract country information
            result = data['results'][0]
            components = result.get('components', {})
            
            country_code = components.get('ISO_3166-1_alpha-2')
            country_name = components.get('country')
            
            if not country_code:
                return Response(
                    {'error': 'Country code not found in location data'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response({
                'country_code': country_code.lower(),
                'country_name': country_name
            })
            
        except requests.RequestException as e:
            return Response(
                {'error': f'Failed to fetch location data: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
