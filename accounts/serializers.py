# accounts/serializers.py

from rest_framework import serializers
from .models import CustomUser, Friendship, FriendTransaction
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Friendship, FriendTransaction, TransactionDeleteRequest, HistoryResetRequest
User = get_user_model()

# --- User Serializer ---
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the CustomUser model.
    Includes basic user information. Password is write-only.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'password']
        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}}
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

# --- Simple User Serializer (for nested representations) ---
class SimpleUserSerializer(serializers.ModelSerializer):
    """
    Simple serializer showing basic user info.
    Used for nested representations (e.g., in friendship, transactions).
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        read_only_fields = fields

# --- Change Password Serializer ---
class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Old password is incorrect."))
        return value

    def validate_new_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError(_("New password must be at least 6 characters long."))
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

# --- Friendship Serializer ---
class FriendshipSerializer(serializers.ModelSerializer):
    """
    Serializer for the Friendship model.
    Includes nested user information for sender and receiver.
    """
    sender = SimpleUserSerializer(source='requester', read_only=True)
    receiver = SimpleUserSerializer(read_only=True)
    receiver_username = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Friendship
        fields = [
            'id',
            'sender',
            'receiver',
            'receiver_username',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'sender', 'receiver', 'created_at', 'updated_at', 'status']
    
    def create(self, validated_data):
        # Remove receiver_username since it's not a model field
        validated_data.pop('receiver_username', None)
        return super().create(validated_data)

# --- Friendship Status Update Serializer ---
class FriendshipStatusUpdateSerializer(serializers.Serializer):
    """
    Simple serializer to accept/reject a friend request.
    """
    action = serializers.ChoiceField(choices=['accept', 'reject'], required=True)

    def validate(self, attrs):
        action = attrs.get('action')
        if action == 'accept':
            attrs['status'] = Friendship.StatusChoices.ACCEPTED
        elif action == 'reject':
            attrs['status'] = Friendship.StatusChoices.REJECTED
        return attrs

# --- Friend Transaction Serializer ---
class FriendTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for FriendTransaction model.
    """
    initiator = SimpleUserSerializer(read_only=True)
    friend = SimpleUserSerializer(read_only=True)
    friend_username = serializers.CharField(write_only=True, required=False)
    action_taken_by = SimpleUserSerializer(read_only=True)  
    
    class Meta:
        model = FriendTransaction
        fields = [
            'id',
            'initiator',
            'friend',
            'friend_username',
            'amount',
            'description',
            'status',
            'created_at',
            'updated_at',
            'action_taken_by', 
        ]
        read_only_fields = ['id', 'initiator', 'friend', 'status', 'created_at', 'updated_at', 'action_taken_by']
    
    def create(self, validated_data):
        # Remove friend_username since it's not a model field
        validated_data.pop('friend_username', None)
        return super().create(validated_data)
    
# --- Transaction Status Update Serializer ---
class TransactionStatusUpdateSerializer(serializers.Serializer):
    """
    Simple serializer to accept/reject a transaction.
    """
    action = serializers.ChoiceField(choices=['accept', 'reject'], required=True)

    def validate(self, attrs):
        action = attrs.get('action')
        if action == 'accept':
            attrs['status'] = FriendTransaction.StatusChoices.ACCEPTED
        elif action == 'reject':
            attrs['status'] = FriendTransaction.StatusChoices.REJECTED
        return attrs

# --- Login Serializer ---
class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(
                request=self.context.get('request'),
                username=username,
                password=password
            )
            if not user:
                raise serializers.ValidationError(_('Unable to log in with provided credentials.'))
        else:
            raise serializers.ValidationError(_('Must include "username" and "password".'))

        attrs['user'] = user
        return attrs

class TransactionDeleteRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for transaction delete requests.
    """
    requester = SimpleUserSerializer(read_only=True)
    transaction = FriendTransactionSerializer(read_only=True)
    
    class Meta:
        model = TransactionDeleteRequest
        fields = ['id', 'transaction', 'requester', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'requester', 'status', 'created_at', 'updated_at']


class HistoryResetRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for history reset requests.
    """
    requester = SimpleUserSerializer(read_only=True)
    target_user = SimpleUserSerializer(read_only=True)
    
    class Meta:
        model = HistoryResetRequest
        fields = ['id', 'requester', 'target_user', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'requester', 'target_user', 'status', 'created_at', 'updated_at']


class DeleteRequestActionSerializer(serializers.Serializer):
    """
    Simple serializer to approve/reject delete requests.
    """
    action = serializers.ChoiceField(choices=['approve', 'reject'], required=True)

    def validate(self, attrs):
        action = attrs.get('action')
        if action == 'approve':
            attrs['status'] = TransactionDeleteRequest.StatusChoices.APPROVED
        elif action == 'reject':
            attrs['status'] = TransactionDeleteRequest.StatusChoices.REJECTED
        return attrs


class ResetRequestActionSerializer(serializers.Serializer):
    """
    Simple serializer to approve/reject reset requests.
    """
    action = serializers.ChoiceField(choices=['approve', 'reject'], required=True)

    def validate(self, attrs):
        action = attrs.get('action')
        if action == 'approve':
            attrs['status'] = HistoryResetRequest.StatusChoices.APPROVED
        elif action == 'reject':
            attrs['status'] = HistoryResetRequest.StatusChoices.REJECTED
        return attrs
