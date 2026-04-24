from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
	return render(request, 'chatia/home.html')


@login_required
def info(request):
	return render(request, 'chatia/info.html')
