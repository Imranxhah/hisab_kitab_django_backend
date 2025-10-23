# accounts/views.py
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.views import APIView

from .models import Friendship, FriendTransaction
from .serializers import (
    UserSerializer,
    ChangePasswordSerializer,
    FriendshipSerializer,
    FriendshipStatusUpdateSerializer,
    FriendTransactionSerializer,
    TransactionStatusUpdateSerializer,
    SimpleUserSerializer, # Needed for listing friends
)

User = get_user_model() # Get our CustomUser model

# --- User Views ---

class UserRegisterView(generics.CreateAPIView):
    """
    API view for user registration.
    Allows anyone to create a new user account.
    """
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny] # Anyone can register
    serializer_class = UserSerializer

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
    API view to list ACCEPTED transaction history between the authenticated user and a specific friend.
    Requires the friend's username to be passed as a query parameter (e.g., /api/transactions/history/?friend=friend_username)
    """
    serializer_class = FriendTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        friend_username = self.request.query_params.get('friend', None)

        if not friend_username:
            # Return empty if no friend specified, or raise an error
            # raise ValidationError("Friend username query parameter is required.")
            return FriendTransaction.objects.none()

        try:
            friend = User.objects.get(username=friend_username)
        except User.DoesNotExist:
             # Return empty if friend not found, or raise an error
            # raise NotFound("Friend user not found.")
             return FriendTransaction.objects.none()

        # Check if they are actually friends
        are_friends = Friendship.objects.filter(
            (Q(requester=user, receiver=friend, status=Friendship.StatusChoices.ACCEPTED) |
             Q(requester=friend, receiver=user, status=Friendship.StatusChoices.ACCEPTED))
        ).exists()

        if not are_friends:
            # raise ValidationError(f"You are not friends with '{friend_username}'.")
             return FriendTransaction.objects.none()


        # Return transactions where the pair (user, friend) are initiator/friend
        # AND the status is ACCEPTED
        return FriendTransaction.objects.filter(
            (Q(initiator=user, friend=friend) | Q(initiator=friend, friend=user)),
            status=FriendTransaction.StatusChoices.ACCEPTED
        ).order_by('-updated_at') # Order by most recently updated/accepted

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