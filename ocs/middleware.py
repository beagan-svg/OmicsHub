from django.http import HttpResponse

class SourceMapMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the request is for a source map
        if request.path.endswith('.css.map') or request.path.endswith('.js.map'):
            # Return an empty response with 204 status code
            return HttpResponse(status=204)
        
        response = self.get_response(request)
        return response 