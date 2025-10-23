# accounts/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # User Authentication & Management
    path('register/', views.UserRegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),

    # User Search
    path('users/search/', views.UserSearchView.as_view(), name='user-search'),

    # Friend Requests
    path('friends/request/send/', views.FriendRequestSendView.as_view(), name='friend-request-send'),
    path('friends/request/pending/', views.PendingFriendRequestsView.as_view(), name='friend-request-pending'),
    path('friends/request/<int:pk>/action/', views.FriendRequestActionView.as_view(), name='friend-request-action'),
    path('friends/list/', views.FriendListView.as_view(), name='friend-list'),

    # Transactions
    path('transactions/create/', views.CreateTransactionView.as_view(), name='transaction-create'),
    path('transactions/pending/', views.PendingTransactionsView.as_view(), name='transaction-pending-received'),
    path('transactions/sent-pending/', views.SentPendingTransactionsView.as_view(), name='transaction-pending-sent'),
    path('transactions/<int:pk>/action/', views.TransactionActionView.as_view(), name='transaction-action'),
    path('transactions/history/', views.TransactionHistoryView.as_view(), name='transaction-history'),

    # ✅ NEW: Delete Request Endpoints
    path('transactions/delete/request/', views.RequestTransactionDeleteView.as_view(), name='transaction-delete-request'),
    path('transactions/delete/pending/', views.PendingDeleteRequestsView.as_view(), name='delete-requests-pending'),
    path('transactions/delete/<int:pk>/action/', views.DeleteRequestActionView.as_view(), name='delete-request-action'),

    # ✅ NEW: Reset History Endpoints
    path('history/reset/request/', views.RequestHistoryResetView.as_view(), name='history-reset-request'),
    path('history/reset/pending/', views.PendingResetRequestsView.as_view(), name='reset-requests-pending'),
    path('history/reset/<int:pk>/action/', views.ResetRequestActionView.as_view(), name='reset-request-action'),
]
