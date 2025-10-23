# accounts/urls.py
from django.urls import path
from . import views # Import views from the current app

urlpatterns = [
    # User Authentication & Management
    path('register/', views.UserRegisterView.as_view(), name='register'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),

    # Friend Requests
    path('friends/request/send/', views.FriendRequestSendView.as_view(), name='friend-request-send'),
    path('friends/request/pending/', views.PendingFriendRequestsView.as_view(), name='friend-request-pending'),
    # Use <int:pk> to capture the friendship request ID from the URL
    path('friends/request/<int:pk>/action/', views.FriendRequestActionView.as_view(), name='friend-request-action'),
    path('friends/list/', views.FriendListView.as_view(), name='friend-list'),

    # Transactions
    path('transactions/create/', views.CreateTransactionView.as_view(), name='transaction-create'),
    path('transactions/pending/', views.PendingTransactionsView.as_view(), name='transaction-pending-received'),
    path('transactions/sent-pending/', views.SentPendingTransactionsView.as_view(), name='transaction-pending-sent'), # Optional view
    # Use <int:pk> to capture the transaction ID from the URL
    path('transactions/<int:pk>/action/', views.TransactionActionView.as_view(), name='transaction-action'),
    path('transactions/history/', views.TransactionHistoryView.as_view(), name='transaction-history'), # Expects ?friend=username
]