# hisab_kitab_backend/urls.py
from django.contrib import admin
from django.urls import path, include # Add 'include' here

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include the URLs from the 'accounts' app under the 'api/accounts/' prefix
    path('api/accounts/', include('accounts.urls')),
    # You might add other app URLs or root-level API views here later
]