# accounts/views.py
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token

from .serializers import (
    LoginSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    FriendshipSerializer,
    FriendshipStatusUpdateSerializer,
    FriendTransactionSerializer,
    TransactionStatusUpdateSerializer,
    SimpleUserSerializer,
    TransactionDeleteRequestSerializer,      # ← ADD THIS
    HistoryResetRequestSerializer,           # ← ADD THIS
    DeleteRequestActionSerializer,           # ← ADD THIS
    ResetRequestActionSerializer,            # ← ADD THIS
)

from .models import (
    Friendship,
    FriendTransaction,
    TransactionDeleteRequest,  # ← ADD THIS
    HistoryResetRequest,        # ← ADD THIS
)

User = get_user_model()
class UserRegisterView(generics.CreateAPIView):
    """
    API view for user registration.
    Allows anyone to create a new user account.
    Returns user info and auth token.
    """
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        # Call the parent create method
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Get the created user
        user = serializer.instance
        
        # Create or get auth token for the user
        token, created = Token.objects.get_or_create(user=user)
        
        # Return user info with token
        return Response({
            'user': UserSerializer(user, context=self.get_serializer_context()).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)
    
class ChangePasswordView(generics.UpdateAPIView):
    """
    API view for changing the password of the currently authenticated user.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated] # Must be logged in

    def get_object(self, queryset=None):
        # Return the currently authenticated user
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            # save() method in the serializer handles the password update
            serializer.save()
            return Response({"detail": "Password updated successfully"}, status=status.HTTP_200_OK)

        # Note: is_valid(raise_exception=True) handles returning 400 Bad Request on errors

# --- Friendship Views ---

class FriendRequestSendView(generics.CreateAPIView):
    """
    API view to send a friend request to another user by username.
    """
    serializer_class = FriendshipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        receiver_username = serializer.validated_data.get('receiver_username')
        if not receiver_username:
            raise ValidationError("Receiver username must be provided.")

        try:
            receiver = User.objects.get(username=receiver_username)
        except User.DoesNotExist:
            raise NotFound("User with that username does not exist.")

        requester = self.request.user

        if requester == receiver:
            raise ValidationError("You cannot send a friend request to yourself.")

        # Check if a request already exists (in either direction)
        existing_request = Friendship.objects.filter(
            (Q(requester=requester, receiver=receiver) | Q(requester=receiver, receiver=requester))
        ).first()

        if existing_request:
            if existing_request.status == Friendship.StatusChoices.ACCEPTED:
                 raise ValidationError("You are already friends with this user.")
            elif existing_request.status == Friendship.StatusChoices.PENDING:
                 # If request exists B->A and A tries A->B, maybe auto-accept? Or just raise error.
                 # For simplicity, we raise error here.
                 if existing_request.requester == receiver: # They already sent you a request
                    raise ValidationError(f"User '{receiver_username}' has already sent you a friend request. Accept or reject it.")
                 else: # You already sent them a request
                    raise ValidationError(f"You have already sent a friend request to '{receiver_username}'.")
            elif existing_request.status == Friendship.StatusChoices.REJECTED:
                # Optional: Allow resending a request after rejection? If so, delete existing and create new.
                # For now, prevent resending.
                raise ValidationError(f"Your previous friend request with '{receiver_username}' was rejected.")
            # Add handling for other potential statuses if needed

        # If no blocking request exists, create the new pending request
        serializer.save(requester=requester, receiver=receiver, status=Friendship.StatusChoices.PENDING)

class PendingFriendRequestsView(generics.ListAPIView):
    """
    API view to list pending friend requests received by the authenticated user.
    """
    serializer_class = FriendshipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return requests where the current user is the receiver and status is pending
        return Friendship.objects.filter(
            receiver=self.request.user,
            status=Friendship.StatusChoices.PENDING
        )

class FriendRequestActionView(generics.UpdateAPIView):
    """
    API view to accept or reject a pending friend request.
    The URL for this view should include the friendship request ID (pk).
    """
    queryset = Friendship.objects.all()
    serializer_class = FriendshipStatusUpdateSerializer # Use the simple status update serializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Ensure the user can only act on requests sent *to* them that are pending
        return Friendship.objects.filter(
            receiver=self.request.user,
            status=Friendship.StatusChoices.PENDING
        )

    def update(self, request, *args, **kwargs):
        friendship = self.get_object() # Gets the specific request based on pk in URL
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            new_status = serializer.validated_data['status']
            if friendship.status == Friendship.StatusChoices.PENDING:
                friendship.status = new_status
                friendship.save()
                # Return the updated friendship details
                return Response(FriendshipSerializer(friendship).data, status=status.HTTP_200_OK)
            else:
                # Should not happen due to get_queryset, but good practice to check
                return Response({"detail": "This request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

class FriendListView(generics.ListAPIView):
    """
    API view to list all accepted friends of the authenticated user.
    """
    serializer_class = SimpleUserSerializer # Show basic user info
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Find friendships where the status is accepted and the user is either requester or receiver
        accepted_friendships = Friendship.objects.filter(
            (Q(requester=user) | Q(receiver=user)),
            status=Friendship.StatusChoices.ACCEPTED
        )
        # Get the IDs of the friends (the user who is NOT the current user)
        friend_ids = set()
        for friendship in accepted_friendships:
            if friendship.requester == user:
                friend_ids.add(friendship.receiver.id)
            else:
                friend_ids.add(friendship.requester.id)

        # Return the User objects corresponding to the friend IDs
        return User.objects.filter(id__in=friend_ids).order_by('username')


# --- Friend Transaction Views ---

class CreateTransactionView(generics.CreateAPIView):
    """
    API view to create/initiate a new transaction with a friend.
    """
    serializer_class = FriendTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        friend_username = serializer.validated_data.get('friend_username')
        amount = serializer.validated_data.get('amount')
        description = serializer.validated_data.get('description', '')

        if not friend_username:
            raise ValidationError("Friend username must be provided.")
        if amount is None:
             raise ValidationError("Amount must be provided.")
        if amount == 0:
             raise ValidationError("Amount cannot be zero.")

        try:
            friend = User.objects.get(username=friend_username)
        except User.DoesNotExist:
            raise NotFound("User (friend) with that username does not exist.")

        initiator = self.request.user

        if initiator == friend:
            raise ValidationError("You cannot create a transaction with yourself.")

        # Check if they are actually friends (status='accepted')
        are_friends = Friendship.objects.filter(
            (Q(requester=initiator, receiver=friend, status=Friendship.StatusChoices.ACCEPTED) |
             Q(requester=friend, receiver=initiator, status=Friendship.StatusChoices.ACCEPTED))
        ).exists()

        if not are_friends:
            raise ValidationError(f"You are not friends with '{friend_username}'.")

        # Save the transaction with pending status
        serializer.save(
            initiator=initiator,
            friend=friend,
            status=FriendTransaction.StatusChoices.PENDING,
            amount=amount, # Ensure amount sign convention is handled if needed here or in serializer
            description=description
        )

class PendingTransactionsView(generics.ListAPIView):
    """
    API view to list pending transactions that require action from the authenticated user.
    (i.e., transactions initiated by *other* users involving the current user).
    """
    serializer_class = FriendTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return transactions where the current user is the 'friend' (receiver)
        # and the status is 'pending'
        return FriendTransaction.objects.filter(
            friend=self.request.user,
            status=FriendTransaction.StatusChoices.PENDING
        )

class TransactionActionView(generics.UpdateAPIView):
    """
    API view for the 'friend' user to accept or reject a pending transaction.
    The URL for this view should include the transaction ID (pk).
    """
    queryset = FriendTransaction.objects.all()
    serializer_class = TransactionStatusUpdateSerializer # Use simple status update serializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Ensure user can only act on transactions where they are the 'friend' and status is pending
        return FriendTransaction.objects.filter(
            friend=self.request.user,
            status=FriendTransaction.StatusChoices.PENDING
        )

    def update(self, request, *args, **kwargs):
        transaction = self.get_object() # Gets specific transaction based on pk in URL
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            new_status = serializer.validated_data['status']
            if transaction.status == FriendTransaction.StatusChoices.PENDING:
                transaction.status = new_status
                transaction.action_taken_by = request.user # Record who took the action
                transaction.save()
                # Return the updated transaction details
                return Response(FriendTransactionSerializer(transaction).data, status=status.HTTP_200_OK)
            else:
                 # Should not happen due to get_queryset
                return Response({"detail": "This transaction is not pending."}, status=status.HTTP_400_BAD_REQUEST)

class TransactionHistoryView(generics.ListAPIView):
    """
    API view to retrieve transaction history between the authenticated user
    and a specific friend.
    Returns all transactions (pending, accepted, rejected) between the two users.
    """
    serializer_class = FriendTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        friend_username = self.request.query_params.get('friend')
        
        if not friend_username:
            raise ValidationError("Friend username must be provided as a query parameter.")
        
        try:
            friend = User.objects.get(username=friend_username)
        except User.DoesNotExist:
            raise NotFound("Friend not found.")
        
        # Get all transactions between the two users (both directions)
        transactions = FriendTransaction.objects.filter(
            Q(initiator=user, friend=friend) | Q(initiator=friend, friend=user)
        ).order_by('-created_at')
        
        return transactions
# --- Optional: View to see transactions YOU initiated that are still pending ---
class SentPendingTransactionsView(generics.ListAPIView):
    """
    API view to list pending transactions initiated BY the authenticated user.
    """
    serializer_class = FriendTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FriendTransaction.objects.filter(
            initiator=self.request.user,
            status=FriendTransaction.StatusChoices.PENDING
        )
    
# --- User Login View ---
class LoginView(generics.GenericAPIView):
    """
    API view for user login.
    Takes username and password, returns an auth token.
    """
    permission_classes = [permissions.AllowAny] # Anyone can try to log in
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        # Get or create a token for the user
        token, created = Token.objects.get_or_create(user=user)
        
        # Return the token and user info
        return Response({
            "user": UserSerializer(user, context=self.get_serializer_context()).data,
            "token": token.key
        }, status=status.HTTP_200_OK)
    

class UserSearchView(generics.ListAPIView):
    """
    API view to search for users by username.
    Returns a list of users matching the search query.
    """
    serializer_class = SimpleUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        username_query = self.request.query_params.get('username', None)
        
        if not username_query:
            return User.objects.none()
        
        # Search for users whose username contains the query (case-insensitive)
        # Exclude the current user from results
        return User.objects.filter(
            username__icontains=username_query
        ).exclude(
            id=self.request.user.id
        ).order_by('username')[:10]
    

class RequestTransactionDeleteView(generics.CreateAPIView):
    """
    API view to request deletion of a specific transaction.
    Creates a pending delete request that the other user must approve.
    """
    serializer_class = TransactionDeleteRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        transaction_id = self.request.data.get('transaction_id')
        
        if not transaction_id:
            raise ValidationError("Transaction ID must be provided.")
        
        try:
            transaction = FriendTransaction.objects.get(id=transaction_id)
        except FriendTransaction.DoesNotExist:
            raise NotFound("Transaction not found.")
        
        requester = self.request.user
        
        # Verify user is part of this transaction
        if requester not in [transaction.initiator, transaction.friend]:
            raise ValidationError("You are not part of this transaction.")
        
        # Check if a delete request already exists for this transaction
        existing_request = TransactionDeleteRequest.objects.filter(
            transaction=transaction,
            status=TransactionDeleteRequest.StatusChoices.PENDING
        ).first()
        
        if existing_request:
            raise ValidationError("A delete request already exists for this transaction.")
        
        # Create the delete request
        serializer.save(
            transaction=transaction,
            requester=requester,
            status=TransactionDeleteRequest.StatusChoices.PENDING
        )


class PendingDeleteRequestsView(generics.ListAPIView):
    """
    API view to list pending delete requests that require action from the user.
    """
    serializer_class = TransactionDeleteRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Get transactions where user is involved
        user_transactions = FriendTransaction.objects.filter(
            Q(initiator=user) | Q(friend=user)
        )
        
        # Get delete requests for these transactions where user is NOT the requester
        return TransactionDeleteRequest.objects.filter(
            transaction__in=user_transactions,
            status=TransactionDeleteRequest.StatusChoices.PENDING
        ).exclude(requester=user)


class DeleteRequestActionView(generics.UpdateAPIView):
    """
    API view to approve or reject a delete request.
    If approved, the transaction is permanently deleted.
    """
    queryset = TransactionDeleteRequest.objects.all()
    serializer_class = DeleteRequestActionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Get transactions where user is involved
        user_transactions = FriendTransaction.objects.filter(
            Q(initiator=user) | Q(friend=user)
        )
        
        # Can only act on delete requests for their transactions (not created by them)
        return TransactionDeleteRequest.objects.filter(
            transaction__in=user_transactions,
            status=TransactionDeleteRequest.StatusChoices.PENDING
        ).exclude(requester=user)

    def update(self, request, *args, **kwargs):
        delete_request = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid(raise_exception=True):
            new_status = serializer.validated_data['status']
            delete_request.status = new_status
            delete_request.save()
            
            # If approved, delete the transaction permanently
            if new_status == TransactionDeleteRequest.StatusChoices.APPROVED:
                transaction = delete_request.transaction
                transaction.delete()
                return Response(
                    {"detail": "Delete request approved. Transaction deleted."},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "Delete request rejected."},
                    status=status.HTTP_200_OK
                )


# ============================================
# History Reset Request Views
# ============================================

class RequestHistoryResetView(generics.CreateAPIView):
    """
    API view to request resetting transaction history with a friend.
    Creates a pending reset request that the friend must approve.
    """
    serializer_class = HistoryResetRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        friend_username = self.request.data.get('friend_username')
        
        if not friend_username:
            raise ValidationError("Friend username must be provided.")
        
        try:
            target_user = User.objects.get(username=friend_username)
        except User.DoesNotExist:
            raise NotFound("Friend not found.")
        
        requester = self.request.user
        
        if requester == target_user:
            raise ValidationError("You cannot reset history with yourself.")
        
        # Check if they are friends
        are_friends = Friendship.objects.filter(
            (Q(requester=requester, receiver=target_user, status=Friendship.StatusChoices.ACCEPTED) |
             Q(requester=target_user, receiver=requester, status=Friendship.StatusChoices.ACCEPTED))
        ).exists()
        
        if not are_friends:
            raise ValidationError("You are not friends with this user.")
        
        # Check if a reset request already exists
        existing_request = HistoryResetRequest.objects.filter(
            Q(requester=requester, target_user=target_user) |
            Q(requester=target_user, target_user=requester),
            status=HistoryResetRequest.StatusChoices.PENDING
        ).first()
        
        if existing_request:
            raise ValidationError("A reset request already exists between you and this friend.")
        
        # Create the reset request
        serializer.save(
            requester=requester,
            target_user=target_user,
            status=HistoryResetRequest.StatusChoices.PENDING
        )


class PendingResetRequestsView(generics.ListAPIView):
    """
    API view to list pending reset requests received by the user.
    """
    serializer_class = HistoryResetRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return HistoryResetRequest.objects.filter(
            target_user=self.request.user,
            status=HistoryResetRequest.StatusChoices.PENDING
        )


class ResetRequestActionView(generics.UpdateAPIView):
    """
    API view to approve or reject a history reset request.
    If approved, all ACCEPTED transactions between the two users are deleted.
    """
    queryset = HistoryResetRequest.objects.all()
    serializer_class = ResetRequestActionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return HistoryResetRequest.objects.filter(
            target_user=self.request.user,
            status=HistoryResetRequest.StatusChoices.PENDING
        )

    def update(self, request, *args, **kwargs):
        reset_request = self.get_object()
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid(raise_exception=True):
            new_status = serializer.validated_data['status']
            reset_request.status = new_status
            reset_request.save()
            
            # If approved, delete all ACCEPTED transactions between the two users
            if new_status == HistoryResetRequest.StatusChoices.APPROVED:
                requester = reset_request.requester
                target = reset_request.target_user
                
                # Find all accepted transactions between them
                transactions_to_delete = FriendTransaction.objects.filter(
                    (Q(initiator=requester, friend=target) | 
                     Q(initiator=target, friend=requester)),
                    status=FriendTransaction.StatusChoices.ACCEPTED
                )
                
                count = transactions_to_delete.count()
                transactions_to_delete.delete()
                
                return Response(
                    {"detail": f"History reset approved. {count} transactions deleted."},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "History reset request rejected."},
                    status=status.HTTP_200_OK
                )