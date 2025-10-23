from rest_framework import serializers
from .models import CustomUser, Friendship, FriendTransaction
from django.contrib.auth import get_user_model, authenticate # Import authenticate
from django.utils.translation import gettext_lazy as _ # For error messages
# Get the active User model (our CustomUser)
User = get_user_model()

# --- User Serializer ---
class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the CustomUser model.
    Includes basic user information. Password is write-only.
    """
    class Meta:
        model = User
        # Fields to include in the serialized output
        fields = ['id', 'username', 'first_name', 'last_name', 'password']
        # Make password write-only (used for creation/update, but not shown in output)
        extra_kwargs = {
            'password': {'write_only': True, 'style': {'input_type': 'password'}}
        }

    # Override create to handle password hashing
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user

    # Optional: Override update if you want to allow password updates via PUT/PATCH
    # def update(self, instance, validated_data):
    #     password = validated_data.pop('password', None)
    #     user = super().update(instance, validated_data)
    #     if password:
    #         user.set_password(password)
    #         user.save()
    #     return user

# --- Simple User Serializer (for nested display) ---
class SimpleUserSerializer(serializers.ModelSerializer):
    """
    A simplified serializer for displaying user info within other serializers
    (like Friendship or Transaction), showing only essential fields.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name'] # Exclude sensitive info like password

# --- Friendship Serializer ---
class FriendshipSerializer(serializers.ModelSerializer):
    """
    Serializer for the Friendship model.
    Shows nested user details for requester and receiver.
    """
    # Use the SimpleUserSerializer for nested representation
    requester = SimpleUserSerializer(read_only=True)
    receiver = SimpleUserSerializer(read_only=True)

    # Allow setting receiver by username during creation
    receiver_username = serializers.CharField(write_only=True, required=False) # For sending requests

    class Meta:
        model = Friendship
        fields = [
            'id',
            'requester',
            'receiver',
            'status',
            'created_at',
            'updated_at',
            'receiver_username' # Include the write-only field
        ]
        read_only_fields = ['requester', 'status', 'created_at', 'updated_at'] # Fields not set directly by client on create

# --- FriendTransaction Serializer ---
class FriendTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for the FriendTransaction model.
    Shows nested user details for initiator and friend.
    """
    initiator = SimpleUserSerializer(read_only=True)
    friend = SimpleUserSerializer(read_only=True)
    action_taken_by = SimpleUserSerializer(read_only=True, allow_null=True)

    # Allow setting the friend by username during creation
    friend_username = serializers.CharField(write_only=True, required=False) # For creating transactions

    class Meta:
        model = FriendTransaction
        fields = [
            'id',
            'initiator',
            'friend',
            'amount',
            'description',
            'status',
            'created_at',
            'updated_at',
            'action_taken_by',
            'friend_username' # Include the write-only field
        ]
        # Fields not set directly by client on creation/update initially
        read_only_fields = ['initiator', 'status', 'created_at', 'updated_at', 'action_taken_by']


# --- Serializer for Updating Friendship Status (Accept/Reject) ---
class FriendshipStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        Friendship.StatusChoices.ACCEPTED,
        Friendship.StatusChoices.REJECTED
    ])

# --- Serializer for Updating Transaction Status (Accept/Reject) ---
class TransactionStatusUpdateSerializer(serializers.Serializer):
     status = serializers.ChoiceField(choices=[
        FriendTransaction.StatusChoices.ACCEPTED,
        FriendTransaction.StatusChoices.REJECTED
    ])
     

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    Requires the old password and validates the new password confirmation.
    """
    old_password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
    new_password1 = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
    new_password2 = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})

    def validate_old_password(self, value):
        """
        Check if the old password provided matches the user's current password.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Your old password was entered incorrectly. Please enter it again."))
        return value

    def validate(self, data):
        """
        Check that the two new password entries match.
        """
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError(_("The two password fields didn't match."))
        # You could add more password validation logic here (e.g., complexity requirements)
        # from django.contrib.auth.password_validation import validate_password
        # try:
        #     validate_password(data['new_password1'], self.context['request'].user)
        # except serializers.ValidationError as e:
        #     raise serializers.ValidationError({'new_password1': e.messages})
        return data

    def save(self, **kwargs):
        """
        Save the new password for the user.
        """
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password1'])
        user.save()
        return user