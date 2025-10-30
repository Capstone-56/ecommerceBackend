from django.http import HttpResponse

def health(request):
    """
    Health check endpoint for Load Balancer
    """
    return HttpResponse("OK", content_type="text/plain")
