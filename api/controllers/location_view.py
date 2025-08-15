import os
import requests
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.conf import settings


class LocationViewSet(viewsets.ViewSet):
    """
    A ViewSet for location-related operations, including coordinate to country conversion.
    """

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