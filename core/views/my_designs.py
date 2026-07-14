from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import RoomDesign

@login_required
def my_designs(request):
    """View for displaying user's saved room designs"""
    designs = RoomDesign.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'my_designs.html', {'designs': designs})
