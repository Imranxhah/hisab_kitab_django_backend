# accounts/models.py
from django.db import models
from django.conf import settings
from django.db.models import Q, UniqueConstraint
from django.contrib.auth.models import (
    AbstractUser,
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
from django.utils.translation import gettext_lazy as _ # For potential future translations

# Manager for the CustomUser model
class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        """
        Creates and saves a User with the given username and password.
        """
        if not username:
            raise ValueError(_('The Username must be set'))
        # username = self.normalize_email(username) # No email normalization needed
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        """
        Creates and saves a superuser with the given username and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(username, password, **extra_fields)

# Custom User Model (without email)
class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[AbstractUser.username_validator], # Use Django's built-in username validator
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)

    # Fields required by Django admin and auth system
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = CustomUserManager()

    # --- Settings for authentication ---
    # EMAIL_FIELD = None # No email field defined
    USERNAME_FIELD = 'username' # Use username for login
    REQUIRED_FIELDS = [] # Fields prompted for when using createsuperuser (besides username & password)
                           # Add 'first_name', 'last_name' if you want them required for superusers

    def clean(self):
        super().clean()
        # self.email = self.__class__.objects.normalize_email(self.email) # No email to normalize

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def __str__(self):
        return self.username



# accounts/models.py
# ... (Keep the CustomUserManager and CustomUser model code from before) ...

# 2. Friendship Model
class Friendship(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected' # Optional: Add if you want to explicitly track rejections

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, # Uses the AUTH_USER_MODEL setting (our CustomUser)
        related_name='sent_friend_requests',
        on_delete=models.CASCADE # If a user is deleted, their requests are also deleted
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='received_friend_requests',
        on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True) # Automatically set when created
    updated_at = models.DateTimeField(auto_now=True)     # Automatically set when saved

    class Meta:
        # Ensures a user cannot send multiple requests to the same person
        constraints = [
            UniqueConstraint(fields=['requester', 'receiver'], name='unique_friend_request'),
            # Prevent sending a request to oneself
            models.CheckConstraint(check=~Q(requester=models.F('receiver')), name='prevent_self_request')
        ]
        ordering = ['-created_at'] # Show newest requests first by default

    def __str__(self):
        # Provides a readable representation in the admin or shell
        return f"{self.requester.username} -> {self.receiver.username} ({self.status})"

# --- Leave space here for FriendTransaction model later ---


# accounts/models.py
# ... (Keep CustomUser and Friendship model code from before) ...

# 3. Friend Transaction Model
class FriendTransaction(models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'

    # The user who initiated (recorded) the transaction
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL, # Uses CustomUser
        related_name='initiated_transactions',
        on_delete=models.CASCADE
    )
    # The other friend involved in the transaction
    friend = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='involved_transactions',
        on_delete=models.CASCADE
    )
    # Amount: Positive means 'friend' owes 'initiator' (like a debit for the friend).
    #         Negative means 'initiator' owes 'friend' (like a credit for the friend).
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True) # Optional note
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True) # When the request was made
    updated_at = models.DateTimeField(auto_now=True)     # When status last changed

    # Who took the action (accept/reject) - should be the 'friend' (receiver of the request)
    action_taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='actioned_transactions',
        on_delete=models.SET_NULL, # Keep record even if user is deleted
        null=True, # Can be null initially or if user deleted
        blank=True # Allowed to be blank in forms/admin
    )

    class Meta:
        ordering = ['-created_at'] # Show newest transactions first by default
        # Optional: You might add a constraint to prevent initiating a transaction with oneself
        constraints = [
             models.CheckConstraint(check=~Q(initiator=models.F('friend')), name='prevent_self_transaction')
        ]

    def __str__(self):
        # Readable representation
        direction = "owes" if self.amount > 0 else "is owed by"
        return f"{self.initiator.username} -> {self.friend.username}: {abs(self.amount)} ({self.status}) - {self.initiator.username} {direction} {self.friend.username}"
    

class TransactionDeleteRequest(models.Model):
    """
    Model to track requests to delete a specific transaction.
    Both users must approve before deletion.
    """
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    transaction = models.ForeignKey(
        FriendTransaction,
        on_delete=models.CASCADE,
        related_name='delete_requests'
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transaction_delete_requests_sent'
    )
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['transaction', 'requester']  # Prevent duplicate requests

    def __str__(self):
        return f"Delete request for Transaction #{self.transaction.id} by {self.requester.username}"


class HistoryResetRequest(models.Model):
    """
    Model to track requests to reset transaction history between two friends.
    Both users must approve before reset.
    """
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='history_reset_requests_sent'
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='history_reset_requests_received'
    )
    status = models.CharField(
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Reset request from {self.requester.username} to {self.target_user.username}"